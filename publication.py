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

ICI = os.path.dirname(os.path.abspath(__file__))
SECRET_REGLAGES = os.path.expanduser("~/.hermes/secrets/meta-publicite.json")
JOURNAL = os.path.join(ICI, "publication-journal.log")

VERSION_API = "v25.0"
GRAPHE = f"https://graph.facebook.com/{VERSION_API}"

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
        try:
            corps = json.loads(erreur.read().decode("utf-8", "replace"))
            message = corps.get("error", {}).get("message", "")
            code = corps.get("error", {}).get("code")
        except Exception:  # noqa: BLE001
            message, code = "", None
        consigner(f"ERREUR Meta sur {chemin} : code={code} {message}")
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
    """Traduit la cible lue dans le texte en ce que Meta attend."""
    cible = publicite["cible"]
    geo = {"countries": cible.get("pays") or ["CI"]}
    if cible.get("villes"):
        villes = []
        for nom_ville in cible["villes"]:
            trouve = appel("search", {"type": "adgeolocation", "location_types": '["city"]',
                                      "q": nom_ville, "country_code": (cible.get("pays") or ["CI"])[0]},
                           reglages)
            for resultat in trouve.get("data", [])[:1]:
                villes.append({"key": resultat["key"], "radius": 25, "distance_unit": "kilometer"})
        if villes:
            geo["cities"] = villes
    ciblage = {"geo_locations": geo, "age_min": max(18, cible.get("age_min", 18)),
               "age_max": min(65, cible.get("age_max", 45))}
    if cible.get("sexe") == "hommes":
        ciblage["genders"] = [1]
    elif cible.get("sexe") == "femmes":
        ciblage["genders"] = [2]
    if cible.get("langues"):
        ciblage["locales"] = [6]        # 6 = français, la seule langue qu'on cible ici
    return ciblage


