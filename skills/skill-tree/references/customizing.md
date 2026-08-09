# Customizing the tree

The shipped taxonomy is a starting point built to cover a generalist. It gets
useful when it matches one person's actual work. Everything below is meant to
be edited.

## Where each thing lives

| What | File | Survives a rebuild |
| --- | --- | --- |
| The taxonomy (clusters, keywords) | `references/clusters.yaml` | yes, it is the input |
| Role fixes for a specific skill | `overrides:` in `clusters.yaml` | yes |
| Rules a taxonomy cannot express | house rules block in `ROUTING.md` | yes |
| The generated tree | rest of `ROUTING.md` | no, rewritten every build |

## Adding a cluster

Append an entry to `clusters:`. Only `id` and `label` are required, but a
cluster without keywords will stay empty.

```yaml
  - id: legal
    label: Contracts and compliance
    branch: LEGAL (contract, policy, compliance review)
    strong: [contract, compliance, gdpr, privacy policy, terms of service, nda]
    match: [legal, clause, liability, regulation, audit trail, jurisdiction]
    upstream: [risk, scope, jurisdiction check]
    overlay: [review, redline]
    note: A clause you cannot explain in one sentence is a clause you have not read.
```

The four keyword lists do different jobs:

- `strong` is near-proof of membership. Weight 6 in the skill name, 3 in the
  description.
- `match` is supporting evidence. Weight 3 in the name, 1 in the description.
- `upstream` marks the skills that decide what to make, before making it. They
  print as `first` in the tree.
- `overlay` marks the skills that ride along with every output of the cluster.
  They print as `always`.

`upstream` and `overlay` also earn membership when they hit the skill name, but
they are ignored inside descriptions. Words like "plan", "test" and "review"
appear in half of any skill corpus, and letting them count there dragged
unrelated skills into every branch.

Keywords are plain lowercase substrings. `seo` matches `seo-audit` and also
`video-seo`. Names are matched twice, hyphenated and spaced, so `code review`
catches a skill named `code-review`.

## Pinning a role

When a skill lands in the right cluster with the wrong role, pin it:

```yaml
overrides:
  - skill: ab-testing
    cluster: code
    role: member
  - skill: my-house-style
    cluster: writing
    role: overlay
```

`role` is `overlay`, `upstream`, or `member`. Match `skill` to the skill's name
as it appears in the tree, without the leading slash.

## House rules

The block at the bottom of `ROUTING.md` between the `HOUSE-RULES` markers is
copied forward on every rebuild. It is the place for anything a keyword list
cannot hold:

- A skill that must run before everything, whatever the branch.
- Two skills that only work as a pair.
- A standard nothing ships without.
- An expert lens to apply on a given subject.
- Where an unplaced skill belongs, when adding keywords for it would be
  clumsier than one sentence.

Write it as instructions to an agent, in the imperative, and give the reason.
A rule whose reason is stated gets applied in situations you did not foresee.
A bare command gets applied literally and nowhere else.

## Tuning the scoring

Constants at the top of `build_tree.py`:

| Constant | Default | What it does |
| --- | --- | --- |
| `MIN_SCORE` | 6 | Confidence needed to place a skill. Lower catches more and adds noise. |
| `SECONDARY_RATIO` | 0.75 | How strong a second cluster must be, relative to the winner, to also claim the skill. |
| `MAX_CLUSTERS` | 2 | How many branches one skill can appear in. |
| `MAX_CORE` | 3 | How many "pick one of these" skills a branch shows. |
| `DESC_CAP` | 6 | Ceiling on what description keywords alone can contribute. Stops a 2000-character description from colonising every branch. |

Check the effect before keeping it:

```bash
python build_tree.py --print | head -60      # the tree, without writing
python build_tree.py --min-score 4 --print   # try a threshold
python build_tree.py --json classification.json
```

A tree where nothing is unplaced usually means the threshold is too low and the
branches are full of skills that do not belong. Twenty percent unplaced on a
large, idiosyncratic corpus is normal, and those are exactly the skills worth
placing by hand.

## Per-project trees

Skills in `<project>/.claude/skills` are picked up automatically when you build
from inside the project. To keep a project tree separate from the personal one:

```bash
python build_tree.py --out ./.claude/ROUTING.md
python install_hook.py --project --dry-run
```

The hook reads whichever path it is given as its first argument, and falls back
to `SKILL_TREE_ROUTING` in the environment, then to the personal file.

## The config file format

`clusters.yaml` is real YAML, but the parser used when PyYAML is absent
understands one shape only: top-level keys, a list of items under a key, and
scalar or inline-list values. Two levels, no nesting, no multi-line lists.

```yaml
clusters:
  - id: thing              # scalar
    match: [a, b, c]       # inline list
```

Install PyYAML if you want the full grammar. The parser is used automatically
when it is available, and both paths produce the same result on the shipped
file.

## When the whole taxonomy is wrong

If the default clusters describe someone else's job, replace the file. Sixteen
marketing-and-engineering clusters are the wrong map for a researcher, a
lawyer, or a teacher. Point `--config` at your own version and keep the shipped
one as a reference:

```bash
python build_tree.py --config ~/my-clusters.yaml
```

Writing a taxonomy from scratch takes about twenty minutes and is the single
highest-leverage edit in this repo.
