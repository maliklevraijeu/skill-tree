---
name: skill-tree
description: Builds and applies a routing tree over the skills actually installed on this machine, so a request arms the whole relevant group of skills instead of one lucky guess. Use this whenever the user asks which skill to use, says their skills go unused or that you keep forgetting them, wants their skills organised, connected, mapped, or routed, asks to set up automatic skill selection, installs a batch of new skills, or asks what they even have installed. Also use it before starting substantial work when the right combination of skills is not obvious.
---

# Skill tree

Most people install skills faster than they use them. The skills sit there, the
agent picks whichever one the request happens to name, and the other thirty
never fire. Worse, the skill that should have run *before* the work (the one
that decides what to make) gets called after it, when it can only rubber-stamp
what already exists.

This skill fixes the selection step. It reads the skills that are actually
installed on this machine, groups them into clusters, and writes a decision
tree whose branches name real skills. Then every request routes through the
tree instead of through memory.

## First move: is there a tree already?

```bash
cat ~/.claude/skill-tree/ROUTING.md
```

If that file exists, read it and route from it. It is the user's map, including
whatever they wrote in the house rules block, and it beats anything you would
infer on the fly.

If it does not exist, build it. The scripts sit next to this file:

```bash
python <this skill's folder>/scripts/build_tree.py   # writes ~/.claude/skill-tree/ROUTING.md
```

If the user asked you to install this from the repo, clone it somewhere
temporary and run `python install.py` from the clone: that copies the skill
into `~/.claude/skills/` and builds the tree in one go.

The build takes a second or two and needs nothing installed beyond Python 3.8.
Report what came back: how many skills were found, how many were placed, how
many were not.

## The three commands

```bash
python scripts/scan_skills.py                 # what is installed, and where
python scripts/build_tree.py                  # write ROUTING.md
python scripts/install_hook.py --dry-run      # preview the always-on hook
```

`scan_skills.py` reads every SKILL.md it can find: personal skills in
`~/.claude/skills`, project skills in `<project>/.claude/skills`, and plugin
skills from the plugin cache. It pulls the name and description out of each
frontmatter, which is the same information the agent uses to choose a skill in
the first place.

`build_tree.py` scores each skill against the clusters in
`references/clusters.yaml` and writes the tree. Rerun it after installing or
removing skills.

`install_hook.py` adds one UserPromptSubmit hook that prints the tree ahead of
every message. Offer it, explain what it changes, and let the user decide. It
backs up settings.json, leaves other hooks alone, and `--uninstall` reverses it.
Without the hook the tree still works, it just has to be read on purpose.

## How to route

The tree is not a lookup table. Four rules make it work.

**Arm the whole branch, not one skill.** A design request pulls the design base
skill, the modules that match the specific job, and the overlays. Picking the
one skill whose name matches the request is the failure this file exists to
prevent. Invoke them for real with the Skill tool, before producing a line, not
as a mention in your reply.

**Run `first` before you produce.** Those skills decide what to make: who it is
for, what the angle is, what the spec says. They are worthless after the fact.
If the branch has a `first` entry and the request is substantial, that call
happens before anything else.

**`base` means pick exactly one.** Several skills usually cover the same ground
from different angles (build versus audit versus direction). Read the
descriptions, choose the one that fits this job, and say in one line why.
Stacking all of them wastes context and produces mush.

**`always` means always.** Overlays are the standards nothing ships without: an
editor, a reviewer, a checker. If the branch produces output, the overlays run
on that output. This is the rule people most often skip, and it is the one that
decides whether the result is publishable.

When two branches both apply (a landing page is design plus conversion plus
writing), arm the base of the primary branch and pull the overlays of the
others. A skill invoked twice costs nothing.

When nothing matches, say so in one line and do the work directly. An
unnecessary skill call is worse than none.

## What the scripts cannot do, and you can

Keyword matching gets the bulk of the corpus right and openly fails on the
rest. Three gaps are yours to close:

**Unplaced skills.** The bottom of ROUTING.md lists everything the scoring
could not confidently place, with descriptions. Skills named in another
language, or named after an internal concept, land here almost every time. Read
them, work out where they belong, and either say so in the house rules block or
add the keywords that would have caught them to `clusters.yaml`. Both survive a
rebuild.

**Wrong roles.** A skill in the wrong slot (a base filed as an overlay, say)
gets pinned in the `overrides` block of `clusters.yaml`. One entry per fix.

**The expert lens.** A skill is one practitioner's opinion written down. When a
request lands in a domain where the user follows someone specific, apply that
lens alongside the cluster. That is a house rule, not something a script can
infer, so it belongs in the house rules block of ROUTING.md.

## Editing the tree

`ROUTING.md` is regenerated by the build, with one exception: anything between
the `HOUSE-RULES` markers is carried over untouched. Rules that a taxonomy
cannot express go there.

`references/clusters.yaml` is the taxonomy itself. It ships generic on purpose
and gets better the moment the user bends it to their own work. Adding a
cluster means adding an entry with an id, a label, a branch line, and keywords.
When the user's work does not look like the default clusters at all (research
science, legal, teaching, ops), rewriting that file is the right move, not a
workaround.

Read `references/customizing.md` before making non-trivial edits to either.

## Setting it up for someone

When the user asks for the full setup, do it in this order:

1. Run `scan_skills.py` and tell them what they have. The count alone is
   usually a surprise.
2. Run `build_tree.py` and read the result yourself.
3. Go through the unplaced list with them, briefly. This is where their
   idiosyncratic skills get placed, and it is worth the two minutes.
4. Offer the hook with `install_hook.py --dry-run` first, so they see the exact
   line before it touches their settings.
5. Suggest one or two house rules based on what you have seen in their tree.

Then use the tree yourself for the rest of the session, out loud, so they can
see the difference.
