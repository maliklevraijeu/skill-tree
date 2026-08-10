#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for skill-tree.

Run them with the standard library, nothing to install:

    python -m unittest discover -s tests -v

Each test exercises a public seam: the frontmatter reader, the config parser,
the scorer, the classifier, the renderer, and the two CLIs end to end. Nothing
here reaches into private state, so the internals stay free to change.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "skill-tree", "scripts")
CONFIG = os.path.join(ROOT, "skills", "skill-tree", "references", "clusters.yaml")
sys.path.insert(0, SCRIPTS)

import build_tree            # noqa: E402
import hook_reminder         # noqa: E402
import scan_skills           # noqa: E402


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def write_skill(root, name, description, extra=""):
    folder = os.path.join(root, name)
    os.makedirs(folder, exist_ok=True)
    write(os.path.join(folder, "SKILL.md"),
          "---\nname: %s\ndescription: %s\n%s---\n\n# %s\n" % (name, description, extra, name))
    return folder


class TempCorpus(unittest.TestCase):
    """Base class giving each test its own throwaway skills directory."""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="skill-tree-test-")
        self.addCleanup(shutil.rmtree, self.dir, True)


class FrontmatterTest(TempCorpus):
    def read(self, text):
        path = os.path.join(self.dir, "SKILL.md")
        write(path, text)
        return scan_skills.parse_frontmatter(path)

    def test_reads_name_and_description(self):
        meta = self.read("---\nname: pdf\ndescription: Work with PDF files.\n---\n\n# PDF\n")
        self.assertEqual(meta["name"], "pdf")
        self.assertEqual(meta["description"], "Work with PDF files.")

    def test_joins_a_folded_description(self):
        meta = self.read("---\nname: x\ndescription: >-\n  first line\n  second line\n---\n")
        self.assertEqual(meta["description"], "first line second line")

    def test_joins_a_wrapped_description(self):
        meta = self.read("---\nname: x\ndescription: starts here\n  and wraps\n---\n")
        self.assertEqual(meta["description"], "starts here and wraps")

    def test_strips_matching_quotes(self):
        meta = self.read('---\nname: x\ndescription: "quoted value"\n---\n')
        self.assertEqual(meta["description"], "quoted value")

    def test_keeps_an_apostrophe_inside_a_value(self):
        meta = self.read("---\nname: x\ndescription: it's fine\n---\n")
        self.assertEqual(meta["description"], "it's fine")

    def test_a_file_without_frontmatter_yields_nothing(self):
        self.assertEqual(self.read("# Just a heading\n"), {})

    def test_an_unterminated_frontmatter_yields_nothing(self):
        self.assertEqual(self.read("---\nname: x\ndescription: y\n"), {})


class ScanTest(TempCorpus):
    def test_finds_skills_and_labels_the_source(self):
        write_skill(self.dir, "alpha", "Does alpha things.")
        write_skill(self.dir, "beta", "Does beta things.")
        found = scan_skills.scan(None, [self.dir], isolated=True)
        self.assertEqual({s["name"] for s in found}, {"alpha", "beta"})
        self.assertEqual({s["source"] for s in found}, {"extra"})

    def test_falls_back_to_the_folder_name_when_frontmatter_is_missing(self):
        folder = os.path.join(self.dir, "nameless")
        os.makedirs(folder)
        write(os.path.join(folder, "SKILL.md"), "# no frontmatter\n")
        found = scan_skills.scan(None, [self.dir], isolated=True)
        self.assertEqual(found[0]["name"], "nameless")
        self.assertEqual(found[0]["description"], "")

    def test_a_skill_vendored_twice_is_reported_once(self):
        other = tempfile.mkdtemp(prefix="skill-tree-test-")
        self.addCleanup(shutil.rmtree, other, True)
        write_skill(self.dir, "twin", "First copy.")
        write_skill(other, "twin", "Second copy.")
        found = scan_skills.scan(None, [self.dir, other], isolated=True)
        self.assertEqual(len(found), 1)

    def test_isolated_mode_ignores_the_installed_skills(self):
        write_skill(self.dir, "solo", "Only me.")
        found = scan_skills.scan(os.getcwd(), [self.dir], isolated=True)
        self.assertEqual([s["name"] for s in found], ["solo"])

    def test_it_does_not_descend_into_vendor_directories(self):
        write_skill(os.path.join(self.dir, "node_modules"), "ghost", "Should not appear.")
        write_skill(self.dir, "real", "Should appear.")
        found = scan_skills.scan(None, [self.dir], isolated=True)
        self.assertEqual([s["name"] for s in found], ["real"])


