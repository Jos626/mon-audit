#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conversations.py — LIRE LES TROIS SOURCES DE PAROLES DU CLIENT.

Les conversations sont la matière première la plus précieuse d'un annonceur : c'est le seul endroit
où le client dit lui-même ce qu'il veut, ce qui le bloque, et avec quels mots. Encore faut-il savoir
les lire — les trois sources ne s'exportent pas de la même façon.

  1. **WHATSAPP** — « Exporter la discussion » produit un .txt. Deux écritures existent selon le
     téléphone, et il FAUT accepter les deux :
        [09/10/2026, 14:32:05] Awa: Bonjour, c'est combien le sac ?     (iPhone et Android récents)
        09/10/2026 14:32 - Awa: Bonjour, c'est combien le sac ?         (Android plus anciens)
     Et deux pièges qui n'en sont pas : les messages SYSTÈME (« Les messages sont chiffrés de bout
     en bout », « Awa a ajouté +225… ») ne sont pas des paroles de client, et un message écrit sur
     PLUSIEURS LIGNES n'a d'horodatage que sur sa première ligne — le couper en morceaux ferait
     compter trois questions là où le client en a posé une.

  2. **MESSENGER** — « Télécharger vos informations » sur Facebook produit un dossier JSON :
     `messages/inbox/<une_conversation>/message_1.json` avec des entrées
     {sender_name, timestamp_ms, content}. On lit le JSON, jamais le HTML (qui change de forme et
     ferait échouer la lecture en silence).

  3. **LES COMMENTAIRES DE LA PAGE** — pas d'export propre. On accepte donc le copier-coller : un
     commentaire par ligne. C'est ce que le commerçant fera de toute façon, et c'est mieux qu'une
     API qu'il ne sait pas brancher.

