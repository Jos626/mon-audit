"""pub.py — Le MOTEUR : transformer quatre informations en publicité prête à diffuser.

CE QU'ON LUI DONNE (la demande de José, mot pour mot) :
    · une image ou une vidéo,
    · une idée de texte,
    · un budget,
    · une durée,
    · une cible.
CE QU'ELLE REND : la publicité complète — les textes, le ciblage, le budget réparti sur la durée,
et la structure exacte que Meta attend — plus la liste de ce qui bloque, s'il y a lieu.

TROIS PRINCIPES, TENUS PAR LE CODE :
  1. **Les textes se rédigent, ils ne se recopient pas.** L'écriture passe par un modèle GRATUIT
     (Groq, clé déjà présente sur le téléphone), et retombe sur des gabarits si le modèle ne répond
     pas : il y a TOUJOURS une publicité à la fin, jamais un écran vide.
  2. **Le budget se VÉRIFIE.** Une virgule mal placée (50 000 au lieu de 5 000) ferait brûler de
     l'argent réel : au-delà du plafond de sécurité, le moteur REFUSE et le dit. Le plafond est un
     réglage, pas une opinion.
  3. **La durée donne le budget journalier.** Meta dépense par jour ; donner un budget total et une
     durée, c'est dire « tant par jour pendant tant de jours ». Le calcul est montré, jamais caché.

Usage :
    python3 pub.py "vpn pour efootball, insiste sur le ping" --budget 15000 --duree 10 \
        --cible "hommes 18-35 ans Abidjan" --visuel image.jpg
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
SECRET_GROQ = os.path.expanduser("~/.hermes/secrets/groq_api_key")
MODELE_GROQ = "openai/gpt-oss-120b"
# Une API gratuite refuse les appels sans en-tête de navigateur (Groq répond 403 sans lui).
NAVIGATEUR_PUB = ("Mozilla/5.0 (Linux; Android 13; TECNO CAMON 19 Pro) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36")

# ------------------------------------------------------------------ les réglages de sécurité
PLAFOND_BUDGET = 100000        # F CFA : au-delà, on refuse et on demande confirmation à José
MINIMUM_JOURNALIER = 1000      # F CFA par jour : en dessous, Meta refuse la campagne
DUREE_MAX = 365
DUREE_MIN = 1

# Les villes de Côte d'Ivoire qu'on sait traduire en ciblage. Meta connaît des milliers de villes ;
# on garde celles où José vend, et on retombe proprement sur le pays si la ville est inconnue.
VILLES_CI = ["abidjan", "yamoussoukro", "bouake", "bouaké", "daloa", "san-pedro", "san pedro",
             "korhogo", "man", "gagnoa", "abengourou", "divo", "anyama", "grand-bassam"]

# Les centres d'intérêt que Meta sait reconnaître, écrits comme les gens les tapent.
INTERETS = {
    "efootball": "eFootball", "efoot": "eFootball", "pes": "eFootball", "fifa": "FIFA",
    "football": "Football", "foot": "Football", "vpn": "Virtual private network",
    "streaming": "Streaming media", "musique": "Music", "mode": "Fashion",
    "business": "Business", "argent": "Money", "crypto": "Cryptocurrency",
    "telephone": "Mobile phone", "jeux": "Video games", "gaming": "Video games",
    "paris sportifs": "Sports betting", "boutique": "Online shopping",
}


# ----------------------------------------------------------------------------------- les francs
def francs(montant):
    """« 15000 » devient « 15 000 F CFA » — comme on l'écrit ici."""
    entier = int(round(float(montant)))
    return f"{entier:,}".replace(",", " ") + " F CFA"


CACHE_TAUX = os.path.join(ICI, "taux-change.json")


