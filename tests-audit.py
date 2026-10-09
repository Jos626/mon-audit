#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests-audit.py — LES RÈGLES DU MOTEUR D'AUDIT, VERROUILLÉES.

POURQUOI CE FICHIER EXISTAIT PAS ENCORE, ET POURQUOI C'EST UN DÉFAUT. Le moteur d'audit est la pièce
principale de l'outil : c'est lui qui dit où part l'argent. Il avait été vérifié à l'œil, sur un seul
compte d'exemple. Un moteur qui accuse à tort coûte plus cher que pas de moteur du tout — le
commerçant coupe une campagne qui marchait, et il ne revient jamais.

CE QUI EST VERROUILLÉ ICI, ET CHAQUE CONTRÔLE VIENT D'UN RISQUE RÉEL :

  1. **UN COMPTE SAIN NE DÉCLENCHE RIEN.** C'est le contrôle le plus important : un audit qui crie au
     loup sur un compte correct se fait désinstaller dès la deuxième utilisation.
  2. **Le compte à problèmes déclenche LES BONNES alertes** — pas n'importe lesquelles.
  3. **Le tri se fait par ARGENT**, puis par gravité : le commerçant veut d'abord savoir où part son
     budget, pas la liste des bonnes pratiques.
  4. **Sous 30 résultats, aucun visuel n'est déclaré gagnant ou perdant** — même leçon que la mesure
     des paris : un écart sur un petit volume n'est pas une découverte.
  5. **Aucun montant inventé** : quand le coût n'est pas calculable, il n'y a pas de chiffre.
  6. **Les formats français** : « 100 000 », jamais « 100,000 » ; « 2,5 », jamais « 2.5 ».
  7. **Le piège des nombres d'Ads Manager** : les espaces insécables dans les milliers.

  python3 tests-audit.py
