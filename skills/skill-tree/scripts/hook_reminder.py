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

DEFAULT_ROUTING = os.path.join(os.path.expanduser("~"), ".claude", "skill-tree", "ROUTING.md")
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
