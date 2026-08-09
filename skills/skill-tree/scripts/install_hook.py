#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wire (or unwire) the routing tree into every prompt.

Adds one UserPromptSubmit hook to ~/.claude/settings.json that runs
hook_reminder.py. That is the difference between a skill you have to remember
to call and a tree that is simply there when you type.

    python install_hook.py --dry-run     # show the change, touch nothing
    python install_hook.py               # install, after confirmation
    python install_hook.py --uninstall   # remove it
    python install_hook.py --project     # write to ./.claude/settings.json

Your settings file is backed up before any write. Every other hook you have is
left exactly as it was: this only ever appends or removes its own entry.
"""

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REMINDER = os.path.join(HERE, "hook_reminder.py")
MARKER = "hook_reminder.py"
EVENT = "UserPromptSubmit"


def settings_path(project):
    if project:
        return os.path.join(os.getcwd(), ".claude", "settings.json")
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8-sig") as fh:
        text = fh.read().strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except ValueError as exc:
        raise SystemExit("%s is not valid JSON (%s). Fix it before installing." % (path, exc))


def command():
    python = sys.executable or "python3"
    return '"%s" "%s"' % (python, REMINDER)


def entries(settings):
    hooks = settings.setdefault("hooks", {})
    matchers = hooks.setdefault(EVENT, [])
    return matchers


def already_installed(matchers):
    for matcher in matchers:
        for hook in (matcher.get("hooks") or []):
            if MARKER in str(hook.get("command", "")):
                return True
    return False


def remove_ours(matchers):
    removed = 0
    kept = []
    for matcher in matchers:
        hooks = [h for h in (matcher.get("hooks") or []) if MARKER not in str(h.get("command", ""))]
        removed += len(matcher.get("hooks") or []) - len(hooks)
        if hooks:
            matcher["hooks"] = hooks
            kept.append(matcher)
        elif not matcher.get("hooks"):
            kept.append(matcher)
    return kept, removed


def write(path, settings):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    if os.path.exists(path):
        backup = path + ".skill-tree-backup"
        shutil.copyfile(path, backup)
        print("backed up %s" % backup)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(settings, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def confirm(question):
    try:
        answer = input("%s [y/N] " % question).strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def main():
    ap = argparse.ArgumentParser(description="Install the skill-tree prompt hook.")
    ap.add_argument("--uninstall", action="store_true", help="remove the hook")
    ap.add_argument("--dry-run", action="store_true", help="show the change without writing")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    ap.add_argument("--project", action="store_true",
                    help="write to ./.claude/settings.json instead of the personal one")
    args = ap.parse_args()

    path = settings_path(args.project)
    settings = load(path)
    matchers = entries(settings)

    if args.uninstall:
        kept, removed = remove_ours(matchers)
        if not removed:
            print("Nothing to remove: no skill-tree hook in %s" % path)
            return
        settings["hooks"][EVENT] = kept
        print("Will remove %d skill-tree hook(s) from %s" % (removed, path))
        if args.dry_run:
            return
        if args.yes or confirm("Remove?"):
            write(path, settings)
            print("Removed.")
        return

    if already_installed(matchers):
        print("Already installed in %s. Nothing to do." % path)
        print("The hook reads ROUTING.md at run time, so rebuilding the tree is "
              "enough to update what it says.")
        return

    if not os.path.exists(REMINDER):
        raise SystemExit("Cannot find %s" % REMINDER)

    new_entry = {"hooks": [{"type": "command", "command": command(), "timeout": 10}]}
    print("Will add to %s, under hooks.%s:" % (path, EVENT))
    print(json.dumps(new_entry, indent=2))
    existing = sum(len(m.get("hooks") or []) for m in matchers)
    if existing:
        print("(%d existing %s hook(s) stay untouched)" % (existing, EVENT))
    if args.dry_run:
        return
    if not (args.yes or confirm("Install?")):
        print("Cancelled.")
        return

    matchers.append(new_entry)
    write(path, settings)
    print("Installed. Restart Claude Code, or start a new session, to pick it up.")


if __name__ == "__main__":
    main()
