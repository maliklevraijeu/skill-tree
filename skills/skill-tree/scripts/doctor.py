#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check that the install actually works, and say what to do when it does not.

    python doctor.py            # a readable report, exit 1 if something is broken
    python doctor.py --quiet    # one line: OK, or the first problem

"Did it work?" is the question every install raises and few answer. The build
printing a path is not an answer: the skill can sit in a folder Claude Code
never reads, the tree can be older than the skills it names, the hook can point
at a file that moved. Each check below is one of those failures, made visible.

Every problem prints the exact command that fixes it. No third-party imports,
so this runs on the machine of whoever is reporting the bug.
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scan_skills  # noqa: E402


def scripts_dir():
    """Where the user should run the fix from.

    Someone checking a clone runs the doctor from the repo, but the copy that
    matters is the installed one. Pointing a fix at the clone would repair a
    directory Claude Code never reads.
    """
    installed = os.path.join(scan_skills.claude_home(), "skills", "skill-tree", "scripts")
    return installed if os.path.isdir(installed) else HERE


TREE_BEGIN = "<!-- TREE:BEGIN -->"
TREE_END = "<!-- TREE:END -->"
HOOK_MARKER = "hook_reminder.py"


class Report(object):
    def __init__(self):
        self.lines = []
        self.problems = []

    def ok(self, label, detail=""):
        self.lines.append(("ok", label, detail, ""))

    def warn(self, label, detail="", fix=""):
        self.lines.append(("!", label, detail, fix))

    def fail(self, label, detail="", fix=""):
        self.lines.append(("x", label, detail, fix))
        self.problems.append((label, detail, fix))

    def render(self):
        width = max(len(l[1]) for l in self.lines) if self.lines else 0
        out = []
        for mark, label, detail, fix in self.lines:
            out.append("[%-2s] %-*s %s" % (mark, width, label, detail))
            if fix:
                out.append("     fix: %s" % fix)
        return "\n".join(out)


