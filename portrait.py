#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""portrait.py — LE PORTRAIT ROBOT DU CLIENT, BÂTI SUR SES PROPRES PAROLES.

CE QUE CE MODULE FAIT, ET CE QU'IL REFUSE DE FAIRE.

Il compte. Sur Messenger, WhatsApp et les commentaires de la page, il compte :
  · ce que les clients demandent le plus souvent (et dans quel ordre) ;
  · ce qui les bloque, avec leurs phrases exactes ;
  · les mots qu'ils emploient EUX (pour que l'annonce parle leur langue) ;
  · les villes qu'ils citent (donc la carte de livraison, et la zone à cibler) ;
  · les heures où ils écrivent (donc quand diffuser) ;
  · et combien de clients ont écrit sans jamais recevoir de réponse.

Il refuse de faire : inventer un âge, un revenu, une « personnalité ». Ces choses-là ne se lisent pas
dans un fil de discussion, et un portrait inventé produit des annonces inventées — c'est exactement
l'erreur que José ne veut plus voir (« hier il m'a servi un match qui n'existe pas »). Tout ce qui
sort d'ici est adossé à un nombre de conversations, et le nombre est écrit à côté.

LA RÈGLE DE VOLUME, la même que pour la mesure des paris : sous ~30 messages de clients, il n'y a pas
de portrait — il y a des impressions. L'outil le dit au lieu de décrire un client qui n'existe pas.