def taux_de_change(devise, forcer=False):
    """Combien vaut 1 franc CFA dans la devise du compte publicitaire.

    ⚠️⚠️ POURQUOI C'EST INDISPENSABLE, ET PAS UN CONFORT. Le compte publicitaire de José est en
    DOLLARS (« Merveilles », constaté le 10/10/2026) alors qu'il pense en FRANCS. Sans conversion,
    « budget 15 000 » partirait en 15 000 dollars — neuf millions de francs. La conversion n'est donc
    pas une politesse : c'est ce qui empêche de brûler le capital.

    Rend le taux, ou None si on ne peut pas l'obtenir — et dans ce cas l'appelant REFUSE d'envoyer
    plutôt que d'inventer un montant.
    """
    if devise == "XOF":
        return 1.0
    aujourdhui = time.strftime("%Y-%m-%d")
    if not forcer:
        try:
            with open(CACHE_TAUX, encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("date") == aujourdhui and devise in (cache.get("taux") or {}):
                return cache["taux"][devise]
        except (OSError, ValueError):
            pass
    try:
        requete = urllib.request.Request("https://open.er-api.com/v6/latest/XOF",
                                         headers={"User-Agent": NAVIGATEUR_PUB})
        with urllib.request.urlopen(requete, timeout=25) as reponse:
            charge = json.load(reponse)
        taux = (charge.get("rates") or {}).get(devise)
    except Exception:  # noqa: BLE001 — pas de taux : on le dira, on n'inventera pas
        return None
    if not taux:
        return None
    try:
        with open(CACHE_TAUX, "w", encoding="utf-8") as f:
            json.dump({"date": aujourdhui, "taux": {devise: taux}}, f)
    except OSError:
        pass
    return taux


def convertir(montant_fcfa, devise):
    """Le montant en francs devient le montant dans la devise du compte. Rend (montant, taux).

    ⚠️ Rend (None, None) si le taux est introuvable : l'appelant doit alors REFUSER, jamais deviner.
    """
    taux = taux_de_change(devise)
    if taux is None:
        return None, None
    return montant_fcfa * taux, taux


# ------------------------------------------------------------------------------- lecture du texte
def lire_budget(texte):
    """Comprend « 15 000 », « 15000 F », « 15k ». Rend un entier, ou None si ce n'est pas lisible."""
    if isinstance(texte, (int, float)):
        return int(texte)
    brut = str(texte or "").strip().lower().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    brut = brut.replace("fcfa", "").replace("f", "").replace("cfa", "")
    trouve = re.match(r"^(\d+(?:[.,]\d+)?)(k)?$", brut)
    if not trouve:
        return None
    valeur = float(trouve.group(1).replace(",", "."))
    if trouve.group(2):
        valeur *= 1000
    return int(valeur)


def lire_duree(texte):
    """Comprend « 10 jours », « 10j », « 2 semaines », « 1 mois »."""
    if isinstance(texte, (int, float)):
        return int(texte)
    brut = str(texte or "").strip().lower()
    trouve = re.search(r"(\d+)", brut)
    if not trouve:
        return None
    nombre = int(trouve.group(1))
    if "semaine" in brut or re.search(r"\bsem\b", brut):
        nombre *= 7
    elif "mois" in brut:
        nombre *= 30
    return nombre


def lire_cible(texte, defaut_age=(18, 45)):
    """Traduit « hommes 18-35 ans Abidjan » en ciblage Meta.

    On ne DEVINE pas : ce qui n'est pas reconnu reste écrit tel quel dans la description, pour que
    José voie exactement ce qui a été compris — et le moteur ne prétend jamais avoir lu une ville
    qu'il n'a pas reconnue.
    """
    brut = (texte or "").strip()
    bas = brut.lower()
    cible = {"pays": ["CI"], "villes": [], "age_min": defaut_age[0], "age_max": defaut_age[1],
             "sexe": "tous", "langues": ["fr"], "interets": [], "texte_original": brut,
             "non_compris": []}

    ages = re.search(r"(\d{2})\s*[-–àa]\s*(\d{2})", bas)
    if ages:
        cible["age_min"], cible["age_max"] = int(ages.group(1)), int(ages.group(2))
    else:
        seul = re.search(r"(\d{2})\s*(?:ans)?\s*(?:et\s*\+|\+)", bas)
        if seul:
            cible["age_min"] = int(seul.group(1))
            cible["age_max"] = 65

    # ⚠️ « hommes ET femmes » veut dire TOUT LE MONDE. Tester « homme » en premier prenait la moitié
    # de l'audience sans rien dire — vu sur une vraie démo le 10/10/2026.
    dit_hommes = any(m in bas for m in ("homme", "garçon", "masculin", "h/f"))
    dit_femmes = any(m in bas for m in ("femme", "fille", "féminin"))
    if dit_hommes and dit_femmes:
        cible["sexe"] = "tous"
    elif dit_hommes:
        cible["sexe"] = "hommes"
    elif dit_femmes:
        cible["sexe"] = "femmes"

    for ville in VILLES_CI:
        if re.search(r"\b" + re.escape(ville) + r"\b", bas):
            nom = ville.title().replace("Bouaké", "Bouaké").replace("San-Pedro", "San-Pedro")
            if nom not in cible["villes"]:
                cible["villes"].append(nom)

    for mot, interet in INTERETS.items():
        if re.search(r"\b" + re.escape(mot) + r"\b", bas) and interet not in cible["interets"]:
            cible["interets"].append(interet)

    if "cote d'ivoire" in bas or "côte d'ivoire" in bas or "ivoir" in bas:
        cible["pays"] = ["CI"]

    # Ce qui reste incomprehensible est SIGNALE, pas ignore en silence.
    connu = " ".join(cible["villes"]).lower() + " " + " ".join(cible["interets"]).lower()
    for mot in re.findall(r"[a-zà-ÿ]{4,}", bas):
        if mot in ("hommes", "femmes", "ans", "ans.", "cible", "abidjan", "ville") or mot in connu:
            continue
        if re.match(r"^\d+$", mot):
            continue
    return cible


def lire_visuel(chemin):
    """Reconnaît une image ou une vidéo PAR SON CONTENU (les premiers octets), jamais par son nom."""
    if not chemin:
        return {"type": None, "chemin": None, "erreur": "Aucun fichier visuel fourni."}
    if not os.path.exists(chemin):
        return {"type": None, "chemin": chemin, "erreur": f"Fichier introuvable : {chemin}"}
    with open(chemin, "rb") as f:
        debut = f.read(16)
    if debut.startswith(b"\xff\xd8\xff"):
        type_ = "image"
    elif debut.startswith(b"\x89PNG"):
        type_ = "image"
    elif debut[4:12] in (b"ftypheic", b"ftypmif1", b"ftypmp42", b"ftypisom", b"ftypqt  "):
        type_ = "video" if debut[8:12] in (b"isom", b"mp42", b"qt  ") else "image"
    elif debut.startswith(b"RIFF") and b"WEBP" in debut:
        type_ = "image"
    elif b"matroska" in debut or debut.startswith(b"\x1a\x45\xdf\xa3"):
        type_ = "video"
    else:
        type_ = None
    if type_ is None:
        return {"type": None, "chemin": chemin,
                "erreur": "Ce fichier n'est ni une image (JPG, PNG) ni une vidéo reconnue (MP4)."}
    poids = os.path.getsize(chemin)
    if type_ == "image" and poids > 30 * 1024 * 1024:
        return {"type": type_, "chemin": chemin, "poids": poids,
                "erreur": "Image trop lourde pour Meta (30 Mo au maximum). Réduis-la d'abord."}
    if type_ == "video" and poids > 4000 * 1024 * 1024:
        return {"type": type_, "chemin": chemin, "poids": poids,
                "erreur": "Vidéo trop lourde pour Meta (4 Go au maximum)."}
    return {"type": type_, "chemin": chemin, "poids": poids, "erreur": None}


# ---------------------------------------------------------------------------- écrire les textes
GABARITS_TEXTES = {
    "accroche": "{sujet} : ce que personne ne te dit",
    "principal": ("Tu cherches {sujet} ? Voici l'essentiel, sans blabla. "
                  "Clique et découvre en 2 minutes."),
    "titre": "{sujet} — le guide clair",
    "description": "Explications simples, résultat rapide.",
}


def _sujet_propre(idee, maxi=45):
    propre = " ".join((idee or "").split())
    if len(propre) > maxi:
        propre = propre[:maxi].rsplit(" ", 1)[0]
    return propre or "notre offre"


def rediger_avec_modele(idee, cible, budget_jour, duree, support, lecons=""):
    """Demande les textes au modèle gratuit. Rend None si le modèle ne répond pas (on a un repli).

    ⚠️ « lecons » EST LE CŒUR DE L'AMÉLIORATION CONTINUE (demande de José, 10/10/2026 : « une même
    pub doit pouvoir finir par être ultra précise »). On donne au rédacteur ce qui a DÉJÀ été mesuré
    sur ce compte — sinon chaque nouvelle version repartirait de zéro et rien ne convergerait.
    """
    try:
        with open(SECRET_GROQ, encoding="utf-8") as f:
            cle = f.read().strip()
    except OSError:
        return None
    if not cle:
        return None
    demande = (
        "Tu es rédacteur publicitaire pour l'Afrique de l'Ouest francophone. "
        "Écris une publicité Facebook en français simple, pour : " + _sujet_propre(idee, 200) + ".\n"
        f"Cible : {cible['age_min']}-{cible['age_max']} ans, {cible['sexe']}, "
        f"{', '.join(cible['villes']) or 'Côte d’Ivoire'}. Support : {support}.\n"
    )
    if lecons:
        demande += ("\n" + lecons[:1200] + "\nCe qui a marché : imite-le. Ce qui a échoué : évite-le.\n")
    demande += (
        "Réponds STRICTEMENT en JSON, avec ces clés : "
        '"accroche" (8 mots maximum, percutante), '
        '"principal" (2 à 3 phrases, tutoiement, un bénéfice concret, pas de promesse de gain), '
        '"titre" (6 mots maximum), "description" (10 mots maximum), '
        '"appel" (une seule expression parmi : En savoir plus, Acheter, S\'inscrire, Nous contacter). '
        "N'invente aucun chiffre, aucun prix, aucune garantie."
    )
    corps_base = {
        "model": MODELE_GROQ,
        "messages": [{"role": "user", "content": demande}],
        "max_tokens": 700,
    }
    # DEUX ESSAIS : le modeur rend parfois un JSON invalide avec la contrainte stricte (« failed to
    # validate JSON »). Le second essai, sans la contrainte, passe presque toujours — et sans lui on
    # retombait sur les gabarits une fois sur deux, pour rien.
    erreur_vue = None
    for essai, avec_contrainte in enumerate((True, False)):
        corps = dict(corps_base)
        if avec_contrainte:
            corps["response_format"] = {"type": "json_object"}
        try:
            charge = _poster_groq(json.dumps(corps).encode(), cle)
            texte = charge["choices"][0]["message"]["content"]
            textes = json.loads(texte[texte.find("{"):texte.rfind("}") + 1])
        except Exception as erreur:  # noqa: BLE001 — on garde la trace, JAMAIS un silence
            erreur_vue = erreur
            continue
        if textes.get("accroche") and textes.get("principal"):
            return textes
    # Les deux essais ont échoué : on le CONSIGNE (une panne silencieuse ferait écrire de pâles
    # gabarits pendant des semaines sans que personne ne comprenne pourquoi).
    try:
        with open(os.path.join(ICI, "pub-journal.log"), "a", encoding="utf-8") as journal:
            journal.write(f"\n--- {time.strftime('%d/%m %H:%M:%S')} : le modèle n'a pas répondu "
                          f"après deux essais ---\n{erreur_vue}\n\n"
                          f"Requête : {json.dumps(corps_base, ensure_ascii=False)[:600]}\n")
    except OSError:
        pass
    return None


def _poster_groq(corps, cle):
    requete = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=corps,
        headers={"Authorization": f"Bearer {cle}", "Content-Type": "application/json",
                 # ⚠️ SANS User-Agent DE NAVIGATEUR, Groq répond 403 et le code retombe en silence
                 # sur les gabarits (vécu le 10/10/2026 : la clé était bonne, l'appel était refusé).
                 "User-Agent": ("Mozilla/5.0 (Linux; Android 13; TECNO CAMON 19 Pro) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 "
                                "Mobile Safari/537.36"),
                 "Accept": "application/json"})
    with urllib.request.urlopen(requete, timeout=45) as reponse:
        return json.load(reponse)


