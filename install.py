#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install the skill and build your tree, in one command.

    python install.py           # install, then build the tree
    python install.py --hook    # also wire the always-on prompt hook
    python install.py --dry-run # say what would happen, touch nothing

Copies skills/skill-tree into ~/.claude/skills/, then runs the build so you
end up with a ROUTING.md instead of an installed thing you still have to
figure out. Nothing to install beyond Python 3.8.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "skills", "skill-tree")
sys.path.insert(0, os.path.join(SOURCE, "scripts"))

import scan_skills  # noqa: E402
# Overridable so the tests can install into a scratch directory instead of the
# real one. Nobody needs it in normal use.
TARGET = os.environ.get("SKILL_TREE_TARGET") or os.path.join(
    scan_skills.claude_home(), "skills", "skill-tree")


def copy(dry_run):
    if not os.path.isdir(SOURCE):
        raise SystemExit("Cannot find %s. Run this from inside the cloned repo." % SOURCE)
    existing = os.path.isdir(TARGET)
    verb = "Updating" if existing else "Installing"
    print("%s %s" % (verb, TARGET))
    if dry_run:
        return existing
    parent = os.path.dirname(TARGET)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    if existing:
        # Replace the code, keep nothing stale behind. Anything the user edited
        # lives in ROUTING.md or in their own copy of clusters.yaml, neither of
        # which is in here, so this is safe to blow away.
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return existing


def run(script, *args):
    cmd = [sys.executable, os.path.join(TARGET, "scripts", script)] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stdout.write(proc.stderr)
    return proc.returncode, (proc.stdout + proc.stderr)


def main():
    ap = argparse.ArgumentParser(description="Install skill-tree and build your routing tree.")
    ap.add_argument("--hook", action="store_true",
                    help="also install the UserPromptSubmit hook that shows the tree every message")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen")
    args = ap.parse_args()

    copy(args.dry_run)
    if args.dry_run:
        print("Would then build the tree into ~/.claude/skill-tree/ROUTING.md")
        if args.hook:
            print("Would then install the prompt hook into ~/.claude/settings.json")
        return

    print("")
    # Point the build at where the skill just landed. Without this, an install
    # into a non-standard location builds a tree that cannot see itself.
    code, output = run("build_tree.py", "--path", os.path.dirname(TARGET))
    if code != 0:
        if "No skills found" in output:
            print("")
            print("Installed, but there are no skills here to route yet.")
            print("Install a few, then run: python \"%s\""
                  % os.path.join(TARGET, "scripts", "build_tree.py"))
            return
        raise SystemExit("The build failed. Open an issue with the output above.")

    if args.hook:
        print("")
        if run("install_hook.py", "--yes")[0] != 0:
            print("The hook did not install. Everything else works, run it later with:")
            print('  python "%s" ' % os.path.join(TARGET, "scripts", "install_hook.py"))

    # Finish on a diagnosis rather than a path. "It printed something" is not
    # the same as "it works", and the difference is what people report back.
    print("")
    run("doctor.py")
    if not args.hook:
        print("")
        print("To have the tree in front of the agent on every message, rerun with --hook.")
    print("Open your tree, the branches are named after your own skills.")


if __name__ == "__main__":
    main()
