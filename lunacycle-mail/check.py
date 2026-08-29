#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifie que le mot de passe fonctionne, sans envoyer le moindre mail.

    python3 check.py

Ouvre une connexion chiffree vers le SMTP Infomaniak, tente l'authentification,
puis raccroche. Le mot de passe n'est jamais affiche.
"""

import smtplib
import ssl
import sys

import config


def connect(cfg, timeout=20):
    """Retourne une connexion SMTP authentifiee, chiffree dans les deux cas.

    Port 465 : TLS implicite. Tout autre port (587) : STARTTLS obligatoire, et
    on echoue si le serveur ne le propose pas plutot que de continuer en clair.
    """
    context = ssl.create_default_context()
    if cfg["port"] == 465:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"],
                                  context=context, timeout=timeout)
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=timeout)
        server.ehlo()
        if not server.has_extn("starttls"):
            server.close()
            raise SystemExit(
                "%s:%s ne propose pas STARTTLS. Refus d'envoyer en clair."
                % (cfg["host"], cfg["port"]))
        server.starttls(context=context)
        server.ehlo()
    server.login(cfg["user"], cfg["password"])
    return server


def main():
    cfg = config.settings()
    print("Serveur      : %s:%s" % (cfg["host"], cfg["port"]))
    print("Utilisateur  : %s" % cfg["user"])
    print("Mot de passe : %s" % config.redacted(cfg["password"]))
    print("Connexion en cours…")
    try:
        server = connect(cfg)
    except smtplib.SMTPAuthenticationError as exc:
        detail = getattr(exc, "smtp_error", b"")
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace")
        print("\nECHEC de l'authentification : %s" % (detail or exc))
        print("Le mot de passe d'application est probablement mal copie, "
              "ou lie a un autre compte que %s." % cfg["user"])
        return 1
    except (smtplib.SMTPException, OSError) as exc:
        print("\nConnexion impossible : %s" % exc)
        print("Verifie le reseau, ou essaie le port 587 "
              "(LUNACYCLE_SMTP_PORT=587).")
        return 1
    server.quit()
    print("\nOK — authentification reussie. Tu peux envoyer avec send.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