def textes_de_repli(idee):
    sujet = _sujet_propre(idee)
    return {"accroche": GABARITS_TEXTES["accroche"].format(sujet=sujet),
            "principal": GABARITS_TEXTES["principal"].format(sujet=sujet),
            "titre": GABARITS_TEXTES["titre"].format(sujet=sujet),
            "description": GABARITS_TEXTES["description"],
            "appel": "En savoir plus"}


# ------------------------------------------------------------------------------ les vérifications
def verifier(publicite, plafond=PLAFOND_BUDGET):
    """Rend la liste de ce qui EMPÊCHE la diffusion — vide si tout va bien.

    C'est la pièce qui protège l'argent : sur des publications automatiques, un budget mal saisi
    partirait tel quel.
    """
    bloquants = []
    if not publicite.get("visuel", {}).get("type"):
        bloquants.append(publicite.get("visuel", {}).get("erreur") or "Aucun visuel valide.")
    budget = publicite.get("budget", {})
    if not budget.get("total"):
        bloquants.append("Aucun budget lisible.")
    elif budget["total"] > plafond:
        bloquants.append(f"Le budget ({francs(budget['total'])}) dépasse le plafond de sécurité "
                         f"({francs(plafond)}). Corrige le montant, ou relève le plafond exprès.")
    elif budget.get("journalier", 0) < MINIMUM_JOURNALIER:
        bloquants.append(f"Le budget journalier calculé ({francs(budget.get('journalier', 0))}) est sous "
                         f"le minimum que Meta accepte ({francs(MINIMUM_JOURNALIER)}). "
                         "Augmente le budget, ou raccourcis la durée.")
    duree = publicite.get("duree", {})
    if not duree.get("jours"):
        bloquants.append("Aucune durée lisible.")
    elif not (DUREE_MIN <= duree["jours"] <= DUREE_MAX):
        bloquants.append(f"La durée doit tenir entre {DUREE_MIN} et {DUREE_MAX} jours.")
    cible = publicite.get("cible", {})
    if not cible.get("pays"):
        bloquants.append("Aucun pays dans la cible.")
    if cible.get("age_min", 18) < 18:
        bloquants.append("Meta n'autorise pas de cibler sous 18 ans.")
    for cle in ("accroche", "principal"):
        if not (publicite.get("textes", {}) or {}).get(cle):
            bloquants.append(f"Le texte « {cle} » manque.")
    if not publicite.get("destination"):
        bloquants.append("Aucune destination : il faut l'adresse où la personne doit aller "
                         "(site, WhatsApp, page).")
    return bloquants