class ConfigParserTest(unittest.TestCase):
    def test_parses_the_shipped_taxonomy(self):
        clusters, overrides = build_tree.load_config(CONFIG)
        self.assertGreater(len(clusters), 5)
        ids = [c["id"] for c in clusters]
        self.assertIn("writing", ids)
        self.assertEqual(len(ids), len(set(ids)), "cluster ids must be unique")
        for c in clusters:
            self.assertTrue(c["label"] and c["branch"])
            self.assertIsInstance(c["strong"], list)

    def test_the_bundled_parser_agrees_with_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        text = read(CONFIG)
        self.assertEqual(build_tree.parse_simple_yaml(text), yaml.safe_load(text))

    def test_inline_lists_and_scalars(self):
        data = build_tree.parse_simple_yaml(
            "clusters:\n"
            "  - id: one\n"
            "    label: First\n"
            "    strong: [a, b, c]\n"
            "    upstream: []\n"
        )
        first = data["clusters"][0]
        self.assertEqual(first["strong"], ["a", "b", "c"])
        self.assertEqual(first["upstream"], [])
        self.assertEqual(first["label"], "First")

    def test_comments_and_blank_lines_are_ignored(self):
        data = build_tree.parse_simple_yaml(
            "# leading comment\n\nclusters:\n  - id: one\n    label: First\n\n# trailing\n")
        self.assertEqual(len(data["clusters"]), 1)

    def test_overrides_are_read(self):
        clusters, overrides = build_tree.load_config(CONFIG)
        self.assertIsInstance(overrides, dict)


def cluster(**kw):
    base = {"id": "test", "label": "Test", "branch": "TEST", "note": "",
            "strong": [], "match": [], "upstream": [], "overlay": []}
    base.update(kw)
    return base


class ScoringTest(unittest.TestCase):
    def test_a_name_hit_outweighs_a_description_hit(self):
        c = cluster(strong=["design"])
        by_name = build_tree.score_skill({"name": "design-system", "description": ""}, c)
        by_desc = build_tree.score_skill({"name": "zzz", "description": "about design"}, c)
        self.assertGreater(by_name, by_desc)

    def test_a_hyphenated_name_matches_a_spaced_keyword(self):
        c = cluster(strong=["code review"])
        self.assertGreaterEqual(
            build_tree.score_skill({"name": "code-review", "description": ""}, c), 6)

    def test_description_hits_are_capped(self):
        c = cluster(match=["a%d" % i for i in range(40)])
        verbose = {"name": "zzz", "description": " ".join("a%d" % i for i in range(40))}
        self.assertLessEqual(build_tree.score_skill(verbose, c), build_tree.DESC_CAP)

    def test_role_keywords_count_in_the_name_but_not_the_description(self):
        c = cluster(overlay=["review"])
        self.assertGreater(build_tree.score_skill({"name": "review-me", "description": ""}, c), 0)
        self.assertEqual(build_tree.score_skill({"name": "zzz", "description": "review"}, c), 0)

    def test_an_unrelated_skill_scores_zero(self):
        c = cluster(strong=["seo"], match=["ranking"])
        self.assertEqual(build_tree.score_skill({"name": "pdf", "description": "PDF files"}, c), 0)


