# skill-tree

A router over the skills you already have.

[Version française](README.fr.md)

Count what is installed on your machine:

```bash
ls ~/.claude/skills | wc -l
```

Now count how many you used this week. For most people the second number is
three or four, whatever the first one says.

Installing skills is the easy half. The agent picks whichever skill the request
happens to name, and the rest of the library sits there. The skill that should
run *before* the work, the one that decides what to make, gets called after it,
where it can only approve what already exists.

skill-tree reads the skills that are actually on your machine, groups them into
clusters, and writes a decision tree whose branches name real skills. Then it
puts that tree in front of the agent on every message, so selection stops being
a guess.

## What it produces

Run one command and you get a `ROUTING.md` like this, built from your own
skills:

```
REQUEST
|
|-- WRITE (post, article, script, email, page copy, doc)
|     base: /copywriting
|     always: /copy-editing, /humanizer, /no-ai-slop, /plain-writing
|-- CODE (build, debug, refactor, review, ship)
|     base (pick one): /tdd, /codebase-design, /resolving-merge-conflicts
|     always: /code-review, /git-guardrails
|-- SEO (rankings, technical audit, content clusters)
|     first: /seo-audit
|     base: /seo-content
|-- DECIDE (stress-test a plan, choose between options, scope a build)
|     base: /grilling
```

Four roles, and they are the whole idea:

- `first` runs before you produce anything. It decides what to make.
- `base` is a group of alternatives. Pick one, not all of them.
- `modules` are the pieces you add depending on the specific job.
- `always` are the standards every output of that branch passes through.

A full generated example, from a corpus of well-known public skills, is in
[examples/ROUTING.example.md](examples/ROUTING.example.md).

## Install

As a Claude Code plugin:

```
/plugin marketplace add OWNER/skill-tree
/plugin install skill-tree@skill-tree
```

With the skills CLI:

```bash
npx skills add OWNER/skill-tree
```

By hand:

```bash
git clone https://github.com/OWNER/skill-tree
cp -r skill-tree/skills/skill-tree ~/.claude/skills/
```

Python 3.8 or later, and nothing else. No packages to install, no API calls, no
network access. PyYAML is used if you happen to have it.

## Use

Ask your agent to build the tree, or run it yourself:

```bash
cd ~/.claude/skills/skill-tree

python scripts/scan_skills.py        # what you have, and where it came from
python scripts/build_tree.py         # writes ~/.claude/skill-tree/ROUTING.md
```

Rebuild after installing or removing skills. The build is instant and reads
nothing but frontmatter.

### The always-on part

The tree only changes how you work if it is present when you type. One hook
does that:

```bash
python scripts/install_hook.py --dry-run   # see the exact line first
python scripts/install_hook.py             # install, after confirmation
python scripts/install_hook.py --uninstall # remove it
```

It appends a single `UserPromptSubmit` entry to `~/.claude/settings.json`,
backs the file up first, and leaves every other hook alone. On each message it
prints the tree, around 1 to 3 KB depending on how many skills you have.

Skip it if you would rather invoke `/skill-tree` on purpose. Everything else
works the same.

## How skills get classified

Each skill is scored against the clusters in
[clusters.yaml](skills/skill-tree/references/clusters.yaml) using the name and
description from its frontmatter, which is the same information the agent uses
to choose a skill in the first place. Name matches decide, description matches
confirm, and what a description alone can contribute is capped so that one
verbose skill does not end up in every branch.

The scoring is deliberately conservative. On a large, idiosyncratic corpus
around a fifth of skills come back unplaced, listed with their descriptions at
the bottom of ROUTING.md. Skills named in another language, or named after an
internal concept, land there almost every time. That list is the part worth
reading: those are your skills, and placing them by hand takes two minutes.

Three ways to correct it, all of which survive a rebuild:

- Add keywords to `clusters.yaml`, or add a cluster of your own.
- Pin a skill's role in the `overrides` block of the same file.
- Write a sentence in the house rules block at the bottom of ROUTING.md, which
  is copied forward on every build.

See [customizing.md](skills/skill-tree/references/customizing.md) for the
details, including how to replace the taxonomy entirely. The shipped clusters
describe a generalist who writes, builds, designs and markets. If your work
looks nothing like that, rewriting that one file is the highest-leverage thing
you can do here.

## What it does not do

It does not install, update or remove skills. It does not call a model to
classify anything, so there is no cost and no latency. It does not read the
body of your skills, only the frontmatter. And it cannot invent structure that
your skills do not have: a corpus of forty skills with vague one-line
descriptions produces a vague tree.

## Why a tree and not a list

A list of skills tells the agent what exists. It does not say what to reach for
first, which two options are alternatives, or what has to run over the output
before anything ships. Those three questions are where skill selection actually
fails, and a tree is the smallest structure that answers them.

The strongest rule in the file is `always`. Overlay skills, the editors and
reviewers and checkers, are the ones people skip when they are moving fast, and
they are what separates a draft from something publishable.

## License

MIT. See [LICENSE](LICENSE).
