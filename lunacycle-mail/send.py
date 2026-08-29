#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envoie un mail depuis contact@trylunacycle.com.

    python3 send.py --to client@example.com --subject "Bonjour" --body "Salut !"
    python3 send.py --to client@example.com --subject "Bonjour" --body-file message.txt
    python3 send.py --to client@example.com --subject "Test" --body "…" --dry-run

--dry-run affiche le message construit et ne se connecte a rien : de quoi
verifier un envoi avant de le rendre reel.
"""

import argparse
import email.utils
import sys
from email.message import EmailMessage

import check
import config


def build_message(cfg, to, subject, body, reply_to=None):
    message = EmailMessage()
    message["From"] = email.utils.formataddr((cfg["from_name"], cfg["user"]))
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    message["Date"] = email.utils.formatdate(localtime=True)
    # Un Message-ID sur le domaine expediteur : sans lui, certains filtres
    # anti-spam notent le message plus severement.
    message["Message-ID"] = email.utils.make_msgid(
        domain=cfg["user"].split("@")[-1])
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body)
    return message


def read_body(args):
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as handle:
            return handle.read()
    return args.body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--to", required=True, action="append",
                        help="destinataire (repetable)")
    parser.add_argument("--subject", required=True)
    body_source = parser.add_mutually_exclusive_group(required=True)
    body_source.add_argument("--body", help="corps du message")
    body_source.add_argument("--body-file", help="fichier contenant le corps")
    parser.add_argument("--reply-to", help="adresse de reponse, si differente")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche le message sans rien envoyer")
    args = parser.parse_args(argv)

    if args.dry_run:
        # settings() exigerait le mot de passe ; un dry-run doit marcher sans.
        cfg = {
            "user": config.get("LUNACYCLE_SMTP_USER"),
            "from_name": config.get("LUNACYCLE_FROM_NAME"),
            "host": config.get("LUNACYCLE_SMTP_HOST"),
            "port": config.get("LUNACYCLE_SMTP_PORT"),
        }
        message = build_message(cfg, args.to, args.subject,
                                read_body(args), args.reply_to)
        print("--- DRY RUN, rien n'est envoye ---")
        print(message)
        return 0

    cfg = config.settings()
    message = build_message(cfg, args.to, args.subject,
                            read_body(args), args.reply_to)
    server = check.connect(cfg)
    try:
        server.send_message(message)
    finally:
        server.quit()
    print("Envoye a %s" % ", ".join(args.to))
    return 0


if __name__ == "__main__":
    sys.exit(main())
