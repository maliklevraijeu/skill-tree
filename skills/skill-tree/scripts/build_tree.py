#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Turn an inventory of installed skills into a routing tree.

Reads every SKILL.md on the machine (via scan_skills.py), scores each skill
against the clusters in references/clusters.yaml, and writes ROUTING.md: a
decision tree whose branches name the skills you actually have.

Usage:
    python build_tree.py                       # write ~/.claude/skill-tree/ROUTING.md
    python build_tree.py --print               # print it instead
    python build_tree.py --out ./ROUTING.md    # somewhere else
    python build_tree.py --config my.yaml      # your own taxonomy

Anything you write between the HOUSE RULES markers in ROUTING.md survives a
rebuild, so the file is safe to edit by hand.

No third-party dependencies (PyYAML is used if present). Python 3.8+.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scan_skills  # noqa: E402

DEFAULT_CONFIG = os.path.join(os.path.dirname(HERE), "references", "clusters.yaml")
DEFAULT_OUT = os.path.join(os.path.expanduser("~"), ".claude", "skill-tree", "ROUTING.md")

TREE_BEGIN = "<!-- TREE:BEGIN -->"
TREE_END = "<!-- TREE:END -->"
RULES_BEGIN = "<!-- HOUSE-RULES:BEGIN -->"
RULES_END = "<!-- HOUSE-RULES:END -->"

MIN_SCORE = 6           # below this, a skill is not confidently in a cluster
SECONDARY_RATIO = 0.75  # a second cluster needs 75% of the winner's score
MAX_CLUSTERS = 2
MAX_CORE = 3            # how many "pick one of these" skills a cluster shows
DESC_CAP = 6            # ceiling on what description keywords alone can score

DEFAULT_RULES = """\
Write your own rules here. They survive every rebuild.

Good candidates: a skill that must run before anything else, a pair that always
goes together, a house standard nothing ships without, an expert lens you want
applied to a given subject.
"""


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------

def parse_scalar(value):
    value = (value or "").strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [unquote(x) for x in inner.split(",") if x.strip()]
    return unquote(value)


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def parse_simple_yaml(text):
    """Parse the small YAML subset clusters.yaml is written in.

    Supported: top-level keys, a list of items under a key, scalar values and
    inline lists. That is the whole grammar, which is why this can be 25 lines
    instead of a dependency.
    """
    data = {}
    current_key = None
    current_item = None
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == 0:
            key, sep, rest = stripped.partition(":")
            if not sep:
                continue
            key = key.strip()
            if rest.strip():
                data[key] = parse_scalar(rest)
                current_key, current_item = None, None
            else:
                data[key] = []
                current_key, current_item = key, None
            continue
        if stripped.startswith("- "):
            current_item = {}
            if current_key is None:
                continue
            data[current_key].append(current_item)
            stripped = stripped[2:].strip()
        if current_item is None:
            continue
        key, sep, rest = stripped.partition(":")
        if sep:
            current_item[key.strip()] = parse_scalar(rest)
    return data