"""
import os
import re
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
os.chdir(ICI)

import audit       # noqa: E402
import lecture     # noqa: E402
import rapport     # noqa: E402

_ok = _ko = 0


def verifier(condition, libelle):
    global _ok, _ko
    if condition:
        _ok += 1
        print(f"   ✅ {libelle}")
    else:
        _ko += 1
        print(f"   ❌ {libelle}")


def compte(lignes):
    """Fabrique l'export minimal qu'un vrai fichier produirait, pour interroger le moteur seul."""
    return {"lignes": lignes, "trouvees": [], "absentes": [], "souhaitees_absentes": [],
            "total": {c: sum(l.get(c, 0) for l in lignes)
                      for c in ("depense", "impressions", "clics", "resultats", "achats",
                                "valeur_achats")} | {"lignes": len(lignes)}}


def ligne(pub, depense, resultats, cout=None, freq=1.8, ctr=1.5, objectif="achat",
          type_resultat="achat", achats=0, ensemble="Ensemble A"):
    return {"campagne": "Camp", "ensemble": ensemble, "pub": pub, "objectif": objectif,
            "type_resultat": type_resultat, "depense": depense, "impressions": depense * 6,
            "portee": depense * 4, "frequence": freq, "clics": depense // 30, "ctr": ctr,
            "cpm": 400, "cpc": 25, "resultats": resultats,
            "cout_resultat": cout if cout is not None else (depense / resultats if resultats else 0),
            "achats": achats, "valeur_achats": 0}


print("🔍 LE MOTEUR D'AUDIT — IL ACCUSE JUSTE, OU IL SE TAIT")

# ----------------------------------------------------------------------- 1 · un compte sain
print("\n1) Un compte qui marche : l'audit doit se taire")
sain = compte([
    ligne("Sac cuir - vidéo 1", 42000, 60, 700, freq=1.6, ctr=2.4, achats=60),
    ligne("Sac cuir - photo prix", 28000, 40, 700, freq=1.5, ctr=2.1, achats=40),
    ligne("Sac promo", 18000, 26, 692, freq=1.7, ctr=1.9, achats=26),
])
a_sain = audit.auditer(sain, {"marge": 5000, "fermeture": "site"})
verifier(not a_sain["critiques"],
         f"aucune alerte importante sur un compte sain ({len(a_sain['critiques'])} trouvée(s))")
verifier(a_sain["note_parfaite"] is True, "…et l'audit le dit explicitement")

# ----------------------------------------------------------------------- 2 · le compte à problèmes
print("\n2) Le compte à problèmes : les bonnes alertes, et pas d'autres")
malade = compte([
    ligne("Sac cuir - vidéo 1", 42000, 210, 200, freq=4.2, ctr=1.3, objectif="messages",
          type_resultat="Messages"),
    ligne("Sac promo -20%", 18000, 5, 3600, freq=2.1, ctr=0.73, objectif="messages",
          type_resultat="Messages"),
    ligne("Sac cuir - relance", 12600, 96, 131, freq=3.0, ctr=3.0, objectif="messages",
          type_resultat="Messages"),
    ligne("Sac cuir - vidéo 2", 15000, 34, 441, freq=2.8, ctr=0.88, objectif="messages",
          type_resultat="Messages"),
])
a_malade = audit.auditer(malade, {})
codes = {t["code"] for t in a_malade["trouvailles"]}
verifier("MESURE_VENTE_ABSENTE" in codes,
         "« rien ne mesure tes ventes » est signalé — le contrôle qui passe avant tous les autres")
verifier("OBJECTIF_LOIN_DE_LA_VENTE" in codes,
         "le budget qui ne vise pas la vente est signalé")
verifier("AUDIENCE_FATIGUEE" in codes, "la fréquence de 4,2 est signalée (la même personne, 4 fois)")
verifier("ANNONCES_QUI_BRULENT" in codes, "l'annonce à 3 600 F le résultat est signalée")
verifier("CE_QUI_MARCHE" in codes, "…et les annonces qui marchent sont nommées, pour ne pas y toucher")

# ----------------------------------------------------------------------- 3 · le tri par argent
print("\n3) Le tri : par argent d'abord")
argents = [t["argent"] for t in a_malade["trouvailles"] if t["argent"]]
verifier(argents == sorted(argents, reverse=True),
         f"les constats sont triés par montant décroissant ({[int(x) for x in argents[:3]]}…)")
verifier(a_malade["trouvailles"][0]["argent"] is not None,
         "le premier constat porte un montant : on commence par son argent, pas par la théorie")
verifier(a_malade["argent_en_jeu"] > 0,
         f"le total en jeu est calculé ({a_malade['argent_en_jeu']:,.0f} F)".replace(",", " "))

# ----------------------------------------------------------------------- 4 · la prudence de volume
print("\n4) Peu de résultats : personne n'est déclaré gagnant")
petit = compte([ligne("Sac A", 8000, 4, 2000, achats=4), ligne("Sac B", 5000, 3, 1667, achats=3)])
a_petit = audit.auditer(petit, {})
codes_petit = {t["code"] for t in a_petit["trouvailles"]}
verifier("TROP_PEU_DE_DONNEES" in codes_petit or "PEU_DE_RESULTATS" in codes_petit,
         "le manque de volume est annoncé comme tel")
verifier("CE_QUI_MARCHE" not in codes_petit,
         "…et aucune annonce n'est déclarée « gagnante » sur 7 résultats (c'est du hasard)")

# ----------------------------------------------------------------------- 5 · aucun montant inventé
print("\n5) Aucun chiffre inventé")
for t in a_malade["trouvailles"]:
    verifier(t["argent"] is None or t["argent"] > 0,
             f"« {t['titre'][:38]} » : montant positif ou absent, jamais négatif ni fabriqué")
sans_marge = [t for t in a_malade["trouvailles"] if t["code"] == "MARGE_DEPASSEE"]
verifier(not sans_marge,
         "sans la marge du client, l'outil NE déclare PAS « tu perds de l'argent » (il ne peut pas le savoir)")
# ⚠️ LA FIXTURE COMPTAIT 0 ACHAT : le contrôle de marge ne pouvait rien dire, et le test accusait le
# moteur. Un contrôle de refus ne vaut que si le CALCUL a été prouvé exécuté — il faut des achats pour
# comparer leur coût à une marge.
avec_achats = compte([
    ligne("Sac cuir - vidéo 1", 42000, 60, 700, achats=60),
    ligne("Sac cuir - photo", 28000, 40, 700, achats=40),
])
a_achats = audit.auditer(avec_achats, {"marge": 500, "panier": 15000, "fermeture": "site"})
marge_trouvee = [t for t in a_achats["trouvailles"] if t["code"] == "MARGE_DEPASSEE"]
verifier(bool(marge_trouvee),
         f"avec la marge donnée et de vraies commandes, il le déclare "
         f"({marge_trouvee[0]['argent']:,.0f} F perdus)".replace(",", " ") if marge_trouvee else
         "avec la marge donnée, il le déclare — et le chiffre est alors fondé")
verifier(not marge_trouvee or marge_trouvee[0]["preuves"]["cout_par_commande"] >
         marge_trouvee[0]["preuves"]["marge"],
         "…et le constat porte le calcul qui le fonde (coût par commande face à la marge)")

# ----------------------------------------------------------------------- 6 · les formats français
print("\n6) Les formats d'écriture")
texte = rapport.construire(a_malade, "Compte test")
# ⚠️ L'écriture française utilise une ESPACE FINE INSÉCABLE (\u202f) entre les milliers, pas l'espace
# ordinaire du clavier. Le contrôle comparait « 100 000 » (espace normale) et échouait donc alors que
# l'affichage était juste. On normalise AVANT de comparer — sans jamais accepter la virgule anglaise.
# ⚠️ Deuxième jet encore faux : il cherchait le nombre « 100 000 » dans un compte qui n'en contient
# aucun. On vérifie la RÈGLE, pas un chiffre : aucune virgule de milliers à l'anglaise, et un vrai
# séparateur français là où il y a des milliers.
import re as _re  # noqa: E402

anglais = _re.findall(r"\d,\d{3}", texte)
verifier(not anglais,
         f"aucun montant à l'anglaise (virgule de milliers) dans le rapport — trouvés : {anglais[:3]}")
milliers = _re.findall(r"\d[ \u202f\u00a0]\d{3}", texte)
verifier(len(milliers) > 0,
         f"les milliers sont écrits à la française ({len(milliers)} montants, ex. « {milliers[0]} »)")
verifier("2.5" not in texte and "4.2" not in texte,
         "les décimales aussi (2,5 et 4,2, pas 2.5 et 4.2)")
verifier("F CFA" in texte, "la monnaie est nommée")

# ----------------------------------------------------------------------- 7 · le piège des nombres
print("\n7) Le piège des nombres d'Ads Manager (espaces insécables)")
NB = "\u00a0"
fichier = os.path.join(tempfile.mkdtemp(), "export.csv")
with open(fichier, "w", encoding="utf-8-sig") as f:
    f.write("Nom de la campagne;Nom de l'ensemble de publicités;Nom de la publicité;"
            "Montant dépensé;Impressions;Résultats;Coût par résultat;Achats\n")
    f.write(f"C;Ens;Pub A;12{NB}500;50{NB}000;25;500;25\n")
    f.write(f"C;Ens;Pub B;7{NB}500;30{NB}000;15;500;15\n")
lue = lecture.lire(fichier)
verifier(lue["total"]["depense"] == 20000,
         f"« 12 500 » avec espace insécable est lu 12500, pas 12 ni 0 (total : {lue['total']['depense']:.0f})")
verifier(lue["total"]["resultats"] == 40, f"et les résultats totalisent 40 ({lue['total']['resultats']:.0f})")

print()
if _ko:
    print(f"❌ {_ko} problème(s) — un audit qui accuse à tort coûte plus cher que pas d'audit.")
    sys.exit(1)
print(f"✅ {_ok} contrôles verts — il accuse juste, il se tait quand il faut, et il ne fabrique rien.")