class RoleTest(unittest.TestCase):
    def test_an_overlay_is_recognised_by_its_name(self):
        c = cluster(overlay=["humaniz"])
        self.assertEqual(build_tree.role_of({"name": "humanizer"}, c, {}), "overlay")

    def test_an_upstream_is_recognised_by_its_name(self):
        c = cluster(upstream=["audit"])
        self.assertEqual(build_tree.role_of({"name": "seo-audit"}, c, {}), "upstream")

    def test_a_description_alone_does_not_set_a_role(self):
        c = cluster(overlay=["review"])
        skill = {"name": "impeccable", "description": "audit, critique and review a UI"}
        self.assertEqual(build_tree.role_of(skill, c, {}), "member")

    def test_an_override_wins(self):
        c = cluster(overlay=["humaniz"])
        overrides = {("humanizer", "test"): "member"}
        self.assertEqual(build_tree.role_of({"name": "humanizer"}, c, overrides), "member")


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        self.clusters = [
            cluster(id="writing", label="Writing", branch="WRITE",
                    strong=["copywriting", "humanizer"], match=["write", "copy"],
                    overlay=["humaniz"]),
            cluster(id="seo", label="SEO", branch="SEO",
                    strong=["seo", "backlink"], match=["ranking"], upstream=["audit"]),
        ]

    def classify(self, skills):
        return build_tree.classify(skills, self.clusters)

    def test_a_clear_skill_lands_in_its_cluster(self):
        buckets, unplaced = self.classify([{"name": "copywriting", "description": "Write copy."}])
        self.assertEqual([e["name"] for e in buckets["writing"]["core"]], ["copywriting"])
        self.assertEqual(unplaced, [])

    def test_an_overlay_lands_in_the_overlay_slot(self):
        buckets, _ = self.classify([{"name": "humanizer", "description": "Rewrite copy."}])
        self.assertEqual([e["name"] for e in buckets["writing"]["overlays"]], ["humanizer"])
        self.assertEqual(buckets["writing"]["core"], [])

    def test_an_upstream_lands_in_the_upstream_slot(self):
        buckets, _ = self.classify([{"name": "seo-audit", "description": "Audit a site."}])
        self.assertEqual([e["name"] for e in buckets["seo"]["upstream"]], ["seo-audit"])

    def test_an_unmatched_skill_is_reported_unplaced(self):
        buckets, unplaced = self.classify([{"name": "montage-video", "description": "Edit video."}])
        self.assertEqual([s["name"] for s in unplaced], ["montage-video"])

    def test_a_skill_never_exceeds_the_cluster_ceiling(self):
        skills = [{"name": "seo-copywriting", "description": "Write copy that ranks."}]
        buckets, _ = self.classify(skills)
        placements = sum(
            1 for b in buckets.values() for slot in ("core", "modules", "upstream", "overlays")
            for e in b[slot] if e["name"] == "seo-copywriting")
        self.assertLessEqual(placements, build_tree.MAX_CLUSTERS)

    def test_only_the_strongest_members_become_bases(self):
        skills = [{"name": "copywriting-%d" % i, "description": "Write copy."} for i in range(6)]
        buckets, _ = self.classify(skills)
        self.assertLessEqual(len(buckets["writing"]["core"]), build_tree.MAX_CORE)
        self.assertTrue(buckets["writing"]["modules"])

    def test_raising_the_threshold_places_fewer_skills(self):
        skills = [{"name": "notes", "description": "Write and copy things."}]
        loose, _ = build_tree.classify(skills, self.clusters, min_score=1)
        _, strict_unplaced = build_tree.classify(skills, self.clusters, min_score=99)
        self.assertTrue(loose["writing"]["core"])
        self.assertEqual(len(strict_unplaced), 1)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.clusters, self.overrides = build_tree.load_config(CONFIG)
        self.skills = [
            {"name": "copywriting", "description": "Write marketing copy."},
            {"name": "humanizer", "description": "Remove AI patterns from a draft."},
            {"name": "quantum-flapdoodle", "description": "Nothing anyone can classify."},
        ]
        self.buckets, self.unplaced = build_tree.classify(
            self.skills, self.clusters, overrides=self.overrides)

    def render(self, house_rules=""):
        return build_tree.render(self.buckets, self.clusters, self.unplaced,
                                 self.skills, house_rules, CONFIG)

    def test_the_tree_markers_are_present_and_ordered(self):
        out = self.render()
        self.assertIn(build_tree.TREE_BEGIN, out)
        self.assertLess(out.index(build_tree.TREE_BEGIN), out.index(build_tree.TREE_END))

    def test_unplaced_skills_are_listed_with_their_description(self):
        out = self.render()
        self.assertIn("quantum-flapdoodle", out)
        self.assertIn("Nothing anyone can classify.", out)

    def test_house_rules_are_carried_into_the_output(self):
        out = self.render("Always start with the grill skill.")
        self.assertIn("Always start with the grill skill.", out)
        self.assertIn(build_tree.RULES_BEGIN, out)

    def test_the_tree_names_real_skills(self):
        tree = hook_reminder.extract_tree(self.render())
        self.assertIn("/copywriting", tree)


