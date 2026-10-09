#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lecture.py — Lire un export d'Ads Manager TEL QU'IL SORT, sans rien lui demander.

POURQUOI CE FICHIER EXISTE, ET POURQUOI IL EST SI PRUDENT.

Un outil d'audit vit ou meurt sur une chose : **est-ce qu'il lit correctement ce que le commerçant
lui donne ?** Si la lecture se trompe d'une colonne, l'audit accuse le mauvais levier, le client
coupe une campagne qui marchait, et il ne revient jamais. C'est le pire résultat possible — pire
que pas d'outil du tout.

Or les exports d'Ads Manager sont un vrai champ de mines :

  · Les EN-TÊTES CHANGENT de langue selon le compte (« Montant dépensé » / « Amount spent ») et de
    version (« Clics » / « Clics (tous) »). On ne cherche donc pas un nom exact : on cherche par
    MOTS-CLÉS, en français ET en anglais, et on note ce qu'on n'a pas trouvé.
  · Les NOMBRES sont écrits à la française (« 1 234,56 F CFA ») ou à l'anglaise (« 1,234.56 »).
    Le piège coûteux : Meta insère des ESPACES INSÉCABLES (U+00A0 / U+202F) dans les milliers. Un
    parseur naïf qui ne retire que l'espace normale lit « 12 500 » comme... rien, ou comme 12.
    Un budget de 12 500 F lu comme 12 F, c'est un audit qui dit « tu dépenses trop peu ».
  · Le SÉPARATEUR peut être la virgule ou le point-virgule (selon la version d'Excel).
  · L'ENCODAGE peut être UTF-8, UTF-8 avec BOM, ou UTF-16 (export ouvert dans Excel avant d'être
    envoyé). Un fichier mal décodé fait disparaître les accents — « Fréquence » devient illisible.

