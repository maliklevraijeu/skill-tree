#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Range le mot de passe d'application Infomaniak dans .env, en securite.

    python3 store_secret.py

La saisie est masquee (getpass), donc le mot de passe ne passe ni par
l'historique du shell ni par la liste des processus. Le fichier .env est cree
en 0600 : lisible par toi seul. Il est deja ignore par git.
"""

import getpass
import os
import stat
import sys

import config


def prompt(label):
    """Saisie masquee, en exigeant un vrai terminal.

    Sans tty, getpass bascule tout seul sur une saisie en clair. On refuse :
    un mot de passe echo a l'ecran finit dans un log ou une capture.
    """
    if not sys.stdin.isatty():
        raise EOFError
    return getpass.getpass(label)


def read_existing():
    values = config.load_env_file()
    return values


def write_env(values):
    lines = ["# Genere par store_secret.py — NE JAMAIS COMMITER CE FICHIER.\n"]
    for key in sorted(values):
        lines.append("%s=%s\n" % (key, values[key]))
    # On cree le fichier deja restreint, plutot que de le chmod apres coup :
    # sinon il existe une fenetre ou il est lisible par tout le monde.
    fd = os.open(config.ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.writelines(lines)
    os.chmod(config.ENV_FILE, stat.S_IRUSR | stat.S_IWUSR)


def main():
    print("Mot de passe d'application Infomaniak pour %s"
          % config.get("LUNACYCLE_SMTP_USER"))
    print("(la saisie reste invisible, c'est normal)")
    try:
        first = prompt("Mot de passe : ")
        if not first.strip():
            raise SystemExit("Rien saisi, abandon.")
        second = prompt("Confirme     : ")
    except EOFError:
        # Pas de terminal : script lance par un agent, un cron, un pipe. Mieux
        # vaut le dire que de laisser tomber une traceback sur l'utilisateur.
        raise SystemExit(
            "\nAucun terminal interactif : impossible de saisir le mot de passe ici.\n"
            "Lance cette commande depuis un vrai terminal, ou passe par\n"
            "l'environnement :  export LUNACYCLE_SMTP_PASSWORD='…'")
    if first != second:
        raise SystemExit("Les deux saisies different, abandon. Rien n'a ete ecrit.")

    values = read_existing()
    values["LUNACYCLE_SMTP_PASSWORD"] = first
    write_env(values)

    print("\nEcrit dans %s (permissions 0600)." % config.ENV_FILE)
    print("Valeur enregistree : %s" % config.redacted(first))
    print("\nEtape suivante : python3 check.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