class HouseRulesTest(TempCorpus):
    def path(self, text):
        p = os.path.join(self.dir, "ROUTING.md")
        io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        return p

    def test_rules_survive_a_rebuild(self):
        p = self.path("# ROUTING\n%s\nkeep me\n%s\n" % (build_tree.RULES_BEGIN, build_tree.RULES_END))
        self.assertEqual(build_tree.existing_house_rules(p), "keep me")

    def test_a_missing_file_yields_no_rules(self):
        self.assertEqual(build_tree.existing_house_rules(os.path.join(self.dir, "absent.md")), "")

    def test_a_file_without_markers_yields_no_rules(self):
        self.assertEqual(build_tree.existing_house_rules(self.path("# ROUTING\nno markers\n")), "")


class HookTest(TempCorpus):
    def test_it_extracts_only_the_tree(self):
        text = "before\n%s\nTREE BODY\n%s\nafter" % (build_tree.TREE_BEGIN, build_tree.TREE_END)
        self.assertEqual(hook_reminder.extract_tree(text), "TREE BODY")

    def test_no_markers_means_no_tree(self):
        self.assertEqual(hook_reminder.extract_tree("nothing here"), "")

    def test_a_tree_built_after_the_skills_is_fresh(self):
        skills = os.path.join(self.dir, "skills")
        os.makedirs(skills)
        routing = os.path.join(self.dir, "ROUTING.md")
        write(routing, "x")
        os.utime(routing, (2_000_000_000, 2_000_000_000))
        os.utime(skills, (1_000_000_000, 1_000_000_000))
        self.assertFalse(hook_reminder.is_stale(routing, [skills]))

    def test_a_skill_installed_after_the_build_makes_it_stale(self):
        skills = os.path.join(self.dir, "skills")
        os.makedirs(skills)
        routing = os.path.join(self.dir, "ROUTING.md")
        write(routing, "x")
        os.utime(routing, (1_000_000_000, 1_000_000_000))
        os.utime(skills, (2_000_000_000, 2_000_000_000))
        self.assertTrue(hook_reminder.is_stale(routing, [skills]))

    def test_a_missing_skills_folder_is_not_stale(self):
        routing = os.path.join(self.dir, "ROUTING.md")
        write(routing, "x")
        self.assertFalse(hook_reminder.is_stale(routing, [os.path.join(self.dir, "absent")]))

    def test_it_stays_silent_when_routing_is_missing(self):
        out = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "hook_reminder.py"),
             os.path.join(self.dir, "absent.md")],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")

    def test_it_emits_valid_hook_json(self):
        routing = os.path.join(self.dir, "ROUTING.md")
        io.open(routing, "w", encoding="utf-8", newline="\n").write(
            "# ROUTING\n%s\n```\nREQUEST\n|-- WRITE\n```\n%s\n" % (build_tree.TREE_BEGIN, build_tree.TREE_END))
        out = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "hook_reminder.py"), routing],
            capture_output=True, text=True, timeout=60)
        payload = json.loads(out.stdout)
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn("REQUEST", payload["hookSpecificOutput"]["additionalContext"])


