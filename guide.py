#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""guide.py — CE QU'ON DEMANDE AU COMMERÇANT, GESTE PAR GESTE.

Un audit ne vaut que par ce qu'on arrive à récupérer. Or chaque source a SA façon de sortir ses
données, et le commerçant ne les connaît pas : lui donner un mode d'emploi à cinq étapes d'un coup,
c'est le perdre à la troisième. Le texte ci-dessous suit donc la règle qu'il faut : **un geste par
bloc, avec le MOT EXACT à toucher**, et ce qu'il va voir ensuite.

TROIS SOURCES, TROIS LOGIQUES — c'est aussi la réponse à « et pour WhatsApp ? » :

  · **FACEBOOK** (publicités, pages, commentaires, audience) → un JETON accordé par le client dans
    l'outil de Meta. Le plus rapide, et il remonte en direct (les chiffres du jour).
  · **WHATSAPP** → un EXPORT de discussion (.txt). WhatsApp n'a pas de jeton à donner : le seul
    mécanisme honnête qui existe aujourd'hui pour lire un historique est l'export — et pour un AUDIT,
    c'est même le meilleur, parce qu'il contient les mois passés, ce qu'une connexion en direct ne
    peut pas donner (elle ne voit que ce qui arrive après le branchement).
  · **MESSENGER** → le dossier JSON de « Télécharger vos informations ». Facebook ne l'expose pas par
    jeton, et l'export a le même avantage : tout l'historique.

⚠️ CE QUI N'EST PAS PROPOSÉ, ET QUI NE LE SERA PAS : le lien par CODE QR de WhatsApp Web, ou un mot
de passe WhatsApp. Prendre la session de quelqu'un, c'est prendre son compte — c'est exactement la
mécanique des vols de compte par message, et un outil d'audit qui l'utiliserait détruirait la
confiance avant d'avoir servi à quoi que ce soit. Voir l'en-tête de `connexion.py`.
"""

# --------------------------------------------------------------------------- Facebook : le jeton
FACEBOOK = """*FACEBOOK — 5 gestes*

1. Ouvre : `developers.facebook.com/tools/explorer`
   _(c'est l'outil de Meta lui-même — ton mot de passe ne sort jamais de chez Facebook)_

2. Connecte-toi, puis dans la colonne de droite, ajoute ces cinq droits :
   `ads_read` · `business_management` · `pages_show_list` · `pages_read_engagement` · `read_insights`

3. Clique **Generate Access Token** (bouton bleu, en haut).

4. Facebook te demande de confirmer : accepte.

5. Copie le long texte qui apparaît dans la case, et colle-le ici.

Tu verras à l'écran : _un jeton valable environ 1 heure_. C'est normal — on s'en sert pour l'audit du
jour. Tu peux le révoquer quand tu veux : réglages → Applications et sites web → Supprimer.
"""

# --------------------------------------------------------------------------- WhatsApp : l'export
WHATSAPP = """*WHATSAPP — 4 gestes, par discussion*

1. Ouvre WhatsApp, puis ouvre la discussion avec un client.

2. Touche les **trois points** en haut à droite (⋮).

3. Touche **Plus**, puis **Exporter la discussion**.

4. Choisis **Sans média** — puis envoie le fichier ici (partage → Telegram).

Tu verras à l'écran : un fichier qui finit par `.txt`.

👉 Fais-le pour les discussions où **tu as vendu**, et pour celles où **le client a disparu** : les
deux ensemble, c'est ce qui montre où ça casse. Une dizaine suffit pour commencer.
"""

# --------------------------------------------------------------------------- Messenger : le dossier
MESSENGER = """*MESSENGER — 5 gestes*

1. Sur Facebook : **Paramètres et confidentialité** → **Paramètres**.

2. Onglet **Tes informations Facebook** → **Télécharger tes informations**.

3. Choisis : **Messages** · **format JSON** · **qualité moyenne**.

4. Lance la création. _(Facebook prépare le dossier ; tu reçois un message quand c'est prêt, souvent
   en quelques minutes.)_

5. Télécharge le dossier, puis envoie-moi le fichier `message_1.json` de la conversation qui
   t'intéresse — il est dans `messages/inbox/`.

Tu verras dans le dossier : des sous-dossiers par personne. Un seul suffit pour commencer.
"""

# --------------------------------------------------------------------------- Commentaires + commandes
COMMENTAIRES = """*LES COMMENTAIRES DE TA PAGE — 2 gestes*

1. Ouvre une de tes publications, et descends jusqu'aux commentaires.

2. Copie-les et colle-les ici : **un commentaire par ligne**.

_(Pas besoin d'être propre : je trie. C'est la source où les gens disent le plus franchement ce qui
les bloque — souvent plus que dans les messages privés.)_
"""

COMMANDES = """*TES VENTES — 1 geste*

Un simple tableau, une ligne par commande, avec ce que tu as : `nom, ville, produit, montant, date`.

Si tu n'as pas de fichier : ouvre une note et écris tes 20 dernières ventes à la main, une par ligne.
Vingt vraies ventes valent mieux que deux cents lignes inventées — et si tu n'en as que cinq, donne
les cinq : je te dirai ce qu'on peut en tirer, et ce qu'on ne peut pas.
"""

TOUT = (FACEBOOK, WHATSAPP, MESSENGER, COMMENTAIRES, COMMANDES)


def tout():
    """Les cinq sources d'un seul tenant, séparées — pour un premier message au client."""
    return "\n\n━━━━━━━━━━━━━━━━━━━\n\n".join(TOUT)


def resume():
    """Ce qu'on peut déjà faire avec ce qu'il a, et ce que ça change."""
    return (
        "🎯 *CE QUE JE PEUX FAIRE, SELON CE QUE TU M'ENVOIES*\n\n"
        "· **Le jeton Facebook seul** → l'audit du compte publicitaire : où part l'argent, pourquoi "
        "ça ne convertit pas, ce qui marche et qu'il ne faut pas toucher.\n"
        "· **+ l'export WhatsApp (et Messenger)** → le portrait du client : ce qu'il demande, ce qui "
        "le bloque, ses mots exacts, ses villes, ses horaires, et les clients jamais rappelés.\n"
        "· **+ tes ventes** → les chiffres qui tranchent : le coût par commande face à ta marge, et "
        "la liste de tes acheteurs à donner à Meta pour qu'il cherche des gens comme eux.\n\n"
        "⚠️ *Ce qui n'est pas dans ces sources ne sera pas inventé.* Pas d'âge, pas de revenu, pas "
        "d'intention : ce qui manque se dit comme manquant.")


if __name__ == "__main__":
    print(resume())
    print("\n")
    print(tout())
