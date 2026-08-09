#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventory the skills that are actually installed on this machine.

Reads every SKILL.md it can find (personal, project, plugin) and pulls the
`name` and `description` out of the YAML frontmatter. Those two fields are all
the router needs: `description` is what the agent itself uses to decide whether
a skill applies, so classifying on it keeps the tree honest.

Usage:
    python scan_skills.py                     # human-readable summary
    python scan_skills.py --json out.json     # machine-readable inventory
    python scan_skills.py --path ./extra      # add a search root

No third-party dependencies. Python 3.8+.
"""

import argparse
import json
import os
import sys

MAX_DEPTH = 4  # how deep under a search root we look for SKILL.md


def home():
    return os.path.expanduser("~")


def search_roots(project_dir, extra, isolated=False):
    """Where skills live, in resolution order (later wins on name conflicts).

    Claude Code loads personal skills from ~/.claude/skills, project skills from
    <project>/.claude/skills, and plugin skills from the plugin cache. A project
    skill shadows a personal one with the same name, so project comes last.
    """
    roots = []
    if isolated:
        return [(os.path.abspath(p), "extra") for p in (extra or []) if os.path.isdir(p)]
    plugins = os.path.join(home(), ".claude", "plugins")
    for sub in ("marketplaces", "cache", "repos"):
        p = os.path.join(plugins, sub)
        if os.path.isdir(p):
            roots.append((p, "plugin"))
    personal = os.path.join(home(), ".claude", "skills")
    if os.path.isdir(personal):
        roots.append((personal, "personal"))
    if project_dir:
        proj = os.path.join(project_dir, ".claude", "skills")
        if os.path.isdir(proj):
            roots.append((proj, "project"))
    for p in extra or []:
        if os.path.isdir(p):
            roots.append((os.path.abspath(p), "extra"))
    return roots


def find_skill_files(root):
    """Walk a root looking for SKILL.md, skipping noise like .git and node_modules."""
    hits = []
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        if depth >= MAX_DEPTH:
            dirnames[:] = []
        dirnames[:] = [
            d for d in dirnames
            if d not in (".git", "node_modules", "__pycache__", ".venv", "venv",
                         "dist", "build", ".next", "evals", "assets")
        ]
        for fn in filenames:
            if fn.lower() == "skill.md":
                hits.append(os.path.join(dirpath, fn))
    return hits


def parse_frontmatter(path):
    """Pull name/description out of the YAML frontmatter.

    Deliberately a small hand-rolled reader rather than a YAML dependency: this
    script has to run on a stranger's machine with nothing installed. It handles
    the shapes that appear in real skills, including folded blocks
    (`description: >-`) and quoted values.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return {}
    if not text.lstrip().startswith("---"):
        return {}
    text = text.lstrip()
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]

    data = {}
    key = None
    buf = []
    folded = False

    def flush():
        if key is None:
            return
        value = " ".join(x.strip() for x in buf if x.strip()) if folded else "".join(buf)
        data[key] = clean_scalar(value)

    for raw in block.splitlines():
        if not raw.strip():
            if folded and key:
                buf.append("")
            continue
        indented = raw[:1] in (" ", "\t")
        if not indented and ":" in raw:
            flush()
            key, _, rest = raw.partition(":")
            key = key.strip()
            rest = rest.strip()
            folded = rest in (">", ">-", "|", "|-")
            buf = [] if folded else [rest]
        elif key is not None:
            folded = True
            buf.append(raw.strip())
    flush()
    return data


def clean_scalar(value):
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return " ".join(value.split())


def scan(project_dir=None, extra=None, isolated=False):
    seen = {}
    order = []
    for root, source in search_roots(project_dir, extra, isolated):
        for path in find_skill_files(root):
            meta = parse_frontmatter(path)
            name = meta.get("name") or os.path.basename(os.path.dirname(path))
            desc = meta.get("description", "")
            entry = {
                "name": name,
                "description": desc,
                "path": path.replace("\\", "/"),
                "source": source,
            }
            # The same skill vendored twice (marketplace + cache) is common.
            # A personal or project install shadows a plugin copy, the way
            # Claude Code resolves it, so that entry replaces the plugin one.
            # Otherwise the first sighting wins and later copies are dropped.
            if name in seen:
                prev = seen[name]
                if source in ("personal", "project", "extra") and prev["source"] == "plugin":
                    prev.update(entry)
                continue
            seen[name] = entry
            order.append(name)
    return [seen[n] for n in order]


def main():
    ap = argparse.ArgumentParser(description="Inventory installed Claude skills.")
    ap.add_argument("--project", default=os.getcwd(),
                    help="project directory to check for .claude/skills (default: cwd)")
    ap.add_argument("--path", action="append", default=[],
                    help="extra directory to search (repeatable)")
    ap.add_argument("--only-path", action="store_true",
                    help="search only the --path directories, ignoring installed skills")
    ap.add_argument("--json", metavar="FILE",
                    help="write the inventory as JSON (use - for stdout)")
    args = ap.parse_args()

    skills = scan(args.project, args.path, args.only_path)
    payload = {"count": len(skills), "skills": skills}

    if args.json:
        out = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json == "-":
            sys.stdout.write(out + "\n")
        else:
            with open(args.json, "w", encoding="utf-8") as fh:
                fh.write(out + "\n")
            sys.stderr.write("wrote %s (%d skills)\n" % (args.json, len(skills)))
        return

    by_source = {}
    for s in skills:
        by_source.setdefault(s["source"], []).append(s["name"])
    print("%d skills found" % len(skills))
    for source in ("personal", "project", "plugin", "extra"):
        names = by_source.get(source)
        if names:
            print("\n[%s] %d" % (source, len(names)))
            print("  " + ", ".join(sorted(names)))
    undocumented = [s["name"] for s in skills if not s["description"]]
    if undocumented:
        print("\nNo description (the router can't place these): "
              + ", ".join(sorted(undocumented)))


if __name__ == "__main__":
    main()
