# skill-tree

Un routeur au-dessus des skills que tu as déjà.

[![tests](https://github.com/maliklevraijeu/skill-tree/actions/workflows/tests.yml/badge.svg)](https://github.com/maliklevraijeu/skill-tree/actions/workflows/tests.yml)

Compte ce qui est installé sur ta machine :

```bash
ls ~/.claude/skills | wc -l
```

Maintenant compte combien tu en as utilisés cette semaine. Chez la plupart des
gens, le deuxième chiffre est trois ou quatre, quel que soit le premier.

Installer des skills, c'est la partie facile. L'agent prend celui dont la
requête cite le nom, et le reste de la bibliothèque dort. Le skill qui devrait
tourner *avant* le travail, celui qui décide quoi produire, est appelé après,
quand il ne peut plus que valider ce qui existe déjà.

skill-tree lit les skills réellement présents sur la machine, les regroupe en
clusters, et écrit un arbre de décision dont les branches portent le nom de tes
skills. Ensuite il met cet arbre devant l'agent à chaque message, pour que la
sélection cesse d'être une devinette.

## Ce que ça produit

Une commande, et tu obtiens un `ROUTING.md` construit à partir de tes propres
skills :

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
```

Quatre rôles, et c'est toute l'idée :

- `first` tourne avant de produire quoi que ce soit. Il décide quoi faire.
- `base` est un groupe d'alternatives. Tu en prends un seul.
- `modules` sont les pièces à ajouter selon le travail précis.
- `always` sont les standards par lesquels passe toute sortie de la branche.

Un exemple complet, généré depuis un corpus de skills publics connus, est dans
[examples/ROUTING.example.md](examples/ROUTING.example.md).

## Installation

Le plus simple : demande-le à Claude Code. Colle ça dans une session :

> Installe le skill depuis https://github.com/maliklevraijeu/skill-tree et construis mon arbre de routage.

Ou une seule commande dans un terminal :

```bash
git clone https://github.com/maliklevraijeu/skill-tree && python skill-tree/install.py
```

Ça copie le skill là où Claude Code va le chercher, construit ton arbre, et
affiche où il est. Ajoute `--hook` pour brancher aussi le hook permanent décrit
plus bas.

En plugin Claude Code :

```
/plugin marketplace add maliklevraijeu/skill-tree
/plugin install skill-tree@skill-tree
```

Python 3.8 ou plus, rien d'autre. Aucun paquet à installer, aucun appel API,
aucun accès réseau.

## Utilisation

Demande à ton agent de construire l'arbre, ou lance-le toi-même :

```bash
cd ~/.claude/skills/skill-tree

python scripts/scan_skills.py        # ce que tu as, et d'où ça vient
python scripts/build_tree.py         # écrit ~/.claude/skill-tree/ROUTING.md
```

Reconstruis après avoir installé ou retiré des skills. Le build est instantané
et ne lit que le frontmatter.

### La partie automatique

L'arbre ne change ta façon de travailler que s'il est présent au moment où tu
tapes. Un hook s'en charge :

```bash
python scripts/install_hook.py --dry-run   # voir la ligne exacte d'abord
python scripts/install_hook.py             # installer, après confirmation
python scripts/install_hook.py --uninstall # retirer
```

Il ajoute une seule entrée `UserPromptSubmit` dans `~/.claude/settings.json`,
sauvegarde le fichier avant, et ne touche à aucun autre hook. À chaque message
il imprime l'arbre, entre 1 et 3 Ko selon le nombre de skills.

Il détecte aussi quand l'arbre est périmé. Installer ou retirer un skill change
la date du dossier de skills, et quand elle est plus récente que ROUTING.md, le
hook ajoute une ligne qui dit à l'agent de reconstruire avant de se fier à une
branche. Un arbre périmé est pire que pas d'arbre, il route avec assurance vers
des skills qui n'existent plus.

Tu peux t'en passer et invoquer `/skill-tree` quand tu veux. Le reste
fonctionne pareil.

## Comment les skills sont classés

Chaque skill est noté contre les clusters de
[clusters.yaml](skills/skill-tree/references/clusters.yaml), à partir du nom et
de la description de son frontmatter. C'est exactement l'information que
l'agent utilise pour choisir un skill. Le nom décide, la description confirme,
et ce qu'une description seule peut apporter est plafonné pour qu'un skill
bavard ne se retrouve pas dans toutes les branches.

Le scoring est volontairement prudent. Sur un corpus large et personnel, un
cinquième des skills revient non classé, listé avec sa description en bas de
ROUTING.md. Les skills nommés dans une autre langue, ou nommés d'après un
concept interne, atterrissent là presque à chaque fois. Cette liste est la
partie qui vaut la lecture : ce sont tes skills, et les placer à la main prend
deux minutes.

Trois façons de corriger, toutes conservées d'un build à l'autre :

- Ajouter des mots-clés à `clusters.yaml`, ou ajouter ton propre cluster.
- Épingler le rôle d'un skill dans le bloc `overrides` du même fichier.
- Écrire une phrase dans le bloc house rules en bas de ROUTING.md, recopié à
  chaque build.

Voir [customizing.md](skills/skill-tree/references/customizing.md), y compris
pour remplacer entièrement la taxonomie. Les clusters livrés décrivent un
généraliste qui écrit, code, design et fait du marketing. Si ton travail ne
ressemble pas à ça, réécrire ce seul fichier est ce qui te rapportera le plus.

## Développement

La suite de tests tourne sur la bibliothèque standard, comme le skill :

```bash
python -m unittest discover -s tests -v
```

53 tests couvrent le lecteur de frontmatter, le parser de config (y compris sa
parité avec PyYAML), le scoring, la classification, le rendu, et les deux CLI
de bout en bout, dont le fait que l'installeur ajoute et retire uniquement son
propre hook. La CI les lance sur Linux et Windows avec Python 3.8, 3.11 et
3.13, et casse le build si une dépendance externe se glisse dans le code.

## Ce que ça ne fait pas

Ça n'installe, ne met à jour et ne supprime aucun skill. Ça n'appelle aucun
modèle pour classer, donc zéro coût et zéro latence. Ça ne lit pas le corps de
tes skills, seulement le frontmatter. Et ça ne peut pas inventer une structure
que tes skills n'ont pas : quarante skills avec des descriptions vagues
donnent un arbre vague.

## Pourquoi un arbre et pas une liste

Une liste dit à l'agent ce qui existe. Elle ne dit pas quoi attraper en
premier, quelles options sont des alternatives, ni ce qui doit passer sur la
sortie avant de livrer. C'est exactement là que la sélection échoue, et l'arbre
est la plus petite structure qui répond aux trois questions.

La règle la plus forte du fichier est `always`. Les skills d'overlay, les
relecteurs et les vérificateurs, sont ceux qu'on saute quand on va vite. Ce
sont eux qui séparent un brouillon d'un truc livrable.

## Colophon

Construit avec Claude Code, qui est aussi ce qu'il route. La méthode vient
d'abord, d'une année à voir quels skills n'étaient jamais appelés.

## Licence

MIT. Voir [LICENSE](LICENSE).