class EndToEndTest(TempCorpus):
    def build(self, *args):
        return subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "build_tree.py")] + list(args),
            capture_output=True, text=True, timeout=180)

    def test_it_writes_a_routing_file_from_a_corpus(self):
        write_skill(self.dir, "copywriting", "Write and rewrite marketing copy for landing pages.")
        write_skill(self.dir, "humanizer", "Remove AI writing patterns from a draft.")
        out = os.path.join(self.dir, "ROUTING.md")
        run = self.build("--path", self.dir, "--only-path", "--out", out)
        self.assertEqual(run.returncode, 0, run.stderr)
        text = read(out)
        self.assertIn("/copywriting", text)
        self.assertIn(build_tree.TREE_BEGIN, text)

    def test_a_rebuild_preserves_hand_written_rules(self):
        write_skill(self.dir, "copywriting", "Write marketing copy.")
        out = os.path.join(self.dir, "ROUTING.md")
        self.build("--path", self.dir, "--only-path", "--out", out)
        text = io.open(out, encoding="utf-8").read()
        io.open(out, "w", encoding="utf-8", newline="\n").write(
            text.replace(build_tree.RULES_BEGIN, build_tree.RULES_BEGIN + "\nMY OWN RULE"))
        self.build("--path", self.dir, "--only-path", "--out", out)
        self.assertIn("MY OWN RULE", read(out))

    def test_an_empty_corpus_fails_loudly(self):
        run = self.build("--path", self.dir, "--only-path", "--print")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("No skills found", run.stdout + run.stderr)

    def test_the_json_dump_matches_the_tree(self):
        write_skill(self.dir, "seo-audit", "Audit a site for technical SEO issues.")
        out = os.path.join(self.dir, "ROUTING.md")
        dump = os.path.join(self.dir, "classification.json")
        self.build("--path", self.dir, "--only-path", "--out", out, "--json", dump)
        data = json.loads(read(dump))
        placed = [n for cid, b in data.items() if cid != "_unplaced"
                  for slot in ("upstream", "core", "modules", "overlays") for n in b[slot]]
        self.assertIn("seo-audit", placed + data["_unplaced"])

    def test_the_installer_previews_without_touching_anything(self):
        settings = os.path.join(self.dir, ".claude", "settings.json")
        run = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "install_hook.py"), "--dry-run", "--project"],
            cwd=self.dir, capture_output=True, text=True, timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(os.path.exists(settings), "dry run must not write")

    def test_the_installer_adds_and_removes_its_own_hook_only(self):
        claude = os.path.join(self.dir, ".claude")
        os.makedirs(claude)
        settings = os.path.join(claude, "settings.json")
        io.open(settings, "w", encoding="utf-8", newline="\n").write(json.dumps({
            "model": "opus",
            "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo mine"}]}]},
        }))
        args = [sys.executable, os.path.join(SCRIPTS, "install_hook.py"), "--project", "--yes"]
        subprocess.run(args, cwd=self.dir, capture_output=True, text=True, timeout=60)
        after = json.loads(read(settings))
        commands = [h["command"] for m in after["hooks"]["UserPromptSubmit"] for h in m["hooks"]]
        self.assertEqual(len(commands), 2)
        self.assertTrue(any("hook_reminder.py" in c for c in commands))
        self.assertEqual(after["model"], "opus", "unrelated settings must survive")

        subprocess.run(args + ["--uninstall"], cwd=self.dir, capture_output=True, text=True, timeout=60)
        final = json.loads(read(settings))
        left = [h["command"] for m in final["hooks"]["UserPromptSubmit"] for h in m["hooks"]]
        self.assertEqual(left, ["echo mine"], "only our hook should be removed")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class InstallerTest(TempCorpus):
    """The one-command installer, exercised against a scratch target."""

    def run_installer(self, *args, **kw):
        env = dict(os.environ, SKILL_TREE_TARGET=os.path.join(self.dir, "skill-tree"))
        env.update(kw.get("env", {}))
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "install.py")] + list(args),
            capture_output=True, text=True, timeout=180, env=env)

    def test_a_dry_run_touches_nothing(self):
        run = self.run_installer("--dry-run")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "skill-tree")))

    def test_it_copies_the_skill_where_claude_looks_for_it(self):
        run = self.run_installer()
        self.assertEqual(run.returncode, 0, run.stderr)
        target = os.path.join(self.dir, "skill-tree")
        self.assertTrue(os.path.exists(os.path.join(target, "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(target, "scripts", "build_tree.py")))
        self.assertTrue(os.path.exists(os.path.join(target, "references", "clusters.yaml")))

    def test_reinstalling_over_an_old_copy_leaves_nothing_stale(self):
        self.run_installer()
        target = os.path.join(self.dir, "skill-tree")
        stale = os.path.join(target, "scripts", "removed_in_a_later_version.py")
        write(stale, "# left over from an older install\n")
        self.run_installer()
        self.assertFalse(os.path.exists(stale))
        self.assertTrue(os.path.exists(os.path.join(target, "SKILL.md")))

    def test_it_tells_you_where_your_tree_landed(self):
        run = self.run_installer()
        self.assertIn("ROUTING.md", run.stdout)


class ConfigDirTest(TempCorpus):
    """CLAUDE_CONFIG_DIR moves the whole Claude directory. Everything follows it."""

    def setUp(self):
        super(ConfigDirTest, self).setUp()
        self.previous = os.environ.get("CLAUDE_CONFIG_DIR")
        self.addCleanup(self.restore)

    def restore(self):
        if self.previous is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.previous

    def test_the_variable_moves_the_config_directory(self):
        os.environ["CLAUDE_CONFIG_DIR"] = self.dir
        self.assertEqual(scan_skills.claude_home(), self.dir)

    def test_without_it_the_default_is_used(self):
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        self.assertTrue(scan_skills.claude_home().endswith(".claude"))

    def test_skills_are_found_under_the_moved_directory(self):
        os.environ["CLAUDE_CONFIG_DIR"] = self.dir
        write_skill(os.path.join(self.dir, "skills"), "relocated", "Lives somewhere else.")
        found = scan_skills.scan(None, [])
        self.assertIn("relocated", [s["name"] for s in found])


class VirginMachineTest(TempCorpus):
    """The first-run path, which is the one a stranger hits and I cannot see."""

    def install(self, **extra):
        home = os.path.join(self.dir, "home")
        os.makedirs(home, exist_ok=True)
        env = dict(os.environ, HOME=home, USERPROFILE=home)
        env.pop("CLAUDE_CONFIG_DIR", None)
        env.pop("SKILL_TREE_TARGET", None)
        env.update(extra)
        return subprocess.run([sys.executable, os.path.join(ROOT, "install.py")],
                              capture_output=True, text=True, timeout=180, env=env), env

    def test_installing_on_a_machine_with_no_other_skills_succeeds(self):
        run, env = self.install()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("ROUTING.md", run.stdout)

    def test_a_target_outside_the_config_dir_still_builds(self):
        target = os.path.join(self.dir, "elsewhere", "skill-tree")
        run, env = self.install(SKILL_TREE_TARGET=target)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue(os.path.exists(os.path.join(target, "SKILL.md")))

    def test_it_honours_a_relocated_config_dir(self):
        config = os.path.join(self.dir, "custom-config")
        run, env = self.install(CLAUDE_CONFIG_DIR=config)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertTrue(os.path.exists(os.path.join(config, "skills", "skill-tree", "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(config, "skill-tree", "ROUTING.md")))