def ago(seconds):
    if seconds < 90:
        return "just now"
    if seconds < 5400:
        return "%d minutes ago" % (seconds // 60)
    if seconds < 172800:
        return "%d hours ago" % (seconds // 3600)
    return "%d days ago" % (seconds // 86400)


def python_check(report):
    version = "%d.%d.%d" % sys.version_info[:3]
    if sys.version_info[:2] < (3, 8):
        report.fail("Python", version + ", too old", "install Python 3.8 or later")
    else:
        report.ok("Python", version)


def config_check(report):
    base = scan_skills.claude_home()
    moved = bool(os.environ.get("CLAUDE_CONFIG_DIR"))
    if not os.path.isdir(base):
        report.fail("Claude config", "%s does not exist" % base,
                    "start Claude Code once, or set CLAUDE_CONFIG_DIR to the right folder")
        return base
    report.ok("Claude config", base + (" (via CLAUDE_CONFIG_DIR)" if moved else ""))
    return base


def install_check(report, base):
    """Installed where Claude Code reads, not just installed somewhere."""
    expected = os.path.join(base, "skills", "skill-tree")
    running_from = os.path.dirname(HERE)
    if os.path.isfile(os.path.join(expected, "SKILL.md")):
        note = "" if os.path.normcase(expected) == os.path.normcase(running_from) \
            else " (you are running a different copy: %s)" % running_from
        report.ok("Skill installed", expected + note)
        return True
    report.fail("Skill installed", "nothing at %s" % expected,
                "run install.py from the cloned repo")
    return False


def skills_check(report):
    skills = scan_skills.scan(os.getcwd(), [])
    if not skills:
        report.fail("Skills found", "none",
                    "install a skill or two, then rerun build_tree.py")
        return skills
    by_source = {}
    for s in skills:
        by_source[s["source"]] = by_source.get(s["source"], 0) + 1
    breakdown = ", ".join("%d %s" % (n, src) for src, n in sorted(by_source.items()))
    if len(skills) == 1:
        report.warn("Skills found", "1 (only this one), so the tree has nothing to route yet",
                    "install other skills, then rerun build_tree.py")
    else:
        report.ok("Skills found", "%d (%s)" % (len(skills), breakdown))
    return skills


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def tree_check(report, base, skills):
    routing = os.path.join(base, "skill-tree", "ROUTING.md")
    build = os.path.join(scripts_dir(), "build_tree.py")
    if not os.path.isfile(routing):
        report.fail("Tree", "not built yet", 'python "%s"' % build)
        return None

    text = read(routing)
    start, end = text.find(TREE_BEGIN), text.find(TREE_END)
    if start == -1 or end == -1:
        report.fail("Tree", "%s has no tree block in it" % routing, 'python "%s"' % build)
        return None

    body = text[start + len(TREE_BEGIN):end]
    branches = [l for l in body.splitlines() if l.startswith(("|--", "`--"))]
    named = body.count("/")
    age = ago(time.time() - os.path.getmtime(routing))
    if not branches:
        # No branches is only a fault when there was something to route. On a
        # machine whose only skill is this one, an empty tree is the correct
        # answer, and calling it broken would scare someone off on day one.
        if len(skills or []) > 3:
            report.fail("Tree", "built %s but every branch is empty" % age,
                        "add keywords to references/clusters.yaml, then rebuild")
        else:
            report.warn("Tree", "no branches yet, there is nothing to route with %d skill(s)"
                        % len(skills or []), "install a few skills, then rebuild")
        return routing

    report.ok("Tree", "%d branches, built %s" % (len(branches), age))
    report.ok("Tree file", routing)

    unplaced = 0
    for line in text.splitlines():
        if line.startswith("## Unplaced ("):
            unplaced = int(line.split("(")[1].split(")")[0])
    if skills and unplaced > len(skills) * 0.5:
        report.warn("Unplaced skills", "%d of %d could not be placed" % (unplaced, len(skills)),
                    "read the Unplaced list at the bottom of ROUTING.md, it is the part worth your time")
    elif unplaced:
        report.ok("Unplaced skills", "%d, listed at the bottom of the file" % unplaced)
    if named < 3:
        report.warn("Tree contents", "almost no skills are named in it",
                    "check that your skills have a description in their frontmatter")
    return routing


def stale_check(report, base, routing):
    if not routing:
        return
    import hook_reminder  # cheap, and keeps the staleness rule in one place
    if hook_reminder.is_stale(routing):
        report.warn("Tree freshness", "a skill was installed or removed since the build",
                    'python "%s"' % os.path.join(scripts_dir(), "build_tree.py"))
    else:
        report.ok("Tree freshness", "up to date with your skills folder")


def hook_check(report, base):
    """Installed is one thing, pointing at a file that still exists is another."""
    candidates = [os.path.join(base, "settings.json"),
                  os.path.join(os.getcwd(), ".claude", "settings.json")]
    found = []
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            data = json.loads(read(path) or "{}")
        except ValueError:
            report.warn("Settings", "%s is not valid JSON" % path, "fix the file by hand")
            continue
        for matcher in (data.get("hooks", {}).get("UserPromptSubmit") or []):
            for hook in (matcher.get("hooks") or []):
                command = str(hook.get("command", ""))
                if HOOK_MARKER in command:
                    found.append((path, command))

    installer = os.path.join(scripts_dir(), "install_hook.py")
    if not found:
        report.warn("Prompt hook", "not installed, the tree only loads when you ask for it",
                    'python "%s"' % installer)
        return

    for path, command in found:
        target = command.split('"')[-2] if command.count('"') >= 2 else ""
        if target and not os.path.isfile(target):
            report.fail("Prompt hook", "points at a file that is gone: %s" % target,
                        'python "%s" --uninstall, then reinstall' % installer)
        else:
            report.ok("Prompt hook", "active in %s" % path)


def main():
    ap = argparse.ArgumentParser(description="Check that skill-tree is working.")
    ap.add_argument("--quiet", action="store_true", help="one line of output")
    args = ap.parse_args()

    report = Report()
    python_check(report)
    base = config_check(report)
    install_check(report, base)
    skills = skills_check(report)
    routing = tree_check(report, base, skills)
    stale_check(report, base, routing)
    hook_check(report, base)

    if args.quiet:
        if report.problems:
            label, detail, fix = report.problems[0]
            print("BROKEN: %s, %s" % (label.lower(), detail))
        else:
            print("OK")
        return 1 if report.problems else 0

    print("skill-tree doctor")
    print("")
    print(report.render())
    print("")
    if report.problems:
        print("%d thing(s) to fix, listed above." % len(report.problems))
    else:
        print("Everything checks out. Paste this report if you report a bug.")
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
