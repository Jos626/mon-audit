# Perform

Un outil qui dit à un commerçant **pourquoi sa publicité Facebook ne lui rapporte pas de commandes**,
et ce qu'il faut changer.

## Les deux rapports

1. **L'audit du compte publicitaire** — où part l'argent, quelles annonces ne rapportent rien, quelles
   annonces fonctionnent (et qu'il ne faut pas toucher), et si les ventes sont seulement mesurées.
2. **Le portrait du client** — bâti sur ses propres paroles (WhatsApp, Messenger, commentaires de la
   page) : ce qu'il demande, ce qui le bloque, ses mots exacts, ses villes, ses horaires.

## Ce que l'outil refuse de faire, et qui est écrit dans le code

- **Aucun mot de passe** n'est jamais demandé. L'accès passe par une autorisation révocable (Facebook
  Login) ou par un export de fichiers. Le code QR de WhatsApp Web est refusé pour la même raison.
- **Aucun chiffre inventé** : sous 30 résultats, aucun visuel n'est déclaré gagnant ; sous 30 messages,
  aucun portrait n'est dressé ; sans la marge du client, l'outil ne dit pas qu'il perd de l'argent.
- **Le jeton d'accès n'est pas conservé** après l'audit.

## Fichiers

| Fichier | Rôle |
|---|---|
| `serveur.py` | la page « Continuer avec Facebook », le retour d'autorisation, les pages exigées par Meta |
| `bot-audit.py` | le bot Telegram : le client envoie ses fichiers, il reçoit ses rapports |
| `connexion.py` | la lecture du compte publicitaire par jeton (jamais par mot de passe) |
| `whatsapp.py` | la Cloud API officielle : réception, vérification, envoi |
| `lecture.py` / `audit.py` / `rapport.py` | lire un export d'Ads Manager, l'auditer, l'écrire |
| `conversations.py` / `portrait.py` | lire les paroles du client, en tirer le portrait |
| `tests-*.py` | les gardes : 77 contrôles au total |

## Lancer

    python3 serveur.py      # l'écran de connexion (3 réglages à fournir en variables d'environnement)
    python3 bot-audit.py    # le bot Telegram
    python3 audit-complet.py --fichier export.csv --whatsapp discussion.txt