DERNIÈRE CHOSE, ET C'EST LA PLUS IMPORTANTE POUR LE CIBLAGE. L'ultra-ciblage par centres d'intérêt
n'existe plus chez Meta : les exclusions de ciblage détaillé ont été retirées (juillet 2024), puis les
centres d'intérêt regroupés et supprimés (juin 2025, arrêt de diffusion en janvier 2026 pour ceux qui
les utilisent encore). La précision qui RESTE vient de deux endroits, et ce module les sert tous les
deux : **tes propres données** (les acheteurs réels → audience personnalisée → audience similaire) et
**ton message**. Le portrait sert à écrire le second, et le fichier clients sert le premier.
"""
import re
from collections import Counter
from datetime import datetime, timedelta

# --------------------------------------------------------------------------- ce qu'ils demandent
# Les thèmes sont cherchés par mots-clés, en français d'usage — y compris les tournures ivoiriennes.
# Chaque mot-clé est court : « livr » attrape livrer, livraison, livré, et « envoie ».
THEMES = {
    "le prix":            ["combien", "le prix", "c'est à combien", "tarif", "ça fait combien",
                           "cout", "coût"],
    "la livraison":       ["livr", "envoie", "envoi", "expédi", "tu es où", "c'est où", "je suis à",
                           "dans quel quartier", "la livraison est gratuite"],
    "le délai":           ["quand est-ce que", "dans combien de temps", "ça arrive quand",
                           "arrive quand", "délai", "aujourd'hui", "demain"],
    "la disponibilité":   ["dispo", "en stock", "il reste", "tu as encore", "rupture", "tu en as"],
    "la taille":          ["taille", "pointure", "mesure", "longueur", "largeur", "combien de litres",
                           "dimension"],
    "la qualité":         ["qualité", "du vrai", "original", "solide", "ça tient", "cuir véritable",
                           "c'est du bon"],
    "le paiement":        ["wave", "orange money", "mtn", "moov", "paiement", "payement", "espèces",
                           "à la livraison", "cash", "mobile money"],
    "la confiance":       ["arnaque", "c'est sûr", "sérieux", "escroc", "confiance", "garantie",
                           "tu es à qui"],
    "le crédit":          ["à crédit", "je paie après", "deux tranches", "arrangement", "à tempérament"],
    # ⛔ « cadeau » est RETIRÉ de ce thème (09/10/2026) : « je cherche un cadeau » n'est pas une
    # demande de remise — c'est un motif d'achat. Le mot faisait remonter une demande de prix comme
    # une négociation, et une remontée fausse fait écrire une annonce à côté du sujet.
    "le dernier prix":    ["dernier prix", "tu réduis", "réduction", "moins cher", "rabais",
                           "fais un effort"],
    "les photos":         ["photo", "vidéo", "envoie la photo", "la vraie", "en vrai"],
    "le retour":          ["retour", "échange", "rembourse", "si ça ne va pas", "satisfait"],
}

# Ce qui BLOQUE, et qui n'est pas une question : une objection. Elle se traite dans l'annonce, avant
# que le client écrive — c'est tout l'intérêt.
OBJECTIONS = {
    "c'est trop cher":        ["trop cher", "c'est cher", "pas les moyens", "je n'ai pas assez",
                               "ça dépasse mon budget"],
    "je vais réfléchir":      ["je vais réfléchir", "je vais voir", "je te rappelle", "je reviens",
                               "laisse-moi voir", "je vais me renseigner"],
    "pas maintenant":         ["pas maintenant", "plus tard", "le mois prochain", "l'année prochaine",
                               "quand j'aurai"],
    "j'ai trouvé moins cher": ["moins cher ailleurs", "j'ai trouvé à", "quelqu'un d'autre le fait à"],
    "peur de l'arnaque":      ["arnaque", "escroc", "c'est du faux", "ça me fait peur", "on m'a déjà"],
    "je ne te connais pas":   ["je ne te connais pas", "c'est la première fois", "qui es-tu",
                               "tu es où"],
    "je ne peux pas payer":   ["je n'ai pas wave", "je n'ai pas orange money", "je peux payer à",
                               "je paierai à la livraison"],
}

# Les lieux : liste ivoirienne, à enrichir selon le pays du commerçant. Sert à la carte de livraison
# ET à la zone de diffusion — deux usages qui valent de l'argent.
LIEUX = ["Abidjan", "Yopougon", "Cocody", "Marcory", "Treichville", "Adjamé", "Plateau", "Abobo",
         "Koumassi", "Port-Bouët", "Bingerville", "Anyama", "Grand-Bassam", "Yamoussoukro", "Bouaké",
         "Daloa", "San-Pédro", "Korhogo", "Divo", "Abengourou", "Man", "Gagnoa", "Soubré",
         "Bondoukou", "Séguéla", "Odienné", "Agboville", "Dabou", "Tiassalé", "Aboisso"]

MOTS_VIDES = set("""le la les un une des de du d l à au aux et ou mais donc or ni car que qui quoi dont
où quand comment pourquoi je tu il elle on nous vous ils elles me te se ce cet cette ces mon ma mes
ton ta tes son sa ses notre nos votre vos leur leurs est sont était étaient être avoir ai as a avons
avez ont avais avait pour par avec sans sur sous dans en vers chez y ne pas plus moins très bien bon
joursoir salut bonjour bonsoir svp stp svp merci ok d'accord oui non ça cela ceci moi toi lui
aujourd'hui demain hier matin soir nuit svp plaît vite fait faire fais faites si aussi encore déjà
tout tous toute toutes même autre autres peu beaucoup trop assez c'est c'est-ce qu'est
voudrais veux voudrai aimerais""".split())

SEUIL_PORTRAIT = 30          # messages de clients : sous ce seuil, on ne décrit pas un client


def _client_messages(conversations):
    """Ne garder QUE les paroles des clients — les mots du vendeur ne décrivent pas le client."""
    vendeur = conversations.get("vendeur")
    return [m for m in conversations["messages"] if not vendeur or m["auteur"] != vendeur]


def _compte_themes(messages):
    """Pour chaque thème : combien de messages le portent, et des exemples réels."""
    resultat = {}
    for theme, mots in THEMES.items():
        touches = [m for m in messages if any(mot in m["texte"].lower() for mot in mots)]
        if touches:
            resultat[theme] = {"nombre": len(touches),
                               "part": len(touches) / len(messages) if messages else 0,
                               "exemples": [m["texte"][:120] for m in touches[:3]]}
    return dict(sorted(resultat.items(), key=lambda kv: -kv[1]["nombre"]))


def _compte_objections(messages):
    resultat = {}
    for objection, mots in OBJECTIONS.items():
        touches = [m for m in messages if any(mot in m["texte"].lower() for mot in mots)]
        if touches:
            resultat[objection] = {"nombre": len(touches),
                                  "citations": [m["texte"][:110] for m in touches[:2]]}
    return dict(sorted(resultat.items(), key=lambda kv: -kv[1]["nombre"]))


def _vocabulaire(messages, combien=14):
    """LES MOTS DU CLIENT — c'est ce vocabulaire qui doit passer dans l'annonce.

    On compte les mots de toutes ses phrases (pas seulement des questions), en écartant les mots
    vides : « sac », « cuir », « livraison », « Yopougon » sortent ; « le », « je », « est » non.
    """
    compteur = Counter()
    for m in messages:
        for mot in re.findall(r"[a-zà-ÿ']{4,}", m["texte"].lower()):
            if mot not in MOTS_VIDES:
                compteur[mot] += 1
    return compteur.most_common(combien)


def _lieux(messages):
    compteur = Counter()
    for m in messages:
        t = m["texte"]
        for lieu in LIEUX:
            if re.search(r"\b" + re.escape(lieu) + r"\b", t, re.IGNORECASE):
                compteur[lieu.capitalize()] += 1
    return compteur.most_common(12)


def _heures(messages):
    """QUAND ils écrivent : la seule donnée de ciblage encore vraiment précise chez Meta."""
    par_heure = Counter()
    jours = Counter()
    for m in messages:
        if isinstance(m.get("quand"), datetime):
            par_heure[m["quand"].hour] += 1
            jours[m["quand"].strftime("%A")] += 1
    return par_heure, jours


def _sans_reponse(conversations, fenetre_heures=4):
    """Les clients qui ont écrit et n'ont JAMAIS eu de réponse.

    ⚠️ Ce calcul exige de savoir qui est le vendeur. Sans cette information, on ne rend RIEN plutôt
    qu'un chiffre faux : annoncer « 40 clients ignorés » à tort ferait perdre la confiance dans tout
    le reste du rapport.
    """
    vendeur = conversations.get("vendeur")
    if not vendeur:
        return None
    messages = [m for m in conversations["messages"] if isinstance(m.get("quand"), datetime)]
    messages.sort(key=lambda m: m["quand"])
    # ⚠️ ON NE COMPTE QUE LA DERNIÈRE PHRASE DE CHAQUE RAFALE DU CLIENT. Un client qui écrit trois
    # fois de suite (« il est dispo ? » / « en noir ? » / « c'est combien ? ») poserait sinon trois
    # « messages sans réponse » alors qu'il n'a jamais eu de réponse à AUCUN — un seul client ignoré,
    # pas trois. Sans ce tri, le chiffre devient alarmiste, et un chiffre alarmiste se fait
    # désavouer à la première vérification… ce qui emporte tout le reste du rapport avec lui.
    orphelins = []
    for i, m in enumerate(messages):
        if m["auteur"] == vendeur:
            continue
        suivant = messages[i + 1] if i + 1 < len(messages) else None
        if suivant is not None and suivant["auteur"] != vendeur:
            continue                      # ce n'est pas la fin de sa rafale
        limite = m["quand"] + timedelta(hours=fenetre_heures)
        repondu = any(n["auteur"] == vendeur and m["quand"] <= n["quand"] <= limite
                      for n in messages[i + 1:])
        if not repondu:
            orphelins.append(m)
    return {"nombre": len(orphelins),
            "part": len(orphelins) / len(messages) if messages else 0,
            "exemples": [m["texte"][:100] for m in orphelins[:3]]}


def etudier(conversations, fichier_clients=None):
    """Le portrait complet, avec son nombre de cas partout."""
    clients = _client_messages(conversations)
    if not clients:
        return {"assez": False, "nb_clients": 0,
                "raison": "Aucun message de client n'a été trouvé dans ce que tu m'as donné."}

    resultat = {
        "assez": len(clients) >= SEUIL_PORTRAIT,
        "nb_clients": len(clients),
        "nb_total": conversations["nb"],
        "sources": conversations["sources"],
        "vendeur": conversations.get("vendeur"),
        "themes": _compte_themes(clients),
        "objections": _compte_objections(clients),
        "vocabulaire": _vocabulaire(clients),
    }
    resultat["lieux"] = _lieux(clients)
    heures, jours = _heures(clients)
    resultat["heures"] = heures.most_common()
    resultat["jours"] = jours.most_common()
    resultat["sans_reponse"] = _sans_reponse(conversations)
    resultat["clients_fichier"] = _lire_clients(fichier_clients) if fichier_clients else None
    return resultat


def _lire_clients(chemin):
    """Le fichier des clients réels (une ligne par commande) : c'est LUI qui donne la précision.

    Colonnes attendues, dans n'importe quel ordre : nom, ville, produit, montant, date, téléphone.
    On accepte aussi un simple export de commandes : ce qui compte, c'est qu'il y ait des ACHETEURS
    et des montants — c'est avec ça qu'on bâtit une audience similaire qui vaut quelque chose.
    """
    import csv
    if not chemin or not str(chemin).endswith((".csv", ".txt")):
        return None
    clients = []
    with open(chemin, encoding="utf-8-sig", errors="replace") as f:
        for ligne in csv.DictReader(f):
            propre = {str(k).strip().lower(): (v or "").strip() for k, v in ligne.items()}
            clients.append(propre)
    villes = Counter(c.get("ville", "") for c in clients if c.get("ville"))
    return {"nombre": len(clients), "villes": villes.most_common(8),
            "colonnes": sorted(clients[0].keys()) if clients else []}