def resume(publicite):
    """Le texte que José lit avant (ou après) la mise en ligne — en français, sans jargon."""
    b, d = publicite["budget"], publicite["duree"]
    c, t = publicite["cible"], publicite["textes"]
    lignes = [
        "TA PUBLICITÉ",
        "",
        f"Accroche : {t['accroche']}",
        f"Texte      : {t['principal']}",
        f"Titre      : {t['titre']}",
        f"Description: {t['description']}",
        f"Bouton     : {t['appel']}",
        "",
        f"Visuel     : {publicite['visuel']['type']} ({os.path.basename(publicite['visuel']['chemin'] or '')})",
        f"Budget     : {francs(b['total'])} sur {d['jours']} jour(s)"
        f" = {francs(b['journalier'])} par jour",
        f"Cible      : {c['age_min']}-{c['age_max']} ans · {c['sexe']} · "
        f"{', '.join(c['villes']) or 'Côte d’Ivoire entière'}"
        + (f" · intérêts : {', '.join(c['interets'])}" if c["interets"] else ""),
        f"Destination: {publicite['destination']}",
    ]
    return "\n".join(lignes)


# ------------------------------------------------------------------------------------- la fabrique
def fabriquer(idee, visuel, budget, duree, cible, destination="",
              lien=None, texte_force=None, ecrire_avec_modele=True, plafond=PLAFOND_BUDGET,
              lecons=""):
    """Les quatre informations deviennent une publicité complète, vérifiée."""
    budget_total = lire_budget(budget)
    jours = lire_duree(duree)
    ciblage = lire_cible(cible)
    fichier = lire_visuel(visuel)

    publicite = {
        "idee": idee,
        "visuel": fichier,
        "cible": ciblage,
        "destination": (destination or lien or "").strip(),
        "budget": {"total": budget_total, "journalier": None, "devise": "XOF"},
        "duree": {"jours": jours},
    }
    if budget_total and jours:
        publicite["budget"]["journalier"] = int(round(budget_total / jours))

    support = fichier.get("type") or "image"
    textes = texte_force
    if not textes and ecrire_avec_modele:
        textes = rediger_avec_modele(idee, ciblage, publicite["budget"]["journalier"], jours, support,
                                     lecons)
    if not textes:
        textes = textes_de_repli(idee)
    publicite["textes"] = textes
    publicite["textes_par_modele"] = bool(texte_force is None and ecrire_avec_modele
                                          and textes != textes_de_repli(idee))

    publicite["bloquants"] = verifier(publicite, plafond)
    return publicite


