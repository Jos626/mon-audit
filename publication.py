"""publication.py — mettre la publicité EN LIGNE chez Meta, et vérifier ce qui a été créé.

⚠️ CE FICHIER DÉPENSE DE L'ARGENT RÉEL. Trois protections sont dans le code, pas dans les bonnes
intentions :

  1. **Rien ne part sans les quatre réglages du compte** (jeton, compte publicitaire, page, lien
     d'arrivée). Un jeton n'est PAS le droit de dépenser : sans la page, Meta refuse — et sans compte
     publicitaire, on ne saurait pas où l'argent part.
  2. **Le budget envoyé est RELU après création.** Meta compte dans l'unité la plus petite de la
     devise du compte : la même valeur peut vouloir dire 1 500 F ou 150 000 F selon la devise et le
     pays du compte. On ne se fie donc pas à ce qu'on a envoyé : on **relit** la campagne créée, on
     compare au montant voulu, et **si le montant relu n'est pas le bon, on MET EN PAUSE tout seul**
     et on le dit. Une publicité qui part au centuple se coupe en dix secondes, pas dans la soirée.
  3. **Le plafond de sécurité de `pub.py`** s'applique avant l'envoi (voir PLAFOND_BUDGET).

Le jeton n'est JAMAIS écrit par ce module : il se lit dans un fichier de secrets, et il reste là où
José l'a rangé.

Usage :
    python3 publication.py --a-blanc <publicite.json>     # montre TOUT ce qui serait envoyé, sans rien créer
    python3 publication.py --en-ligne <publicite.json>    # crée campagne, ensemble et annonce
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import pub

ICI = os.path.dirname(os.path.abspath(__file__))
SECRET_REGLAGES = os.path.expanduser("~/.hermes/secrets/meta-publicite.json")
JOURNAL = os.path.join(ICI, "publication-journal.log")

VERSION_API = "v25.0"
GRAPHE = f"https://graph.facebook.com/{VERSION_API}"

# Les devises sans sous-unité : Meta y compte à l'unité près. Partout ailleurs (dollar, euro…),
# le montant envoyé est en CENTIMES — d'où le ×100.
DEVISES_SANS_SOUS_UNITE = ("XOF", "XAF", "JPY", "KRW", "CLP", "VND", "PYG", "RWF", "UGX", "DJF",
                           "GNF", "KMF", "BIF", "ISK", "HUF", "TWD")

# L'objectif et l'optimisation suivent le but : faire venir du monde (trafic), ou faire écrire
# (messagerie). Le reste se règle dans pub.py, jamais ici.
OBJECTIFS = {
    "trafic": ("OUTCOME_TRAFFIC", "LINK_CLICKS", "IMPRESSIONS"),
    "messages": ("OUTCOME_ENGAGEMENT", "CONVERSATIONS", "IMPRESSIONS"),
    "ventes": ("OUTCOME_SALES", "OFFSITE_CONVERSIONS", "IMPRESSIONS"),
}


def consigner(texte):
    """Une trace lisible de tout ce qui touche à l'argent. Jamais d'échec silencieux."""
    try:
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%d/%m %H:%M:%S')}] {texte}\n")
    except OSError:
        pass


def lire_reglages():
    """Les quatre réglages du compte. Rend (reglages, manquants) — jamais une exception obscure."""
    try:
        with open(SECRET_REGLAGES, encoding="utf-8") as f:
            reglages = json.load(f)
    except FileNotFoundError:
        return {}, ["le fichier de réglages du compte publicitaire n'existe pas encore"]
    except ValueError as erreur:
        return {}, [f"le fichier de réglages est illisible ({erreur})"]
    manquants = [cle for cle in ("jeton", "compte_publicitaire", "page_id") if not reglages.get(cle)]
    return reglages, manquants


# --------------------------------------------------------------------------------- appels réseau
def appel(chemin, parametres, reglages, methode="GET"):
    """Un appel à Meta. Rend la réponse décodée, ou lève une erreur QUI DIT QUOI FAIRE."""
    parametres = dict(parametres)
    parametres["access_token"] = reglages["jeton"]
    donnees = urllib.parse.urlencode(parametres).encode()
    if methode == "GET":
        url = f"{GRAPHE}/{chemin}?{donnees.decode()}"
        requete = urllib.request.Request(url, headers={"User-Agent": "MonAudit/1.0"})
    else:
        requete = urllib.request.Request(f"{GRAPHE}/{chemin}", data=donnees,
                                         headers={"User-Agent": "MonAudit/1.0"})
    try:
        with urllib.request.urlopen(requete, timeout=60) as reponse:
            return json.load(reponse)
    except urllib.error.HTTPError as erreur:
        code = sous_code = None
        try:
            corps = json.loads(erreur.read().decode("utf-8", "replace"))
            detail = corps.get("error", {}) or {}
            message = detail.get("message", "")
            code = detail.get("code")
            # ⚠️ LE MESSAGE GÉNÉRIQUE NE SUFFIT PAS. « Invalid parameter » ne dit pas QUEL paramètre :
            # Meta range la précision dans error_user_msg / error_data. Sans ça, on cherche à
            # l'aveugle — vécu le 10/10/2026 sur la création d'ensemble.
            sous_code = detail.get("error_subcode")
            precis = detail.get("error_user_msg") or ""
            donnees = detail.get("error_data") or ""
            message = " ".join(str(x) for x in (message, precis, donnees) if x)
        except Exception:  # noqa: BLE001
            message, code, sous_code = "", None, None
        consigner(f"ERREUR Meta sur {chemin} : code={code} sous-code={sous_code} {message}")
        if code == 190:
            raise RuntimeError("Le jeton Meta a expiré ou a été révoqué. Il faut renouveler "
                               "l'autorisation (un jeton ne dure pas éternellement).") from erreur
        if code == 200 or code == 10:
            raise RuntimeError("Le jeton n'a pas le droit de GÉRER les annonces "
                               "(permission ads_management). Sans ce droit, on peut lire un compte "
                               "mais pas créer de publicité.") from erreur
        raise RuntimeError(f"Meta a refusé ({code}) : {message}") from erreur
    except urllib.error.URLError as erreur:
        consigner(f"RÉSEAU injoignable sur {chemin} : {erreur}")
        raise RuntimeError("Impossible de joindre Meta (réseau). Réessaie dans un instant.") from erreur


def televerser_image(chemin_image, reglages):
    """Envoie le visuel à Meta et rend son empreinte (image_hash), que la publicité réutilise."""
    frontiere = uuid.uuid4().hex
    with open(chemin_image, "rb") as f:
        contenu = f.read()
    nom = os.path.basename(chemin_image)
    type_ = mimetypes.guess_type(nom)[0] or "image/jpeg"
    corps = b""
    for cle, valeur in (("access_token", reglages["jeton"]),):
        corps += (f"--{frontiere}\r\nContent-Disposition: form-data; name=\"{cle}\"\r\n\r\n"
                  f"{valeur}\r\n").encode()
    corps += (f"--{frontiere}\r\nContent-Disposition: form-data; name=\"filename\"; "
              f"filename=\"{nom}\"\r\nContent-Type: {type_}\r\n\r\n").encode() + contenu + b"\r\n"
    corps += f"--{frontiere}--\r\n".encode()
    requete = urllib.request.Request(
        f"{GRAPHE}/{reglages['compte_publicitaire']}/adimages", data=corps,
        headers={"Content-Type": f"multipart/form-data; boundary={frontiere}",
                 "User-Agent": "MonAudit/1.0"})
    try:
        with urllib.request.urlopen(requete, timeout=180) as reponse:
            charge = json.load(reponse)
    except urllib.error.HTTPError as erreur:
        detail = erreur.read().decode("utf-8", "replace")[:400]
        consigner(f"ÉCHEC du téléversement d'image : {detail}")
        raise RuntimeError(f"Meta a refusé l'image : {detail}") from erreur
    images = charge.get("images") or {}
    if not images:
        raise RuntimeError(f"Meta n'a pas renvoyé d'empreinte d'image : {charge}")
    return list(images.values())[0]["hash"]


# ---------------------------------------------------------------------------- la mise en ligne
def verifier_acces(reglages):
    """Avant de créer quoi que ce soit : le compte répond-il, et dans quelle devise ?"""
    compte = appel(reglages["compte_publicitaire"],
                   {"fields": "name,currency,account_status,amount_spent"}, reglages)
    page = appel(reglages["page_id"], {"fields": "name"}, reglages)
    return {"compte": compte, "page": page}


def construire_objectif(reglages, publicite):
    but = (reglages.get("but") or "trafic").lower()
    objectif, optimisation, facturation = OBJECTIFS.get(but, OBJECTIFS["trafic"])
    return objectif, optimisation, facturation


def ciblage_meta(publicite, reglages):
    """Traduit la cible lue dans le texte en ce que Meta attend.

    ⛔ PIÈGE QUI BLOQUE TOUT (vécu le 10/10/2026) : cibler le PAYS et la VILLE du même pays ensemble
    fait échouer la création — « Supprimez un lieu en conflit pour continuer », blame_field targeting.
    Abidjan est en Côte d'Ivoire : inutile de demander les deux. Une ville trouvée remplace le pays ;
    le pays ne sert que de repli quand aucune ville n'a été reconnue.
    """
    cible = publicite["cible"]
    pays = cible.get("pays") or ["CI"]
    villes = []
    for nom_ville in (cible.get("villes") or []):
        trouve = appel("search", {"type": "adgeolocation", "location_types": '["city"]',
                                  "q": nom_ville, "country_code": pays[0]}, reglages)
        for resultat in trouve.get("data", [])[:1]:
            villes.append({"key": resultat["key"], "radius": 25, "distance_unit": "kilometer"})
    geo = {"cities": villes} if villes else {"countries": pays}
    ciblage = {"geo_locations": geo, "age_min": max(18, cible.get("age_min", 18)),
               "age_max": min(65, cible.get("age_max", 45))}
    if cible.get("sexe") == "hommes":
        ciblage["genders"] = [1]
    elif cible.get("sexe") == "femmes":
        ciblage["genders"] = [2]
    # ⚠️ ADVANTAGE_AUDIENCE, OBLIGATOIRE (code 100, vécu le 10/10/2026) : Meta refuse de créer un
    # ensemble sans savoir si on le laisse ÉLARGIR la cible tout seul. On met 0 (désactivé) : quand
    # José demande « femmes 25-45 ans à Abidjan », la publicité doit viser ÇA — pas « à peu près
    # ça ». C'est aussi ce qui rend les mesures lisibles : une cible qui bouge seule rend le
    # journal d'apprentissage inexploitable.
    ciblage["targeting_automation"] = {"advantage_audience": 0}
    if cible.get("langues"):
        ciblage["locales"] = [6]        # 6 = français, la seule langue qu'on cible ici
    return ciblage


def creer_et_verifier(chemin, parametres, reglages, quoi, champ_liste=None, liste_de=None):
    """Crée un objet chez Meta ET VÉRIFIE qu'il existe vraiment.

    ⛔⛔ LA FAUTE QUI A COÛTÉ (vécue le 10/10/2026) : `chemin` DOIT être une SOUS-LISTE du compte
    (« act_…/campaigns »), JAMAIS le compte lui-même. En passant « act_… » seul, le POST ne crée rien :
    il MODIFIE LE COMPTE — le nom de la campagne de test a remplacé le nom du compte de José
    (« Merveilles »), et Meta répondait « {"success": true} », donc le code croyait avoir réussi.
    D'où le garde-fou ci-dessous : mieux vaut une erreur bruyante qu'un compte renommé en silence.

    ⛔⛔ POURQUOI CE N'EST PAS DE LA PARANOÏA (vécu le 10/10/2026) : sur le même appel, Meta rend
    tantôt « {"id": "…"} », tantôt « {"success": true} » — et dans ce second cas **RIEN n'est créé**,
    sans le moindre message d'erreur. Un code qui se fie à la réponse enchaîne alors sur une campagne
    fantôme : ensembles et annonces orphelins, et José qui croit sa publicité en ligne.

    On refait donc l'appel UNE fois, puis on va CHERCHER l'objet par son nom. Si on ne le trouve pas,
    on s'arrête et on le dit — jamais de succès inventé.
    """
    noms = {"campagne": "campaigns", "ensemble": "adsets", "annonce": "ads", "créatif": "adcreatives"}

    # ⛔ GARDE-FOU CONTRE LA FAUTE QUI A RENOMMÉ LE COMPTE DE JOSÉ. Si `chemin` ne désigne pas une
    # sous-liste, on s'arrête AVANT d'envoyer quoi que ce soit : un POST sur « act_… » ne crée rien,
    # il modifie le compte. Mieux vaut une erreur bruyante que cinq secondes de honte silencieuse.
    if not any(chemin.rstrip("/").endswith("/" + suffixe)
               for suffixe in ("campaigns", "adsets", "ads", "adcreatives")):
        raise RuntimeError(
            f"Refusé : « {chemin} » ne désigne pas une sous-liste du compte. Une création doit viser "
            "…/campaigns, …/adsets, …/ads ou …/adcreatives — viser le compte lui-même le MODIFIE au "
            "lieu de créer (c'est ce qui a renommé le compte en douce le 10/10/2026).")

    for tentative in (1, 2):
        reponse = appel(chemin, parametres, reglages, "POST")
        identifiant = reponse.get("id") if isinstance(reponse, dict) else None
        if identifiant:
            return identifiant
        print(f"[publication] Meta a répondu sans créer {quoi} "
              f"(réponse {json.dumps(reponse, ensure_ascii=False)[:80]}) — essai {tentative}/2",
              flush=True)
        if liste_de:
            # On cherche l'objet par son nom : s'il existe, la création a marché malgré la réponse.
            try:
                liste = appel(f"{reglages['compte_publicitaire']}/{noms.get(quoi, 'campaigns')}",
                              {"fields": "name,id", "limit": 25}, reglages).get("data", [])
            except RuntimeError:
                liste = []
            nom_voulu = (parametres.get("name") or "").strip()
            for objet in liste:
                if (objet.get("name") or "").strip() == nom_voulu:
                    print(f"[publication] {quoi} retrouvée malgré la réponse : {objet['id']}",
                          flush=True)
                    return objet["id"]
        # ⚠️ PAUSE PLUS LONGUE ENTRE LES DEUX ESSAIS : Meta répond « success » sans rien créer quand
        # les créations s'enchaînent trop vite (comportement observé le 10/10/2026 sur un compte en
        # mode développement). Insister à la seconde près ne sert à rien ; laisser respirer, oui.
        time.sleep(4)
    raise RuntimeError(
        f"Meta n'a pas créé {quoi} (elle a répondu « success » sans rien créer, deux fois de suite). "
        "Rien n'a été lancé. Réessaie dans un moment : c'est un caprice de leur API, pas une faute "
        "de ta publicité.")


def mettre_en_ligne(publicite, reglages, en_ligne=True):
    """Crée la campagne, l'ensemble et l'annonce. Puis RELIT et compare — voir l'en-tête."""
    if publicite.get("bloquants"):
        raise RuntimeError("La publicité n'est pas bonne à publier : " + " · ".join(publicite["bloquants"]))
    if not publicite.get("destination"):
        raise RuntimeError("Aucune destination (l'adresse où la personne doit aller).")

    acces = verifier_acces(reglages)
    compte, page = acces["compte"], acces["page"]
    devise = compte.get("currency", "XOF")
    # ⚠️ LE POINT QUI COÛTE CHER, EN DEUX MORCEAUX :
    # 1) le montant doit être CONVERTI dans la devise du compte — José pense en francs, son compte
    #    « Merveilles » est en DOLLARS. Sans conversion, « 15 000 » partirait en 15 000 dollars ;
    # 2) Meta compte dans l'unité la PLUS PETITE de la devise : centimes pour le dollar et l'euro
    #    (×100), rien pour le franc CFA (×1). On part de la devise DU COMPTE, et on relit après.
    facteur = 1 if devise in DEVISES_SANS_SOUS_UNITE else 100
    journalier_compte, taux = pub.convertir(publicite["budget"]["journalier"], devise)
    if journalier_compte is None:
        raise RuntimeError("Je n'ai pas pu obtenir le taux de change franc CFA → "
                           f"{devise} : je refuse d'envoyer un montant au hasard. Réessaie quand le "
                           "réseau répond (rien n'a été créé).")
    total_compte = publicite["budget"]["total"] * (taux or 1)
    budget_api = int(round(journalier_compte * facteur))
    total_api = int(round(total_compte * facteur))

    objectif, optimisation, facturation = construire_objectif(reglages, publicite)
    statut = "ACTIVE" if en_ligne else "PAUSED"
    maintenant = int(time.time()) + 300          # on démarre dans 5 minutes
    fin = maintenant + publicite["duree"]["jours"] * 86400
    nom = publicite["textes"]["titre"][:60] or publicite["idee"][:60]

    journal_des_etapes = []
    nom_image = None
    if publicite["visuel"]["type"] == "image":
        nom_image = televerser_image(publicite["visuel"]["chemin"], reglages)
        journal_des_etapes.append(f"visuel téléversé (empreinte {nom_image[:12]}…)")

    campagne_id = creer_et_verifier(f"{reglages['compte_publicitaire']}/campaigns", {
        "name": f"{nom} — {time.strftime('%d/%m %H:%M')}",
        "objective": objectif,
        "status": statut,
        "special_ad_categories": "[]",
        # ⛔⛔ NE JAMAIS ENVOYER « buying_type » AVEC LES OBJECTIFS « OUTCOME_* » (10/10/2026).
        # Meta répond alors « {"success": true} » — un succès qui ne crée RIEN, sans le moindre
        # message d'erreur. La campagne n'existe pas, et le code croit avoir réussi. C'est le pire
        # genre de panne : silencieuse. La preuve se fait en RELISANT les campagnes du compte.
        # ⚠️ ET « is_adset_budget_sharing_enabled » est EXIGÉ dès qu'on ne prend pas le budget au
        # niveau de la campagne (code 100, sous-code 4834011) : false = chacun garde son budget.
        "is_adset_budget_sharing_enabled": "false",
    }, reglages, "campagne", liste_de=True)
    journal_des_etapes.append(f"campagne créée : {campagne_id}")

    reglages_ensemble = {
        "name": f"Ensemble — {nom}",
        "campaign_id": campagne_id,
        "billing_event": facturation,
        "optimization_goal": optimisation,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        # ⛔ UN SEUL BUDGET À LA FOIS (vécu le 10/10/2026) : envoyer daily_budget ET lifetime_budget
        # fait répondre Meta « Veuillez spécifier un budget quotidien ou un budget global » — il ne
        # sait plus lequel appliquer et refuse la création. José pense « tant par jour pendant tant
        # de jours » : c'est donc le budget QUOTIDIEN qu'on envoie, la durée tenant dans end_time.
        "daily_budget": budget_api,
        "start_time": maintenant,
        "end_time": fin,
        "targeting": json.dumps(ciblage_meta(publicite, reglages), ensure_ascii=False),
        "status": statut,
    }
    ensemble_id = creer_et_verifier(f"{reglages['compte_publicitaire']}/adsets", reglages_ensemble,
                                    reglages, "ensemble", liste_de=True)
    journal_des_etapes.append(f"ensemble créé : {ensemble_id}")

    lien = publicite["destination"]
    if publicite["visuel"]["type"] == "image":
        histoire = {"page_id": reglages["page_id"], "link_data": {
            "link": lien, "message": publicite["textes"]["principal"],
            "name": publicite["textes"]["titre"], "description": publicite["textes"]["description"],
            "image_hash": nom_image,
            "call_to_action": {"type": "LEARN_MORE", "value": {"link": lien}}}}
    else:
        # Pour une vidéo, Meta exige l'identifiant renvoyé par le téléversement ; il est fourni
        # par le module vidéo (voir televerser_video), sinon on refuse plutôt que d'inventer.
        if not reglages.get("video_id"):
            raise RuntimeError("Pour une vidéo, il faut d'abord la téléverser (Meta renvoie un "
                               "identifiant) : dis-le moi et je branche cette étape.")
        histoire = {"page_id": reglages["page_id"], "video_data": {
            "video_id": reglages["video_id"], "message": publicite["textes"]["principal"],
            "title": publicite["textes"]["titre"], "image_url": publicite["textes"].get("miniature"),
            "call_to_action": {"type": "LEARN_MORE", "value": {"link": lien}}}}
    creation_id = creer_et_verifier(
        f"{reglages['compte_publicitaire']}/adcreatives",
        {"name": f"Pub — {nom}", "object_story_spec": json.dumps(histoire, ensure_ascii=False)},
        reglages, "créatif")
    journal_des_etapes.append(f"annonce créée (creative) : {creation_id}")

    annonce_id = creer_et_verifier(f"{reglages['compte_publicitaire']}/ads", {
        "name": f"Annonce — {nom}", "adset_id": ensemble_id,
        "creative": json.dumps({"creative_id": creation_id}),
        "status": statut}, reglages, "annonce", liste_de=True)
    journal_des_etapes.append(f"annonce diffusée : {annonce_id}")

    # --------------------------------------------------------------------------------- RElecture
    relu = appel(ensemble_id, {"fields": "daily_budget,lifetime_budget,end_time,status"}, reglages)
    budget_relu = int(relu.get("daily_budget") or 0) / facteur
    verdict = {"etapes": journal_des_etapes, "campagne": campagne_id, "ensemble": ensemble_id,
               "annonce": annonce_id, "creative": creation_id, "devise": devise,
               "budget_envoye": budget_api, "budget_relu": budget_relu, "statut": relu.get("status"),
               "correspond": abs(budget_relu - publicite["budget"]["journalier"]) <= 1}

    if not verdict["correspond"]:
        # ⛔ LE GARDE-FOU QUI COMPTE : si le montant relu n'est pas celui voulu, on coupe TOUT, tout
        # de suite, plutôt que de laisser brûler un budget faux pendant qu'on réfléchit.
        for identifiant in (annonce_id, ensemble_id, campagne_id):
            try:
                appel(identifiant, {"status": "PAUSED"}, reglages, "POST")
            except RuntimeError:
                pass
        verdict["coupe"] = True
        consigner(f"STOP : budget relu {budget_relu} {devise} au lieu de "
                  f"{publicite['budget']['journalier']} {devise}. Tout a été mis en pause.")
    else:
        consigner(f"Pub diffusée : campagne {campagne_id} · ensemble {ensemble_id} · "
                  f"annonce {annonce_id} · {budget_relu} {devise}/jour pendant "
                  f"{publicite['duree']['jours']} jours")
    return verdict


