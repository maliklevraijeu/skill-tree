# lunacycle-mail

Envoi de mails depuis `contact@trylunacycle.com` (SMTP Infomaniak), sans jamais
écrire le mot de passe dans le code ni dans git.

Python 3.8+, aucune dépendance à installer.

## 1. Générer le mot de passe d'application (à faire toi-même)

Cette partie ne peut pas être automatisée : le mot de passe ne s'affiche qu'une
seule fois, dans ton navigateur.

1. `manager.infomaniak.com` → **Service Mail**
2. `trylunacycle.com` → adresse `contact@trylunacycle.com`
3. Onglet **Appareils** → **Ajouter un appareil**
4. **Sans utilisateur**, nomme-le par exemple `PC envois`
5. **Générer un mot de passe** → copie-le immédiatement
6. **Sauvegarder** en bas de page

> Le mot de passe d'application donne un accès complet en envoi **et en lecture**
> à la boîte. Il vaut un mot de passe : il ne se colle ni dans un chat, ni dans
> un ticket, ni dans un fichier versionné.

## 2. Le ranger en sécurité

```bash
cd lunacycle-mail
python3 store_secret.py
```

La saisie est masquée : le mot de passe ne passe ni par l'historique du shell,
ni par la liste des processus. Il est écrit dans `.env`, créé directement en
permissions `0600` (toi seul peux le lire) et ignoré par git.

Sur un serveur, ne crée pas de `.env` du tout : exporte plutôt la variable
d'environnement `LUNACYCLE_SMTP_PASSWORD` depuis le gestionnaire de secrets de
l'hébergeur. L'environnement est prioritaire sur le fichier.

## 3. Vérifier

```bash
python3 check.py
```

Se connecte, s'authentifie, raccroche. Aucun mail n'est envoyé et le mot de
passe n'est jamais affiché — seulement sa longueur, de quoi repérer un
copier-coller tronqué.

## 4. Envoyer

```bash
# Répétition à blanc : construit le message, ne se connecte à rien
python3 send.py --to client@example.com --subject "Test" --body "Salut" --dry-run

# Pour de vrai
python3 send.py --to client@example.com --subject "Bonjour" --body "Salut !"

# Corps depuis un fichier, plusieurs destinataires, adresse de réponse
python3 send.py --to a@x.com --to b@y.com \
                --subject "Nouveauté" --body-file message.txt \
                --reply-to malik@trylunacycle.com
```

Depuis un autre script Python :

```python
import config, check, send

cfg = config.settings()
message = send.build_message(cfg, ["client@example.com"], "Bonjour", "Salut !")
server = check.connect(cfg)
try:
    server.send_message(message)
finally:
    server.quit()
```

## Ce qui est en place côté sécurité

| Risque | Ce qui le couvre |
|---|---|
| Secret commité par accident | `.env` dans `.gitignore`, aucun secret dans le code |
| Secret lisible par un autre compte de la machine | `.env` créé en `0600`, jamais chmod après coup |
| Secret dans l'historique shell / `ps` | saisie masquée par `getpass`, jamais passé en argument |
| Secret affiché dans un log | jamais imprimé ; seule une forme tronquée l'est |
| Mot de passe principal exposé | on n'utilise qu'un mot de passe d'application, révocable seul |
| Trafic en clair | port 465 en TLS implicite ; en 587, STARTTLS **exigé**, sinon refus d'envoyer |
| Certificat non vérifié | `ssl.create_default_context()` (vérification chaîne + nom d'hôte) |

## Si ça casse

- **Authentification refusée** → mot de passe tronqué au copier-coller, ou lié à
  une autre adresse. Régénère un appareil dans Infomaniak et relance
  `store_secret.py`.
- **Connexion impossible / timeout** → port 465 bloqué par le réseau. Essaie
  `LUNACYCLE_SMTP_PORT=587 python3 check.py`.
- **Mot de passe perdu** → il ne se réaffiche jamais. Supprime l'appareil dans
  Infomaniak et recrée-en un ; l'ancien est révoqué du même coup.

## En cas de fuite

Supprime l'appareil concerné dans Infomaniak (**Appareils** → l'appareil →
supprimer). Le mot de passe est révoqué immédiatement, sans toucher au mot de
passe du compte ni aux autres appareils. Puis recrée-en un et relance
`store_secret.py`.