def load_config(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml  # optional, only if the user happens to have it
        data = yaml.safe_load(text)
    except Exception:
        data = parse_simple_yaml(text)
    clusters = data.get("clusters") if isinstance(data, dict) else None
    if not clusters:
        raise SystemExit("No clusters found in %s" % path)
    for c in clusters:
        for field in ("strong", "match", "upstream", "overlay"):
            value = c.get(field) or []
            if isinstance(value, str):
                value = [value]
            c[field] = [str(v).strip().lower() for v in value if str(v).strip()]
        c["id"] = str(c.get("id") or "cluster").strip()
        c["label"] = str(c.get("label") or c["id"]).strip()
        c["branch"] = str(c.get("branch") or c["label"]).strip()
        c["note"] = str(c.get("note") or "").strip()

    overrides = {}
    for item in (data.get("overrides") or []):
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill", "")).strip().lower()
        cluster = str(item.get("cluster", "")).strip()
        role = str(item.get("role", "")).strip().lower()
        if skill and cluster and role in ("overlay", "upstream", "member"):
            overrides[(skill, cluster)] = role
    return clusters, overrides


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def score_skill(skill, cluster):
    """Name matches decide, description matches only confirm.

    Skill descriptions vary wildly in length, and a 2000-character description
    will brush against every cluster in the file. Capping what the description
    can contribute keeps a verbose skill from colonising branches it has no
    business being in.
    """
    name = skill_name_forms(skill)
    desc = (skill.get("description") or "").lower()
    name_score = 0
    desc_score = 0
    for kw in cluster["strong"]:
        if kw in name:
            name_score += 6
        elif kw in desc:
            desc_score += 3
    for kw in cluster["match"]:
        if kw in name:
            name_score += 3
        elif kw in desc:
            desc_score += 1
    # Role keywords earn membership when they appear in the name, otherwise a
    # skill like "to-spec" scores zero on a cluster it obviously belongs to.
    # They are ignored in descriptions, where words like "test" and "plan" show
    # up in half the corpus and pull unrelated skills into the branch.
    for kw in cluster["upstream"] + cluster["overlay"]:
        if kw in name:
            name_score += 3
    return name_score + min(desc_score, DESC_CAP)


def skill_name_forms(skill):
    """Both "code-review" and "code review", so hyphenated names match phrases."""
    name = (skill.get("name") or "").lower().replace("_", "-")
    return name + " " + name.replace("-", " ")


def role_of(skill, cluster, overrides):
    """Overlay, upstream, or a plain member of the cluster.

    Overlays ride along with every output of the cluster (an editor, a
    reviewer, a checker). Upstream skills decide what to make before anything
    gets made. Everything else is a module you pick from.

    Roles are read from the skill NAME only. Matching descriptions here was the
    first version and it misfired constantly: half the design skills mention
    the word "review" somewhere, which turned every base skill into an overlay.
    A name is a deliberate label, so it is the better signal. To place a skill
    the name cannot express, pin it in the `overrides` block of the config.
    """
    pinned = overrides.get((skill.get("name", "").lower(), cluster["id"]))
    if pinned:
        return pinned
    name = skill_name_forms(skill)
    for kw in cluster["overlay"]:
        if kw in name:
            return "overlay"
    for kw in cluster["upstream"]:
        if kw in name:
            return "upstream"
    return "member"


def classify(skills, clusters, min_score=MIN_SCORE, overrides=None):
    overrides = overrides or {}
    buckets = {c["id"]: {"cluster": c, "upstream": [], "core": [], "modules": [], "overlays": []}
               for c in clusters}
    unplaced = []

    for skill in skills:
        scored = [(score_skill(skill, c), c) for c in clusters]
        scored = [(s, c) for s, c in scored if s >= min_score]
        if not scored:
            unplaced.append(skill)
            continue
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        best = scored[0][0]
        keep = [(s, c) for s, c in scored if s >= best * SECONDARY_RATIO][:MAX_CLUSTERS]
        for s, c in keep:
            role = role_of(skill, c, overrides)
            entry = dict(skill)
            entry["score"] = s
            entry["primary"] = (c["id"] == keep[0][1]["id"])
            if role == "overlay":
                buckets[c["id"]]["overlays"].append(entry)
            elif role == "upstream":
                buckets[c["id"]]["upstream"].append(entry)
            else:
                buckets[c["id"]]["modules"].append(entry)

    # The highest-scoring members of a cluster are its bases: the skills that
    # cover the whole job rather than one slice of it. Surfacing two or three
    # is what turns a flat list into "pick one of these, then add modules".
    for bucket in buckets.values():
        members = sorted(bucket["modules"], key=lambda e: (-e["score"], e["name"]))
        bucket["core"] = members[:MAX_CORE]
        bucket["modules"] = members[MAX_CORE:]
        bucket["upstream"].sort(key=lambda e: (-e["score"], e["name"]))
        bucket["overlays"].sort(key=lambda e: (-e["score"], e["name"]))
    return buckets, unplaced


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def names(entries):
    return ", ".join("/" + e["name"] for e in entries)


def render_tree(buckets, clusters):
    lines = ["REQUEST", "|"]
    active = [c for c in clusters if any(buckets[c["id"]][k] for k in ("core", "modules", "upstream", "overlays"))]
    for i, cluster in enumerate(active):
        bucket = buckets[cluster["id"]]
        last = (i == len(active) - 1)
        stem = "`-- " if last else "|-- "
        pad = "    " if last else "|   "
        lines.append(stem + cluster["branch"])
        if bucket["upstream"]:
            lines.append(pad + "  first: " + names(bucket["upstream"][:3]))
        if bucket["core"]:
            label = "  base (pick one): " if len(bucket["core"]) > 1 else "  base: "
            lines.append(pad + label + names(bucket["core"]))
        if bucket["modules"]:
            lines.append(pad + "  modules: " + names(bucket["modules"][:8]))
        if bucket["overlays"]:
            lines.append(pad + "  always: " + names(bucket["overlays"][:4]))
    return "\n".join(lines)


def render(buckets, clusters, unplaced, skills, house_rules, config_path):
    out = []
    out.append("# ROUTING")
    out.append("")
    out.append("Generated by skill-tree from the %d skills installed on this machine. "
               "Rebuild it with `python build_tree.py` after you install or remove skills."
               % len(skills))
    out.append("")
    out.append("Read the tree, arm the whole branch that matches the request, then work. "
               "One skill out of a branch is the failure mode this file exists to prevent.")
    out.append("")
    out.append(TREE_BEGIN)
    out.append("```")
    out.append(render_tree(buckets, clusters))
    out.append("```")
    out.append(TREE_END)
    out.append("")
    out.append("## Clusters")
    out.append("")

    for cluster in clusters:
        bucket = buckets[cluster["id"]]
        if not any(bucket[k] for k in ("core", "modules", "upstream", "overlays")):
            continue
        out.append("### %s" % cluster["label"])
        if cluster["note"]:
            out.append("")
            out.append(cluster["note"])
        out.append("")
        if bucket["upstream"]:
            out.append("- Before producing: %s" % names(bucket["upstream"]))
        if bucket["core"]:
            verb = "Base, pick one" if len(bucket["core"]) > 1 else "Base"
            out.append("- %s: %s" % (verb, names(bucket["core"])))
        if bucket["modules"]:
            out.append("- Modules: %s" % names(bucket["modules"]))
        if bucket["overlays"]:
            out.append("- Always on: %s" % names(bucket["overlays"]))
        out.append("")

    if unplaced:
        out.append("## Unplaced (%d)" % len(unplaced))
        out.append("")
        out.append("Keyword matching could not place these with confidence. Read the "
                   "descriptions, put the useful ones in a branch above, and add the "
                   "keywords that would have caught them to `%s`."
                   % os.path.basename(config_path))
        out.append("")
        for skill in sorted(unplaced, key=lambda s: s["name"]):
            desc = (skill.get("description") or "").strip()
            if len(desc) > 150:
                desc = desc[:147].rstrip() + "..."
            out.append("- **/%s** %s" % (skill["name"], desc or "(no description)"))
        out.append("")

    out.append("## House rules")
    out.append("")
    out.append(RULES_BEGIN)
    out.append(house_rules.strip() or DEFAULT_RULES.strip())
    out.append(RULES_END)
    out.append("")
    return "\n".join(out)


def existing_house_rules(path):
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return ""
    start = text.find(RULES_BEGIN)
    end = text.find(RULES_END)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start + len(RULES_BEGIN):end].strip()


