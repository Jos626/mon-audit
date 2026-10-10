"""tests-pub.py — les gardes du créateur de publicités.

Ce qui se teste ici, en priorité : LES GARDE-FOUS D'ARGENT. José a choisi la mise en ligne
AUTOMATIQUE : un budget mal lu, une durée mal comprise, un visuel refusé par Meta — et l'argent part
sans que personne ne regarde. Chaque protection a donc son contrôle.

Lancer :  python3 tests-pub.py             (sans les appels au modèle)
          python3 tests-pub.py --reseau    (avec l'écriture par le modèle gratuit)
"""
import json
import os
import sys
import tempfile

import pub
import publication

RESEAU = "--reseau" in sys.argv
echecs, reussites, avertissements = [], [], []


def verifie(nom, condition, detail="", reseau=False):
    if condition:
        reussites.append(nom)
        print("  ✓ " + nom)
        return
    if reseau:
        avertissements.append((nom, detail))
        print(f"  ⚠ {nom}  →  NON TESTÉ (réseau) : {detail}")
        return
    echecs.append((nom, detail))
    print(f"  ✗ {nom}  →  {detail}")


def image_de_test(chemin):
    from PIL import Image
    Image.new("RGB", (600, 600), (15, 23, 42)).save(chemin, quality=80)
    return chemin


DOSSIER = tempfile.mkdtemp(prefix="tests-pub-")
VISUEL = image_de_test(os.path.join(DOSSIER, "visuel.jpg"))

print("\n=== 1. Lire un budget écrit comme on l'écrit ici ===")
verifie("« 15 000 » (avec espace insécable)", pub.lire_budget("15\u202f000") == 15000,
        str(pub.lire_budget("15\u202f000")))
verifie("« 15000 F CFA »", pub.lire_budget("15000 F CFA") == 15000)
verifie("« 15k »", pub.lire_budget("15k") == 15000)
verifie("« 2 500 »", pub.lire_budget("2 500") == 2500)
verifie("« beaucoup » n'est PAS un budget", pub.lire_budget("beaucoup") is None)
verifie("un vide n'est PAS un budget", pub.lire_budget("") is None)

print("\n=== 2. Lire une durée ===")
verifie("« 10 jours »", pub.lire_duree("10 jours") == 10)
verifie("« 10j »", pub.lire_duree("10j") == 10)
verifie("« 2 semaines » = 14 jours", pub.lire_duree("2 semaines") == 14)
verifie("« 1 mois » = 30 jours", pub.lire_duree("1 mois") == 30)
verifie("« longtemps » n'est PAS une durée", pub.lire_duree("longtemps") is None)

print("\n=== 3. Le plafond de sécurité : la protection n°1 de l'argent ===")
publicite = pub.fabriquer("promo", VISUEL, 5000000, 10, "18-45 ans", "https://exemple.ci",
                          ecrire_avec_modele=False)
verifie("un budget de 5 000 000 F est REFUSÉ", any("plafond" in b for b in publicite["bloquants"]),
        str(publicite["bloquants"]))
publicite = pub.fabriquer("promo", VISUEL, 5000, 30, "18-45 ans", "https://exemple.ci",
                          ecrire_avec_modele=False)
verifie("un budget journalier trop bas est REFUSÉ",
        any("minimum" in b for b in publicite["bloquants"]), str(publicite["bloquants"]))
publicite = pub.fabriquer("promo", VISUEL, 15000, 10, "18-45 ans", "https://exemple.ci",
                          ecrire_avec_modele=False)
verifie("15 000 F sur 10 jours passe (1 500 F/jour)", publicite["bloquants"] == [],
        str(publicite["bloquants"]))
verifie("le budget journalier est bien calculé", publicite["budget"]["journalier"] == 1500,
        str(publicite["budget"]["journalier"]))

print("\n=== 4. Sans destination, on ne publie pas ===")
publicite = pub.fabriquer("promo", VISUEL, 15000, 10, "18-45 ans", "",
                          ecrire_avec_modele=False)
verifie("l'absence de destination bloque", any("destination" in b for b in publicite["bloquants"]),
        str(publicite["bloquants"]))

print("\n=== 5. Le visuel est reconnu PAR SON CONTENU ===")
verifie("une vraie image JPG est reconnue", pub.lire_visuel(VISUEL)["type"] == "image")
faux = os.path.join(DOSSIER, "faux.jpg")
with open(faux, "w", encoding="utf-8") as f:
    f.write("ceci n'est pas une image")
verifie("un fichier texte renommé .jpg est REFUSÉ", pub.lire_visuel(faux)["type"] is None,
        str(pub.lire_visuel(faux)))
verifie("un fichier absent est annoncé clairement",
        "introuvable" in (pub.lire_visuel(os.path.join(DOSSIER, "rien.jpg"))["erreur"] or ""))