RÈGLE DE CONDUITE DE CE MODULE : il ne devine jamais. Quand une colonne manque, il le DIT
(`colonnes_absentes`) au lieu de laisser un zéro passer pour une vraie valeur — parce qu'un zéro
inventé accusera un pixel cassé qui marche très bien.
"""
import csv
import io
import os
import re
import unicodedata

# --------------------------------------------------------------------------- en-têtes
# Chaque grandeur est cherchée par mots-clés, en français et en anglais. L'ORDRE COMPTE : le premier
# mot-clé trouvé gagne. On met devant les libellés les plus précis, sinon « clics » attraperait
# « clics sur le lien » puis « CTR ».
COLONNES = {
    "campagne":        ["nom de la campagne", "campaign name", "campagne"],
    "ensemble":        ["nom de l'ensemble", "ad set name", "ensemble de publicités", "ensemble"],
    "pub":             ["nom de la publicité", "nom de l'annonce", "ad name", "publicité", "annonce"],
    "objectif":        ["objectif de la campagne", "campaign objective", "objectif"],
    "type_resultat":   ["type de résultat", "result type", "type de resultat"],
    "depense":         ["montant dépensé", "amount spent", "dépenses", "depenses", "coût total"],
    "impressions":     ["impressions"],
    "portee":          ["portée", "reach"],
    "frequence":       ["fréquence", "frequence", "frequency"],
    "clics":           ["clics (tous)", "clicks (all)", "clics sur le lien", "link clicks", "clics"],
    "ctr":             ["ctr (tous)", "ctr (all)", "ctr"],
    "cpm":             ["cpm"],
    "cpc":             ["cpc"],
    "resultats":       ["résultats", "resultats", "results"],
    "cout_resultat":   ["coût par résultat", "cost per result", "cout par resultat"],
    "achats":          ["achats", "purchases"],
    "valeur_achats":   ["valeur d'achat", "valeur des achats", "purchase value", "valeur de conversion"],
    "roas":            ["roas des achats", "purchase roas", "roas"],
    "statut":          ["état de la diffusion", "statut de la diffusion", "ad delivery",
                        "état", "statut", "delivery"],
    "date_debut":      ["début", "debut", "start"],
    "date_fin":        ["fin", "end"],
}

# Les colonnes sans lesquelles l'audit ne peut PAS conclure. On les réclame explicitement au client
# plutôt que de rendre un rapport bâti sur du vide.
INDISPENSABLES = ["depense", "impressions", "resultats"]
SOUHAITEES = ["objectif", "type_resultat", "achats", "frequence", "clics"]

_ESPACES = ("\u00a0", "\u202f", "\u2009", "\u2007", " ")   # espaces insécables et fines


def argent(valeur, decimales=0):
    """Un montant écrit à la française : « 100 000 F » et jamais « 100,000 F ».

    ⚠️ Ce détail n'en est pas un : un document qui écrit « 100,000 F CFA » a l'air traduit par une
    machine, et un client qui doute de la langue doute des chiffres.
    """
    if valeur is None:
        return "—"
    return f"{valeur:,.{decimales}f}".replace(",", "\u202f").replace(".", ",")


def fr_nombre(valeur, decimales=0):
    """Un nombre à la française, décimale comprise : 4.2 -> « 4,2 »."""
    if valeur is None:
        return "—"
    return f"{valeur:.{decimales}f}".replace(".", ",")


def pourcent(part, decimales=0):
    """Une part écrite comme un commerçant la lit : « 64 % » (avec l'espace, comme en français)."""
    if part is None:
        return "—"
    return f"{part * 100:.{decimales}f}".replace(".", ",") + "\u00a0%"


def _sans_accent(texte):
    """« Fréquence » -> « frequence ». Les en-têtes exportés varient aussi par les accents."""
    t = unicodedata.normalize("NFKD", str(texte or ""))
    return "".join(c for c in t if not unicodedata.combining(c)).lower().strip()


def nombre(valeur):
    """Un nombre écrit par un humain, ou par Ads Manager, lu QUEL QUE SOIT le format.

    Renvoie TOUJOURS un float, et 0.0 seulement quand la case est vraiment vide : une case vide et
    une case à zéro ne veulent pas dire la même chose dans un audit (voir `_vide` plus bas).

    Le cas qui coûte cher si on le rate : « 12 500,00 F CFA » avec un ESPACE INSÉCABLE. Sans le
    retirer, int(float('12 500.00')) échoue et on lit 0 — un compte de 12 500 F d'achats passerait
    pour un compte qui ne dépense rien.
    """
    if valeur is None:
        return 0.0
    if isinstance(valeur, (int, float)):
        return float(valeur)
    t = str(valeur).strip()
    if not t or t in {"-", "—", "N/A", "n/a", "ND", "nd", "n.d."}:
        return 0.0
    for e in _ESPACES:
        t = t.replace(e, "")
    t = t.replace("%", "").replace("FCFA", "").replace("FCFA", "")
    t = re.sub(r"[^\d,.\-]", "", t)          # retire les symboles monétaires et les lettres
    if not t:
        return 0.0
    if "," in t and "." in t:
        # les deux présents : celui qui est le PLUS À DROITE est le séparateur décimal
        if t.rfind(",") > t.rfind("."):
            t = t.replace(".", "").replace(",", ".")
        else:
            t = t.replace(",", "")
    elif "," in t:
        # virgule seule : décimale si elle est suivie d'un ou deux chiffres, sinon séparateur de milliers
        t = t.replace(",", ".") if len(t.split(",")[-1]) in (1, 2) else t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return 0.0


def _vide(valeur):
    """La case est-elle VRAIMENT vide (et non un zéro) ? La distinction porte tout l'audit :
    « achats = 0 » et « colonne achats absente » ne se soignent pas pareil."""
    if valeur is None:
        return True
    return str(valeur).strip() in {"", "-", "—", "N/A", "n/a", "ND", "nd", "n.d."}


def _ouvrir(chemin):
    """Lit le fichier en essayant les encodages qu'on rencontre vraiment, dans l'ordre."""
    with open(chemin, "rb") as f:
        brut = f.read()
    if chemin.lower().endswith((".xlsx", ".xlsm")):
        import openpyxl                                    # installation déjà présente sur le poste
        classeur = openpyxl.load_workbook(io.BytesIO(brut), data_only=True)
        feuille = classeur.active
        lignes = [[("" if c is None else c) for c in ligne]
                  for ligne in feuille.iter_rows(values_only=True)]
        return [[str(c) for c in ligne] for ligne in lignes]

    for encodage in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            texte = brut.decode(encodage)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        texte = brut.decode("utf-8", "replace")

    # le séparateur : on essaie les deux et on garde celui qui donne le plus de colonnes
    meilleur, meilleures = None, []
    for separateur in (",", ";", "\t"):
        essai = list(csv.reader(io.StringIO(texte), delimiter=separateur))
        if essai and len(essai[0]) > len(meilleures):
            meilleur, meilleures = separateur, essai
    return meilleures


def _index_colonnes(entetes):
    """Associe chaque grandeur à son numéro de colonne. Rend aussi ce qui manque."""
    propres = [_sans_accent(h) for h in entetes]
    prises, trouvees = set(), {}
    for grandeur in COLONNES:
        for mot in COLONNES[grandeur]:
            mot_p = _sans_accent(mot)
            for i, h in enumerate(propres):
                if i in prises or not h:
                    continue
                if mot_p == h or (len(mot_p) > 4 and mot_p in h):
                    trouvees[grandeur] = i
                    prises.add(i)
                    break
            if grandeur in trouvees:
                break
    return trouvees, [g for g in INDISPENSABLES if g not in trouvees]


def lire(chemin):
    """L'export entier, normalisé.

    Rend un dictionnaire :
      lignes           : une par ligne de l'export (campagne / ensemble / pub, avec ses chiffres)
      trouvees / absentes / souhaitees_absentes : ce que le fichier contenait vraiment
      total            : les totaux du compte, recalculés (jamais repris d'une ligne « total » du
                         fichier, qui peut être une ligne de synthèse mélangée aux vraies)
    """
    lignes_brutes = _ouvrir(chemin)
    # certaines lignes vides ou de titre traînent en tête : on prend la première ligne qui ressemble
    # à un en-tête (au moins trois colonnes dont une parle de dépense ou d'impressions)
    i_entete = 0
    for i, ligne in enumerate(lignes_brutes[:15]):
        texte = " ".join(_sans_accent(c) for c in ligne)
        if sum(1 for c in ligne if str(c).strip()) >= 3 and (
                "depens" in texte or "spent" in texte or "impression" in texte):
            i_entete = i
            break
    entetes = [str(c) for c in lignes_brutes[i_entete]]
    idx, absentes = _index_colonnes(entetes)

    lignes = []
    for brute in lignes_brutes[i_entete + 1:]:
        if not any(str(c).strip() for c in brute):
            continue
        ligne = {}
        for grandeur, i in idx.items():
            brut = brute[i] if i < len(brute) else None
            if grandeur in ("campagne", "ensemble", "pub", "objectif", "type_resultat", "statut",
                            "date_debut", "date_fin"):
                ligne[grandeur] = str(brut).strip() if brut is not None else ""
                ligne[grandeur + "_vide"] = _vide(brut)
            else:
                ligne[grandeur] = nombre(brut)
                ligne[grandeur + "_vide"] = _vide(brut)
        # une ligne sans nom du tout n'est pas une ligne de données (souvent une ligne « Total »)
        if not any(ligne.get(c) for c in ("campagne", "ensemble", "pub")):
            continue
        lignes.append(ligne)

    total = {}
    for grandeur in ("depense", "impressions", "clics", "resultats", "achats", "valeur_achats"):
        total[grandeur] = round(sum(l.get(grandeur, 0.0) for l in lignes), 2)
    total["lignes"] = len(lignes)

    return {
        "chemin": os.path.abspath(chemin),
        "entetes": entetes,
        "trouvees": sorted(idx),
        "absentes": absentes,
        "souhaitees_absentes": [g for g in SOUHAITEES if g not in idx],
        "lignes": lignes,
        "total": total,
    }