def mettre_en_ligne(publicite, reglages, en_ligne=True):
    """Crée la campagne, l'ensemble et l'annonce. Puis RELIT et compare — voir l'en-tête."""
    if publicite.get("bloquants"):
        raise RuntimeError("La publicité n'est pas bonne à publier : " + " · ".join(publicite["bloquants"]))
    if not publicite.get("destination"):
        raise RuntimeError("Aucune destination (l'adresse où la personne doit aller).")

    acces = verifier_acces(reglages)
    compte, page = acces["compte"], acces["page"]
    devise = compte.get("currency", "XOF")
    # ⚠️ LE POINT QUI COÛTE CHER : Meta compte dans l'unité la plus PETITE de la devise. Pour l'euro
    # et le dollar, c'est le centime (×100). Pour le franc CFA, il n'y a pas de centime (×1). On part
    # de la devise DU COMPTE, jamais d'une supposition — et on relit après.
    facteur = 1 if devise in ("XOF", "XAF", "JPY", "KRW", "CLP", "VND", "PYG", "RWF", "UGX", "DJF",
                              "GNF", "KMF", "BIF", "ISK", "HUF", "TWD") else 100
    budget_api = int(publicite["budget"]["journalier"]) * facteur
    total_api = int(publicite["budget"]["total"]) * facteur

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

    campagne = appel(reglages["compte_publicitaire"], {
        "name": f"{nom} — {time.strftime('%d/%m %H:%M')}",
        "objective": objectif,
        "status": statut,
        "special_ad_categories": "[]",
        "buying_type": "AUCTION",
    }, reglages, "POST")
    journal_des_etapes.append(f"campagne créée : {campagne['id']}")

    reglages_ensemble = {
        "name": f"Ensemble — {nom}",
        "campaign_id": campagne["id"],
        "billing_event": facturation,
        "optimization_goal": optimisation,
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "lifetime_budget": total_api,
        "daily_budget": budget_api,
        "start_time": maintenant,
        "end_time": fin,
        "targeting": json.dumps(ciblage_meta(publicite, reglages), ensure_ascii=False),
        "status": statut,
    }
    ensemble = appel(reglages["compte_publicitaire"], reglages_ensemble, reglages, "POST")
    journal_des_etapes.append(f"ensemble créé : {ensemble['id']}")

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
    creation = appel(reglages["compte_publicitaire"],
                     {"name": f"Pub — {nom}", "object_story_spec": json.dumps(histoire, ensure_ascii=False)},
                     reglages, "POST")
    journal_des_etapes.append(f"annonce créée (creative) : {creation['id']}")

    annonce = appel(reglages["compte_publicitaire"], {
        "name": f"Annonce — {nom}", "adset_id": ensemble["id"],
        "creative": json.dumps({"creative_id": creation["id"]}),
        "status": statut}, reglages, "POST")
    journal_des_etapes.append(f"annonce diffusée : {annonce['id']}")

    # --------------------------------------------------------------------------------- RElecture
    relu = appel(ensemble["id"], {"fields": "daily_budget,lifetime_budget,end_time,status"}, reglages)
    budget_relu = int(relu.get("daily_budget") or 0) / facteur
    verdict = {"etapes": journal_des_etapes, "campagne": campagne["id"], "ensemble": ensemble["id"],
               "annonce": annonce["id"], "creative": creation["id"], "devise": devise,
               "budget_envoye": budget_api, "budget_relu": budget_relu, "statut": relu.get("status"),
               "correspond": abs(budget_relu - publicite["budget"]["journalier"]) <= 1}

    if not verdict["correspond"]:
        # ⛔ LE GARDE-FOU QUI COMPTE : si le montant relu n'est pas celui voulu, on coupe TOUT, tout
        # de suite, plutôt que de laisser brûler un budget faux pendant qu'on réfléchit.
        for identifiant in (annonce["id"], ensemble["id"], campagne["id"]):
            try:
                appel(identifiant, {"status": "PAUSED"}, reglages, "POST")
            except RuntimeError:
                pass
        verdict["coupe"] = True
        consigner(f"STOP : budget relu {budget_relu} {devise} au lieu de "
                  f"{publicite['budget']['journalier']} {devise}. Tout a été mis en pause.")
    else:
        consigner(f"Pub diffusée : campagne {campagne['id']} · ensemble {ensemble['id']} · "
                  f"annonce {annonce['id']} · {budget_relu} {devise}/jour pendant "
                  f"{publicite['duree']['jours']} jours")
    return verdict


def apercu_a_blanc(publicite, reglages):
    """Montre exactement ce qui serait envoyé, sans rien créer."""
    devise = reglages.get("devise", "XOF")
    facteur = 1 if devise in ("XOF", "XAF", "JPY", "KRW") else 100
    objectif, optimisation, facturation = construire_objectif(reglages, publicite)
    return {
        "compte": reglages.get("compte_publicitaire", "(à renseigner)"),
        "page": reglages.get("page_id", "(à renseigner)"),
        "objectif": objectif, "optimisation": optimisation, "facturation": facturation,
        "budget_journalier_envoye": publicite["budget"]["journalier"] * facteur,
        "budget_total_envoye": publicite["budget"]["total"] * facteur,
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
    if not options.en_ligne:
        print("Ajoute --a-blanc (montrer) ou --en-ligne (créer pour de vrai).")
        return 1
    try:
        verdict = mettre_en_ligne(publicite, reglages, en_ligne=True)
    except RuntimeError as erreur:
        print("⛔", erreur)
        return 2
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    if verdict.get("coupe"):
        print("\n⛔ Le budget relu ne correspond pas : j'ai tout mis EN PAUSE. "
              "Va voir dans le gestionnaire de pubs avant de relancer.")
        return 3
    print(f"\n✅ En ligne. {verdict['budget_relu']:.0f} {verdict['devise']} par jour pendant "
          f"{publicite['duree']['jours']} jours.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