def main():
    ap = argparse.ArgumentParser(description="Build a routing tree from installed skills.")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="cluster taxonomy (YAML)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="where to write ROUTING.md")
    ap.add_argument("--project", default=os.getcwd(), help="project dir to scan for .claude/skills")
    ap.add_argument("--path", action="append", default=[], help="extra skills directory (repeatable)")
    ap.add_argument("--only-path", action="store_true",
                    help="search only the --path directories, ignoring installed skills")
    ap.add_argument("--min-score", type=int, default=MIN_SCORE, help="confidence threshold")
    ap.add_argument("--print", dest="to_stdout", action="store_true", help="print instead of writing")
    ap.add_argument("--json", metavar="FILE", help="also dump the classification as JSON")
    args = ap.parse_args()

    clusters, overrides = load_config(args.config)
    skills = scan_skills.scan(args.project, args.path, args.only_path)
    if not skills:
        raise SystemExit("No skills found. Nothing to route.")
    buckets, unplaced = classify(skills, clusters, args.min_score, overrides)

    rules = existing_house_rules(args.out) if not args.to_stdout else ""
    text = render(buckets, clusters, unplaced, skills, rules, args.config)

    if args.to_stdout:
        sys.stdout.write(text)
    else:
        folder = os.path.dirname(os.path.abspath(args.out))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        placed = len(skills) - len(unplaced)
        sys.stderr.write("wrote %s\n%d skills, %d placed, %d unplaced\n"
                         % (args.out, len(skills), placed, len(unplaced)))

    if args.json:
        payload = {cid: {
            "label": b["cluster"]["label"],
            "upstream": [e["name"] for e in b["upstream"]],
            "core": [e["name"] for e in b["core"]],
            "modules": [e["name"] for e in b["modules"]],
            "overlays": [e["name"] for e in b["overlays"]],
        } for cid, b in buckets.items()}
        payload["_unplaced"] = [s["name"] for s in unplaced]
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