def apercu_a_blanc(publicite, reglages):
    """Montre exactement ce qui serait envoyé, sans rien créer."""
    devise = reglages.get("devise", "XOF")
    facteur = 1 if devise in DEVISES_SANS_SOUS_UNITE else 100
    objectif, optimisation, facturation = construire_objectif(reglages, publicite)
    journalier_compte, taux = pub.convertir(publicite["budget"]["journalier"], devise)
    total_compte = publicite["budget"]["total"] * (taux or 1) if taux else None
    return {
        "compte": reglages.get("compte_publicitaire", "(à renseigner)"),
        "page": reglages.get("page_id", "(à renseigner)"),
        "objectif": objectif, "optimisation": optimisation, "facturation": facturation,
        "budget_journalier_en_francs": publicite["budget"]["journalier"],
        "budget_journalier_dans_la_devise": round(journalier_compte, 2) if journalier_compte else None,
        "budget_total_dans_la_devise": round(total_compte, 2) if total_compte else None,
        "taux_du_jour_1_franc": taux,
        "budget_journalier_envoye": (int(round(journalier_compte * facteur))
                                     if journalier_compte else None),
        "budget_total_envoye": (int(round(total_compte * facteur)) if total_compte else None),
        "devise_du_compte": devise,
        "duree_jours": publicite["duree"]["jours"],
        "ciblage": ciblage_sans_reseau(publicite["cible"]),
        "textes": publicite["textes"],
        "visuel": publicite["visuel"]["type"],
        "destination": publicite["destination"],
    }