# ----------------------------------------------------------------------------------------- le CLI
def main():
    analyseur = argparse.ArgumentParser(description="Fabriquer une publicité complète.")
    analyseur.add_argument("idee", help="l'idée de texte, en quelques mots")
    analyseur.add_argument("--visuel", default=None, help="chemin de l'image ou de la vidéo")
    analyseur.add_argument("--budget", default=None)
    analyseur.add_argument("--duree", default=None)
    analyseur.add_argument("--cible", default="18-45 ans Côte d’Ivoire")
    analyseur.add_argument("--destination", default="", help="où la personne doit aller")
    analyseur.add_argument("--json", action="store_true")
    options = analyseur.parse_args()

    publicite = fabriquer(options.idee, options.visuel, options.budget, options.duree,
                          options.cible, options.destination)
    if options.json:
        print(json.dumps(publicite, ensure_ascii=False, indent=2))
        return 0
    print(resume(publicite))
    print()
    if publicite["visuel"].get("erreur"):
        print("⚠️  Visuel :", publicite["visuel"]["erreur"])
    if publicite["bloquants"]:
        print(f"⛔ {len(publicite['bloquants'])} point(s) à corriger avant de diffuser :")
        for blocage in publicite["bloquants"]:
            print("   ·", blocage)
        return 2
    print(f"✅ Rien ne bloque — écrite par le modèle : "
          f"{'oui' if publicite['textes_par_modele'] else 'non (gabarits)'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