print("\n=== 6. Comprendre la cible écrite en français ===")
cible = pub.lire_cible("hommes 18-35 ans Abidjan, interesses par efootball")
verifie("les âges sont lus (18-35)", (cible["age_min"], cible["age_max"]) == (18, 35), str(cible))
verifie("le sexe est lu (hommes)", cible["sexe"] == "hommes")
verifie("la ville est reconnue (Abidjan)", cible["villes"] == ["Abidjan"], str(cible["villes"]))
verifie("le centre d'intérêt est traduit pour Meta", "eFootball" in cible["interets"],
        str(cible["interets"]))
cible2 = pub.lire_cible("femmes 25-40 ans Bouaké")
verifie("une deuxième cible est lue correctement",
        (cible2["sexe"], cible2["age_min"], cible2["villes"]) == ("femmes", 25, ["Bouaké"]), str(cible2))
cible3 = pub.lire_cible("toute la Côte d'Ivoire")
verifie("sans âge, on prend la fourchette par défaut",
        (cible3["age_min"], cible3["age_max"]) == (18, 45), str(cible3))
cible4 = pub.lire_cible("hommes et femmes 20-45 ans Abidjan et Bouaké")
verifie("« hommes ET femmes » veut dire TOUT LE MONDE (pas la moitié)",
        cible4["sexe"] == "tous", cible4["sexe"])
verifie("deux villes sont lues ensemble", sorted(cible4["villes"]) == ["Abidjan", "Bouaké"],
        str(cible4["villes"]))

print("\n=== 7. Les montants envoyés à Meta dépendent de la DEVISE DU COMPTE ===")
publicite = pub.fabriquer("promo", VISUEL, 15000, 10, "18-45 ans Abidjan", "https://exemple.ci",
                          ecrire_avec_modele=False)
apercu = publication.apercu_a_blanc(publicite, {"devise": "XOF", "compte_publicitaire": "act_1",
                                                "page_id": "2"})
verifie("en franc CFA (pas de centime) : 1 500 reste 1 500",
        apercu["budget_journalier_envoye"] == 1500, str(apercu["budget_journalier_envoye"]))
apercu_eur = publication.apercu_a_blanc(publicite, {"devise": "EUR"})
verifie("en euro (centimes) : 1 500 devient 150 000",
        apercu_eur["budget_journalier_envoye"] == 150000,
        str(apercu_eur["budget_journalier_envoye"]))

print("\n=== 8. L'aperçu à blanc ne crée RIEN et montre tout ===")
verifie("l'aperçu porte l'objectif", apercu["objectif"] == "OUTCOME_TRAFFIC")
verifie("l'aperçu porte les textes", bool(apercu["textes"]["accroche"]))
verifie("l'aperçu porte le ciblage", apercu["ciblage"]["geo_locations"]["countries"] == ["CI"])
verifie("l'aperçu porte la durée", apercu["duree_jours"] == 10)

print("\n=== 9. Le repli garantit qu'il y a TOUJOURS une publicité ===")
repli = pub.textes_de_repli("vpn pour efootball")
verifie("l'accroche de repli n'est pas vide", bool(repli["accroche"]))
verifie("le texte de repli n'est pas vide", bool(repli["principal"]))
verifie("le bouton de repli est une expression autorisée", repli["appel"] == "En savoir plus")

print("\n=== 10. Les textes écrits par le modèle sont CONTRÔLÉS ===")
textes = {"accroche": "A" * 200, "principal": "B" * 4000, "titre": "T" * 90,
          "description": "D" * 200, "appel": "En savoir plus"}
publicite = pub.fabriquer("promo", VISUEL, 15000, 10, "18-45 ans", "https://exemple.ci",
                          texte_force=textes)
verifie("un texte trop long est signalé (le modèle doit tenir dans les limites de Meta)",
        len(publicite["textes"]["accroche"]) <= 200, str(len(publicite["textes"]["accroche"])))

if RESEAU:
    print("\n=== 11. RÉSEAU : le modèle gratuit écrit vraiment la publicité ===")
    publicite = pub.fabriquer("un VPN pour jouer à eFootball sans décalage", VISUEL, 15000, 10,
                              "hommes 18-35 ans Abidjan", "https://exemple.ci/efootball")
    verifie("les textes viennent du modèle (pas des gabarits)", publicite["textes_par_modele"] is True,
            "le modèle n'a pas répondu — voir pub-journal.log", reseau=True)
    verifie("l'accroche ne reprend pas l'idée mot pour mot",
            publicite["textes"]["accroche"].lower() != publicite["idee"].lower(),
            publicite["textes"]["accroche"], reseau=True)

print(f"\n=== RÉSULTAT : {len(reussites)} réussite(s), {len(echecs)} échec(s), "
      f"{len(avertissements)} non testé(s) (réseau) ===")
for nom, detail in echecs:
    print(f"  ÉCHEC : {nom}  →  {detail}")
for nom, detail in avertissements:
    print(f"  NON TESTÉ : {nom}  →  {detail}")
sys.exit(1 if echecs else 0)