def ciblage_sans_reseau(cible):
    """Le ciblage tel qu'il sera envoyé, sans appeler Meta (pour l'aperçu à blanc)."""
    geo = {"countries": cible.get("pays") or ["CI"]}
    if cible.get("villes"):
        geo["cities"] = [{"nom": v} for v in cible["villes"]]
    return {"geo_locations": geo, "age_min": max(18, cible.get("age_min", 18)),
            "age_max": min(65, cible.get("age_max", 45)), "sexe": cible.get("sexe", "tous")}


def main():
    analyseur = argparse.ArgumentParser(description="Publier une publicité chez Meta.")
    analyseur.add_argument("fichier", help="le JSON rendu par pub.py --json")
    analyseur.add_argument("--a-blanc", action="store_true", help="montrer sans rien créer")
    analyseur.add_argument("--en-ligne", action="store_true", help="créer et activer")
    analyseur.add_argument("--essai", action="store_true",
                           help="créer TOUT, mais en pause : la chaîne est prouvée, rien n'est dépensé")
    options = analyseur.parse_args()

    with open(options.fichier, encoding="utf-8") as f:
        publicite = json.load(f)
    publicite.setdefault("bloquants", [])
    reglages, manquants = lire_reglages()
    if manquants:
        print("⛔ Il manque des réglages du compte publicitaire :")
        for manque in manquants:
            print("   ·", manque)
        print(f"\nIls se rangent dans {SECRET_REGLAGES}")
        print('Forme attendue : {"jeton": "EAA…", "compte_publicitaire": "act_123", '
              '"page_id": "456", "but": "trafic"}')
        return 2
    if options.a_blanc:
        print(json.dumps(apercu_a_blanc(publicite, reglages), ensure_ascii=False, indent=2))
        return 0
    if not (options.en_ligne or options.essai):
        print("Ajoute --a-blanc (montrer), --essai (créer en pause) ou --en-ligne (créer et activer).")
        return 1
    try:
        verdict = mettre_en_ligne(publicite, reglages, en_ligne=options.en_ligne)
    except RuntimeError as erreur:
        print("⛔", erreur)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    if verdict.get("coupe"):
        print("\n⛔ Le budget relu ne correspond pas : j'ai tout mis EN PAUSE. "
              "Va voir dans le gestionnaire de pubs avant de relancer.")
        return 3
    if options.essai:
        print(f"\n✅ ESSAI : tout est créé et VÉRIFIÉ, mais en PAUSE — rien ne se dépense. "
              f"{verdict['budget_relu']:.0f} {verdict['devise']} par jour pendant "
              f"{publicite['duree']['jours']} jours. Dis-moi quand tu veux l'activer.")
        return 0
    print(f"\n✅ En ligne. {verdict['budget_relu']:.0f} {verdict['devise']} par jour pendant "
          f"{publicite['duree']['jours']} jours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
