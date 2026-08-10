#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Feed the routing tree back into every prompt.

Claude Code runs this as a UserPromptSubmit hook. It prints the tree from
ROUTING.md as additional context, so the branch to arm is in front of the model
before it starts working rather than one Skill call away.

The tree only, not the whole file: this text is prepended to every single
message, so it has to stay small. Everything else lives in ROUTING.md, which
the model can read when it needs the detail.

Prints nothing at all when ROUTING.md is missing, which keeps a half-finished
install from breaking every prompt.
"""

import json
import os
import sys

def claude_home():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


DEFAULT_ROUTING = os.path.join(claude_home(), "skill-tree", "ROUTING.md")
TREE_BEGIN = "<!-- TREE:BEGIN -->"
TREE_END = "<!-- TREE:END -->"
MAX_CHARS = 2600

PREAMBLE = (
    "SKILL TREE (automatic). Before producing anything, match the request to a "
    "branch below and invoke the WHOLE branch with the Skill tool, not one skill "
    "out of it. `first` runs before you produce. `base` means pick one. `always` "
    "means every output of that branch passes through it. Nothing matches: say so "
    "in one line and carry on. Full map, unplaced skills and house rules: %s"
)


def routing_path():
    return (
        (sys.argv[1] if len(sys.argv) > 1 else None)
        or os.environ.get("SKILL_TREE_ROUTING")
        or DEFAULT_ROUTING
    )


def extract_tree(text):
    start = text.find(TREE_BEGIN)
    end = text.find(TREE_END)
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start + len(TREE_BEGIN):end].strip()


def is_stale(routing, roots=None):
    """True when a skills directory changed after the tree was built.

    A directory's mtime moves when an entry is added or removed, so installing
    or deleting a skill makes the tree stale without anything having to watch
    for it. Comparing three stat calls costs nothing, which matters: this runs
    on every single prompt. A tree that silently goes out of date is worse than
    no tree, because it routes confidently to skills that are gone.
    """
    if roots is None:
        base = claude_home()
        roots = [os.path.join(base, "skills"),
                 os.path.join(base, "plugins", "marketplaces"),
                 os.path.join(os.getcwd(), ".claude", "skills")]
    try:
        built = os.path.getmtime(routing)
    except OSError:
        return False
    for root in roots:
        try:
            if os.path.getmtime(root) > built:
                return True
        except OSError:
            continue
    return False


def main():
    path = routing_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return

    tree = extract_tree(text)
    if not tree:
        return
    if len(tree) > MAX_CHARS:
        tree = tree[:MAX_CHARS].rsplit("\n", 1)[0] + "\n... (truncated, read the file)"

    context = PREAMBLE % path + "\n\n" + tree
    if is_stale(path):
        context += ("\n\nThis tree is older than the skills folder, so a skill was installed or "
                    "removed since it was built. Rebuild it before relying on a branch: "
                    "python \"%s\"" % os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                   "build_tree.py"))
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A hook that crashes is a hook that ruins every prompt. Stay quiet.
        pass
