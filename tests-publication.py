"""tests-publication.py — verrouille les cinq pièges qui ont réellement coûté, le 10/10/2026.

Chaque test correspond à une erreur VÉCUE contre l'API Meta, pas à une hypothèse. Ils tournent sans
réseau : ce sont des règles de code, et une règle qui n'est pas testée se casse en silence au
prochain changement.
"""
import inspect
import io
import json
import sys
import urllib.error

import publication

# Les essais du code attendent 4 s entre deux tentatives (pour laisser respirer Meta) : inutile de
# faire patienter les tests, on neutralise l'attente.
publication.time.sleep = lambda _secondes: None
vrai_appel = publication.appel

reussites = []
echecs = []


def verifier(nom, condition, detail=""):
    (reussites if condition else echecs).append(nom)
    marque = "✓" if condition else "✗"
    print(f"  {marque} {nom}" + (f" — {detail}" if (detail and not condition) else ""))


print("\n=== 1. Un POST doit viser une SOUS-LISTE, jamais le compte lui-même ===")
print("    (la faute qui a renommé le compte de José en douce, avec un faux « success »)")


def faux_appel(chemin, parametres, reglages, methode="GET"):
    """Espion : note le chemin visé et rend un identifiant, comme Meta quand tout va bien."""
    faux_appel.vus.append(chemin)
    return {"id": "120253903100000001"}


faux_appel.vus = []
publication.appel = faux_appel
reglages_min = {"compte_publicitaire": "act_123", "jeton": "jeton-factice"}

for mauvais in ("act_123", "act_123/", "act_123/insights"):
    try:
        publication.creer_et_verifier(mauvais, {"name": "x"}, reglages_min, "campagne")
        verifier(f"le chemin « {mauvais} » est refusé", False, "il a été accepté !")
    except RuntimeError as erreur:
        verifier(f"le chemin « {mauvais} » est refusé", "sous-liste" in str(erreur))

verifier("aucun appel réseau n'est parti avant le refus", faux_appel.vus == [],
         f"appels partis : {faux_appel.vus}")

# et les bons chemins passent bien
for bon, quoi in (("act_123/campaigns", "campagne"), ("act_123/adsets", "ensemble"),
                  ("act_123/ads", "annonce"), ("act_123/adcreatives", "créatif")):
    try:
        publication.creer_et_verifier(bon, {"name": "x"}, reglages_min, quoi)
        verifier(f"le chemin « {bon} » est accepté", True)
    except RuntimeError as erreur:
        verifier(f"le chemin « {bon} » est accepté", False, str(erreur)[:60])

print("\n=== 2. Le ciblage ne demande jamais le pays ET la ville du même pays ===")
print("    (« Supprimez un lieu en conflit pour continuer »)")


def faux_appel_geo(chemin, parametres, reglages, methode="GET"):
    if chemin == "search":
        return {"data": [{"key": 12345, "name": "Abidjan"}]}
    return {"id": "999"}


publication.appel = faux_appel_geo
reglages_geo = {"compte_publicitaire": "act_123", "jeton": "j"}
pub_avec_ville = {"cible": {"pays": ["CI"], "villes": ["Abidjan"], "age_min": 18, "age_max": 40}}
ciblage = publication.ciblage_meta(pub_avec_ville, reglages_geo)
geo = ciblage["geo_locations"]
verifier("une ville trouvée remplace le pays", "cities" in geo and "countries" not in geo,
         f"geo = {geo}")
verifier("la ville porte bien sa clé Meta", geo.get("cities", [{}])[0].get("key") == 12345)

pub_sans_ville = {"cible": {"pays": ["CI"], "villes": [], "age_min": 18, "age_max": 40}}
ciblage2 = publication.ciblage_meta(pub_sans_ville, reglages_geo)
verifier("sans ville, on retombe sur le pays",
         "countries" in ciblage2["geo_locations"] and "cities" not in ciblage2["geo_locations"],
         f"geo = {ciblage2['geo_locations']}")

print("\n=== 3. Le ciblage dit toujours si la cible peut s'élargir toute seule ===")
print("    (Meta refuse la création sans cette réponse — Advantage Audience)")
verifier("advantage_audience est présent et désactivé",
         ciblage.get("targeting_automation", {}).get("advantage_audience") == 0,
         f"targeting_automation = {ciblage.get('targeting_automation')}")

print("\n=== 4. Un SEUL budget à la fois ===")
print("    (« Veuillez spécifier un budget quotidien ou un budget global »)")
source = inspect.getsource(publication.mettre_en_ligne)
bloc_ensemble = source.split("reglages_ensemble = {", 1)[1].split("\n    }", 1)[0]
a_quotidien = '"daily_budget":' in bloc_ensemble
a_global = '"lifetime_budget":' in bloc_ensemble
verifier("le budget quotidien est envoyé", a_quotidien, f"bloc : {bloc_ensemble[-160:]}")
verifier("le budget global n'est PAS envoyé en même temps", not a_global,
         "les deux partent ensemble : Meta refuse")

print("\n=== 5. Une erreur de Meta est retransmise EN ENTIER ===")
print("    (« Invalid parameter » ne dit pas quel paramètre : la précision est dans error_user_msg)")


class FausseReponse:
    def read(self):
        return json.dumps({"error": {
            "message": "Invalid parameter",
            "code": 100,
            "error_user_msg": "Le paramètre budget est invalide",
            "error_data": {"blame_field": "targeting"}}}).encode()


def appel_qui_echoue(requete, timeout=None):
    raise urllib.error.HTTPError("url", 400, "Bad Request", {}, io.BytesIO(FausseReponse().read()))


publication.urllib.request.urlopen = appel_qui_echoue
publication.appel = vrai_appel          # on retrouve la VRAIE fonction, pour tester ses erreurs
try:
    publication.appel("act_123/campaigns", {"name": "x"}, {"jeton": "j", "compte_publicitaire": "act_123"}, "POST")
    verifier("l'erreur remonte", False, "aucune erreur levée")
except RuntimeError as erreur:
    texte = str(erreur)
    verifier("l'erreur remonte", True)
    verifier("le message précis est conservé", "paramètre budget est invalide" in texte, texte[:80])
    verifier("le champ fautif est conservé", "targeting" in texte, texte[:80])

print(f"\n=== RÉSULTAT : {len(reussites)} réussite(s), {len(echecs)} échec(s) ===")
if echecs:
    for nom in echecs:
        print("  ✗", nom)
sys.exit(1 if echecs else 0)
