# -*- coding: utf-8 -*-
"""Configuration SMTP, lue depuis l'environnement.

Aucun secret n'est ecrit en dur dans ce fichier. Le mot de passe d'application
Infomaniak est lu depuis la variable d'environnement LUNACYCLE_SMTP_PASSWORD,
ou a defaut depuis le fichier .env du dossier (jamais versionne, chmod 600).

Ordre de priorite : environnement du shell > .env > valeur par defaut.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(HERE, ".env")

DEFAULTS = {
    "LUNACYCLE_SMTP_HOST": "mail.infomaniak.com",
    "LUNACYCLE_SMTP_PORT": "465",
    "LUNACYCLE_SMTP_USER": "contact@trylunacycle.com",
    "LUNACYCLE_FROM_NAME": "Lunacycle",
}


def load_env_file(path=ENV_FILE):
    """Lit un .env minimal (CLE=valeur) sans ecraser l'environnement reel."""
    if not os.path.isfile(path):
        return {}
    values = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Les guillemets sont tolerés parce qu'un mot de passe genere peut
            # contenir des caracteres que l'on a envie de proteger a la main.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    return values


def get(key):
    """Valeur de configuration, ou None si nulle part définie."""
    if os.environ.get(key):
        return os.environ[key]
    from_file = load_env_file().get(key)
    if from_file:
        return from_file
    return DEFAULTS.get(key)


def settings():
    """Le bloc de configuration complet, mot de passe compris.

    Leve SystemExit avec un message utile plutot qu'un KeyError si le mot de
    passe manque : c'est l'erreur qu'on fera neuf fois sur dix.
    """
    password = get("LUNACYCLE_SMTP_PASSWORD")
    if not password:
        raise SystemExit(
            "Aucun mot de passe trouve.\n"
            "Lance d'abord : python3 store_secret.py\n"
            "(ou exporte LUNACYCLE_SMTP_PASSWORD dans ton shell)")
    port = get("LUNACYCLE_SMTP_PORT")
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise SystemExit("LUNACYCLE_SMTP_PORT doit etre un nombre, recu : %r" % port)
    return {
        "host": get("LUNACYCLE_SMTP_HOST"),
        "port": port,
        "user": get("LUNACYCLE_SMTP_USER"),
        "password": password,
        "from_name": get("LUNACYCLE_FROM_NAME"),
    }


def redacted(value):
    """De quoi verifier qu'on a bien colle quelque chose, sans le divulguer."""
    if not value:
        return "(vide)"
    return "%s… (%d caracteres)" % (value[:2], len(value))
