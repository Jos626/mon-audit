"""Garde-fou de l'ASSEMBLAGE : ce que Facebook rend doit pouvoir être compris par le moteur.

⛔ POURQUOI CE FICHIER EXISTE (10/10/2026). José a connecté son compte. Facebook a tout autorisé,
4 comptes publicitaires et 8 lignes de statistiques sont revenues — et le rapport a planté sur
`KeyError: 'lignes'`, parce que la clé était rangée à l'intérieur de « total » au lieu de la racine.
Deux fichiers contenaient la même faute (serveur.py et bot-audit.py), et AUCUN test ne reliait les
deux bouts : les tests appelaient la lecture d'un côté, le moteur de l'autre, jamais le passage
de l'un à l'autre.

C'est précisément ce passage que ce fichier vérifie — avec de fausses données, donc sans réseau,
sans jeton, et exécutable en une seconde.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import audit
import connexion

reussis, rates = [], []


def controle(libelle, condition, detail=""):
    (reussis if condition else rates).append(libelle)
    print(("   ✅ " if condition else "   ❌ ") + libelle + ("" if condition else f" — {detail}"))


# Une ligne exactement de la forme que _convertir produit à partir de l'API de Meta.
LIGNE = {"campagne": "Campagne A", "ensemble": "Ensemble 1", "pub": "Pub 1",
         "objectif": "OUTCOME_SALES", "type_resultat": "achat",
         "depense": 25000.0, "impressions": 40000.0, "portee": 22000.0, "frequence": 1.8,
         "clics": 600.0, "ctr": 1.5, "cpm": 625.0, "cpc": 41.67, "resultats": 12.0,
         "cout_resultat": 2083.33, "achats": 12.0, "valeur_achats": 0.0, "roas": 2.4}

print("🔗 GARDE-FOU DE L'ASSEMBLAGE — de Facebook jusqu'au moteur d'audit")

# la seconde ligne a un retour sur dépense DIFFÉRENT et une dépense plus petite : c'est ce qui permet
# de vérifier qu'on calcule bien une MOYENNE PONDÉRÉE (2,4×25000 + 1,0×10000) / 35000 = 2,0
# et non une somme (2,4 + 1,0 = 3,4) ni une moyenne simple (1,7).
resultat = {"lignes": [LIGNE, dict(LIGNE, depense=10000.0, achats=4.0, resultats=4.0, roas=1.0)],
            "comptes": [{"name": "Compte test"}], "soucis": []}
fiche = connexion.fiche_pour_le_moteur(resultat)

controle("la clé « lignes » est à la racine (le bug du 10/10/2026)",
         "lignes" in fiche and len(fiche["lignes"]) == 2)
controle("les trois clés que le moteur réclame sont là",
         {"total", "lignes", "absentes"} <= set(fiche), str(sorted(fiche)))
controle("le total additionne bien les lignes (dépense : 25 000 + 10 000)",
         fiche["total"].get("depense") == 35000.0, str(fiche["total"].get("depense")))
controle("les achats aussi (12 + 4)", fiche["total"].get("achats") == 16.0)
# ⚠️ ATTENTE RETOURNÉE le 10/10/2026 : le total sommait les rapports (2,4 + 1,0 = 3,4), ce qui ne
# veut rien dire. Il calcule désormais une MOYENNE PONDÉRÉE par l'argent engagé : 2,0.
controle("le retour sur dépense est une moyenne PONDÉRÉE (2,4×25 000 + 1,0×10 000) / 35 000 = 2,0",
         fiche["total"].get("roas") == 2.0, str(fiche["total"].get("roas")))
controle("les rapports ne sont jamais additionnés (le CTR est recalculé, pas sommé)",
         fiche["total"].get("ctr") == round(600 / 40040 * 100, 2), str(fiche["total"].get("ctr")))

# ⛔ LE CONTRÔLE QUI AURAIT ÉVITÉ L'ÉCHEC : on traverse réellement le moteur.
try:
    rapport = audit.auditer(fiche, {})
    controle("le moteur traverse l'assemblage sans planter", isinstance(rapport, dict)
             and "trouvailles" in rapport, str(sorted(rapport))[:90])
    controle("…et il a bien quelque chose à dire", len(rapport.get("trouvailles") or []) > 0,
             str(len(rapport.get("trouvailles") or [])))
except Exception as e:
    controle("le moteur traverse l'assemblage sans planter", False, f"{type(e).__name__}: {e}")

# Les cas limites, ceux qui arrivent vraiment : un compte neuf, un compte mal configuré.
vide = connexion.fiche_pour_le_moteur({"lignes": [], "comptes": []})
# ⚠️ ATTENTE RETOURNÉE AUSSI : un « total » VIDE faisait planter le moteur (`KeyError: 'depense'`).
# Désormais les champs connus partent à zéro — la forme est garantie pour le moteur.
controle("un compte sans aucune ligne donne des zéros, pas un vide",
         vide["lignes"] == [] and vide["total"].get("depense") == 0.0 and len(vide["total"]) >= 7,
         str(vide["total"]))
try:
    audit.auditer(vide, {})
    controle("…et le moteur le traverse aussi", True)
except Exception as e:
    controle("…et le moteur le traverse aussi", False, f"{type(e).__name__}: {e}")

incomplet = connexion.fiche_pour_le_moteur({"lignes": [{"depense": 5000.0}]})
controle("une ligne incomplète (champs manquants) passe sans planter",
         incomplet["total"].get("depense") == 5000.0)

print(f"\n{'✅' if not rates else '❌'} {len(reussis)} contrôles verts, {len(rates)} échec(s)")
sys.exit(1 if rates else 0)