CE QUE CE MODULE N'INVENTE JAMAIS : il ne devine pas qui est le vendeur. Il compte. Le vendeur est
celui qui écrit le plus souvent le MÊME genre de choses sur toutes les conversations — méthode
fragile — sauf quand le commerçant le dit (`vendeur="Ma boutique"`). Tant que ce n'est pas établi,
les statistiques qui dépendent du rôle (temps de réponse, messages restés sans réponse) sont
MARQUÉES comme non établies au lieu d'être données fausses.
"""
import json
import os
import re
from datetime import datetime

# Les lignes de journal, pas des paroles de client. Les compter fausserait tout : ils sont souvent
# nombreux et parlent de chiffrement, pas de sacs.
SYSTEME = ("les messages et les appels sont chiffrés", "messages sont chiffrés de bout en bout",
           "a ajouté", "a créé le groupe", "a changé", "a modifié", "vous avez bloqué",
           "chiffrement", "a quitté", "a été ajouté", "<média omis>", "image omise",
           "appel manqué", "appel vocal", "appel vidéo", "ce message a été supprimé",
           "vous avez réagi", "a réagi")

# Les formats d'horodatage réellement produits par WhatsApp.
FORMATS_WHATSAPP = (
    re.compile(r"^\[(\d{2}/\d{2}/\d{2,4}),? (\d{2}:\d{2}(?::\d{2})?)\]\s*([^:]{1,40}):\s?(.*)$"),
    re.compile(r"^\[(\d{1,2}/\d{1,2}/\d{2,4}) (\d{1,2}:\d{2}(?::\d{2})?) [AP]M\]\s*([^:]{1,40}):\s?(.*)$"),
    re.compile(r"^(\d{2}/\d{2}/\d{2,4})[ ,]+(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:[AP]M)?\s*[-–]\s*([^:]{1,40}):\s?(.*)$"),
)


def _est_systeme(texte):
    t = texte.lower()
    return any(m in t for m in SYSTEME)


def _date_iso(jour, heure):
    for format_jour in ("%d/%m/%Y", "%d/%m/%y"):
        for format_heure in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(f"{jour} {heure}", f"{format_jour} {format_heure}")
            except ValueError:
                continue
    return None


def lire_whatsapp(chemin, source="whatsapp"):
    """Un export .txt de WhatsApp -> une liste de messages (auteur, quand, texte)."""
    with open(chemin, encoding="utf-8", errors="replace") as f:
        brut = f.read().splitlines()
    messages, courant = [], None
    for ligne in brut:
        trouve = None
        for motif in FORMATS_WHATSAPP:
            trouve = motif.match(ligne.strip())
            if trouve:
                break
        if trouve:
            if courant:
                messages.append(courant)
            jour, heure, auteur, texte = trouve.groups()
            courant = {"source": source, "auteur": auteur.strip(), "quand": _date_iso(jour, heure),
                       "texte": texte.strip()}
        elif courant is not None:
            # suite d'un message sur plusieurs lignes : on RALLONGE le message, on n'en crée pas un autre
            courant["texte"] += " " + ligne.strip()
    if courant:
        messages.append(courant)
    return [m for m in messages if m["texte"] and not _est_systeme(m["texte"])]


def lire_messenger(chemin):
    """Le dossier JSON de Facebook (« Télécharger vos informations ») -> les messages reçus."""
    if os.path.isdir(chemin):
        fichiers = []
        for racine, _d, noms in os.walk(chemin):
            fichiers += [os.path.join(racine, n) for n in noms if n.endswith(".json")]
    else:
        fichiers = [chemin]
    messages = []
    for fichier in fichiers:
        try:
            with open(fichier, encoding="utf-8", errors="replace") as f:
                donnees = json.load(f)
        except Exception:
            continue
        for m in donnees.get("messages", []) if isinstance(donnees, dict) else []:
            texte = (m.get("content") or "").strip()
            if not texte:
                continue
            quand = None
            if m.get("timestamp_ms"):
                try:
                    quand = datetime.fromtimestamp(m["timestamp_ms"] / 1000)
                except (ValueError, OSError, OverflowError):
                    quand = None
            auteur = m.get("sender_name") or "?"
            messages.append({"source": "messenger", "auteur": auteur, "quand": quand,
                             "texte": texte})
    return [m for m in messages if not _est_systeme(m["texte"])]


def lire_commentaires(texte_ou_chemin, source="commentaires"):
    """Les commentaires de la page : un par ligne, copiés-collés depuis Facebook."""
    if os.path.exists(texte_ou_chemin):
        with open(texte_ou_chemin, encoding="utf-8", errors="replace") as f:
            brut = f.read()
    else:
        brut = texte_ou_chemin
    messages = []
    for ligne in brut.splitlines():
        t = ligne.strip()
        if len(t) < 4:
            continue
        messages.append({"source": source, "auteur": "?", "quand": None, "texte": t})
    return [m for m in messages if not _est_systeme(m["texte"])]


def lire(sources, vendeur=None):
    """Toutes les sources d'un coup.

    `sources` : liste de chemins ou de textes. Le type est déduit de ce qui est fourni :
      · un dossier ou un .json  -> Messenger
      · un .txt                 -> WhatsApp
      · tout le reste           -> des commentaires collés
    """
    messages = []
    for source in sources:
        if isinstance(source, str) and (os.path.isdir(source)
                                        or (os.path.exists(source) and source.endswith(".json"))):
            messages += lire_messenger(source)
        elif isinstance(source, str) and os.path.exists(source) and source.endswith((".txt", ".text")):
            # ⛔ LE CONTENU DÉCIDE, PAS L'EXTENSION (corrigé le 09/10/2026). Les commentaires de page
            # arrivent aussi en .txt : routés par l'extension, ils étaient confiés au lecteur WhatsApp,
            # qui n'y trouvait aucune date — et rendait ZÉRO message en silence. Un fichier qui
            # disparaît sans erreur est le pire des défauts : on croit avoir tout lu.
            lu = lire_whatsapp(source)
            if lu:
                messages += lu
            else:
                messages += lire_commentaires(source)
        else:
            messages += lire_commentaires(source)

    # ENLEVER LES DOUBLONS : le même exporté deux fois (WhatsApp + Messenger) ne doit pas compter
    # deux fois dans les statistiques — sinon une objection paraîtrait deux fois plus fréquente.
    vus, propres = set(), []
    for m in messages:
        cle = (m["auteur"], m["texte"][:180])
        if cle in vus:
            continue
        vus.add(cle)
        propres.append(m)

    vendeurs = _deviner_vendeur(propres, vendeur)
    return {"messages": propres, "vendeur": vendeurs, "nb": len(propres),
            "sources": sorted({m["source"] for m in propres})}


def _deviner_vendeur(messages, vendeur=None):
    """Qui est le vendeur dans ces conversations ?

    Si le commerçant le donne, on le prend. Sinon on cherche l'auteur qui écrit dans PLUSIEURS
    conversations avec des tournures de vendeur — et si le doute persiste, on rend None plutôt
    qu'un nom faux : toutes les mesures qui dépendent du rôle seront marquées « non établies ».
    """
    if vendeur:
        return vendeur
    from collections import Counter
    if not messages:
        return None
    auteurs = Counter(m["auteur"] for m in messages if m["auteur"] not in ("?", None))
    if not auteurs:
        return None
    # un vendeur écrit beaucoup, et les mêmes formules : on prend le plus bavard s'il domine largement
    classement = auteurs.most_common(2)
    if len(classement) == 1:
        return classement[0][0] if classement[0][1] >= 3 else None
    (nom1, n1), (_nom2, n2) = classement
    return nom1 if n1 >= 3 * n2 else None
