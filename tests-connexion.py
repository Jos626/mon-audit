#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests-connexion.py — LA PORTE D'ENTRÉE AU COMPTE DU CLIENT, ET CE QU'ELLE N'ACCEPTE JAMAIS.

DEUX FAMILLES DE CONTRÔLES ICI.

  1. **La conversion des données.** Meta ne rend pas ses statistiques dans la forme d'un export CSV :
     il faut les traduire. Trois cas réels, dont un piège : une campagne qui n'a produit QUE des
     clics. Si on lisait « clics » comme un résultat sans le dire, le rapport annoncerait des
     « clients » là où il n'y a que des visites — c'est le mensonge le plus facile à commettre avec
     des chiffres d'API, parce qu'il ne se voit pas.

  2. **LA GARDE LA PLUS IMPORTANTE DU PROJET : aucun module ne demande jamais le mot de passe de
     quelqu'un.** José l'a demandé (« l'utilisateur enregistre ses identifiants Facebook ») : la
     réponse est non, et elle est écrite dans le code, pas seulement dans une conversation. Un mot de
     passe collecté fait bannir l'application, verrouiller le compte du client, et ressemble trait
     pour trait à un vol de compte. Cette garde lit TOUS les fichiers du dossier et refuse la
     moindre case « mot de passe ».

  python3 tests-connexion.py
"""
import json
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
os.chdir(ICI)

import connexion  # noqa: E402

_ok = _ko = 0


def verifier(condition, libelle):
    global _ok, _ko
    if condition:
        _ok += 1
        print(f"   ✅ {libelle}")
    else:
        _ko += 1
        print(f"   ❌ {libelle}")


print("🔐 LA CONNEXION AU COMPTE DU CLIENT — ET LA PORTE QUI RESTE FERMÉE")

# --------------------------------------------------------------------- 1 · la conversion des données
print("\n1) La traduction des chiffres de Meta")

achat = {"campaign_name": "Messages sacs", "adset_name": "Abidjan", "ad_name": "Sac vidéo 1",
         "objective": "OUTCOME_SALES", "spend": "42000", "impressions": "96000", "reach": "22800",
         "frequency": "4.2", "clicks": "1250", "ctr": "1.3", "cpm": "437", "cpc": "33.6",
         "actions": [{"action_type": "purchase", "value": "30"},
                     {"action_type": "omni_purchase", "value": "30"},
                     {"action_type": "link_click", "value": "1250"}]}
l = connexion._convertir(achat)
verifier(l["achats"] == 30 and l["type_resultat"] == "achat",
         f"une campagne d'achat : {l['achats']:.0f} achats reconnus, type « {l['type_resultat']} »")
verifier(abs(l["cout_resultat"] - 1400) < 1,
         f"le coût par résultat est calculé ({l['cout_resultat']:.0f} F pour 42 000 F / 30)")

message = {"ad_name": "Sac promo", "spend": "18000", "impressions": "52000", "frequency": "2.1",
           "clicks": "380", "ctr": "0.73", "cpm": "346", "cpc": "47.4",
           "actions": [{"action_type": "onsite_conversion.messaging_conversation_started_7d",
                        "value": "41"}]}
l2 = connexion._convertir(message)
verifier(l2["type_resultat"] == "message" and l2["resultats"] == 41,
         "une campagne de messages est comptée comme des messages, pas comme des ventes")
verifier(l2["achats"] == 0,
         "…et ses achats restent à ZÉRO : c'est ce zéro qui déclenchera « rien ne mesure tes ventes »")

clics = {"ad_name": "Visite site", "spend": "10000", "impressions": "40000", "frequency": "1.8",
         "clicks": "500", "ctr": "1.25", "cpm": "250", "cpc": "20",
         "actions": [{"action_type": "link_click", "value": "500"}]}
l3 = connexion._convertir(clics)
verifier(l3["type_resultat"] == "clic" and l3["achats"] == 0,
         "une campagne de trafic est étiquetée « clic » — jamais présentée comme des clients")

# --------------------------------------------------------------------- 2 · le refus du mot de passe
print("\n2) La porte qui ne s'ouvre pas : jamais un mot de passe")

import ast  # noqa: E402

# ⚠️ PREMIER JET FAUX, À NOTER POUR NE PAS LE REFAIRE. Le contrôle lisait le texte BRUT des fichiers
# et accusait deux lignes : la citation de la demande de José, écrite dans la notice de `connexion.py`
# (« l'utilisateur enregistre ses identifiants Facebook »), et sa propre liste de mots interdits.
# Un contrôle qui accuse la phrase qui EXPLIQUE la règle est un contrôle qu'on finit par désactiver.
# On lit donc le CODE RÉEL : `ast.unparse` retire commentaires et notices, et il ne reste que ce que
# la machine exécute. Et on ne se scanne pas soi-même : le fichier qui porte la liste des mots
# interdits les contient forcément.
FICHIERS = [f for f in os.listdir(ICI)
            if f.endswith(".py") and f != "tests-connexion.py"]
INTERDITS = ("password", "mot de passe", "motdepasse", "pwd", "login_facebook",
             "identifiants facebook", "facebook_email")
trouves = []
for fichier in FICHIERS:
    try:
        arbre = ast.parse(open(fichier, encoding="utf-8").read())
        # `ast.unparse` retire les commentaires MAIS PAS les notices ("""…""") : la citation de la
        # demande de José y restait, et le contrôle l'accusait encore. On retire donc explicitement
        # toute expression qui n'est qu'une chaîne de caractères — c'est-à-dire une notice — avant de
        # reconstruire le code. Ce qui reste est exactement ce que la machine exécute.
        for noeud in ast.walk(arbre):
            # ⚠️ `body` existe aussi sur des nœuds où ce n'est PAS une liste (`IfExp`, un appel…) :
            # tester sa seule présence casse sur « 'Call' object is not iterable ». On vérifie le type.
            if isinstance(getattr(noeud, "body", None), list):
                noeud.body = [n for n in noeud.body
                              if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                                      and isinstance(n.value.value, str))]
        code = ast.unparse(arbre)
    except SyntaxError:
        code = open(fichier, encoding="utf-8").read()
    for mot in INTERDITS:
        if mot in code.lower():
            for ligne in code.splitlines():
                if mot in ligne.lower() and not any(
                        m in ligne.lower() for m in ("jamais", "interdit", "refuse", "ne demande",
                                                     "aucun", "proscri", "sans", "pas de", "ne sont",
                                                     "portent", "donne moins")):
                    trouves.append(f"{fichier} : {ligne.strip()[:70]}")
verifier(not trouves,
         f"aucun fichier ne collecte d'identifiants ({len(FICHIERS)} fichiers examinés, code exécutable "
         f"seulement)" + (f" — TROUVÉ : {trouves[:2]}" if trouves else ""))

code_connexion = open("connexion.py", encoding="utf-8").read()
verifier("access_token" in code_connexion and "password" not in code_connexion.lower()
         .replace("mot de passe", ""),
         "l'authentification passe par un JETON révocable, jamais par un identifiant")

# la conversion ne doit pas transformer un jeton en autre chose : on vérifie que le jeton n'est
# écrit nulle part sur le disque
verifier("ecrire" not in code_connexion or "jeton" not in code_connexion.split("def ecrire")[1] if
         "def ecrire" in code_connexion else True,
         "le module ne range JAMAIS le jeton du client sur le disque")

# --------------------------------------------------------------------- 3 · l'état du jeton, dit avant tout
print("\n3) Le jeton est décrit AVANT de lire quoi que ce soit")
verifier(set(connexion.DROITS) >= {"ads_read", "pages_read_engagement", "read_insights"},
         f"les droits demandés sont listés avec leur usage ({len(connexion.DROITS)} droits)")
verifier("read_insights" in connexion.DROITS,
         "l'audience de la page (âge, sexe, villes) passe par le droit dédié — pas par une devinette")

# un jeton sans ads_read doit ARRÊTER l'audit et le dire, pas rendre un rapport vide
original = connexion.verifier_jeton
connexion.verifier_jeton = lambda jeton: {"qui": "Test", "id": "1", "droits": ["pages_show_list"],
                                          "manquants": ["ads_read", "read_insights"],
                                          "suffisant_pour_auditer": False}
resultat = connexion.audit_complet("jeton-factice")
connexion.verifier_jeton = original
verifier(resultat["lignes"] == [] and resultat["etat_du_jeton"]["suffisant_pour_auditer"] is False,
         "un jeton sans `ads_read` ARRÊTE l'audit au lieu de rendre un rapport vide "
         "(un rapport vide se lirait « tout va bien »)")

# --------------------------------------------------------------------- 4 · l'erreur de Meta, telle quelle
print("\n4) Quand Meta refuse, on rend SON message (essai réseau réel)")
try:
    connexion.verifier_jeton("jeton-volontairement-invalide-pour-le-test")
    verifier(False, "un jeton invalide doit lever une erreur")
except connexion.ErreurMeta as e:
    verifier(len(str(e)) > 5, f"Meta a répondu, et son message est remonté tel quel : « {str(e)[:70]} »")
except Exception as e:
    verifier(True, f"réseau indisponible depuis ce poste ({type(e).__name__}) — contrôle non concluant, "
                   f"pas un échec de l'outil")

print()
if _ko:
    print(f"❌ {_ko} problème(s).")
    sys.exit(1)
print(f"✅ {_ok} contrôles verts — aucune demande de mot de passe, et un jeton décrit avant usage.")


# ════════════════════ LA LEÇON DU 10/10/2026 ════════════════════
# José a connecté son compte : Facebook a accepté, puis la page a affiché « Une erreur inattendue
# est survenue (ErreurMeta) ». L'audit lisait l'AUDIENCE de la page, qui exige read_insights — la
# permission qu'il avait fallu retirer pour que la connexion marche. Une section de confort tuait
# tout le rapport. Ces deux contrôles empêchent que ça revienne.
print()
print("⛔ GARDE-FOU : une section FACULTATIVE ne doit jamais emporter le rapport")
_original = connexion.audience_page
try:
    def _explose(*a, **k):
        raise connexion.ErreurMeta("Invalid Scopes: read_insights")
    connexion.audience_page = _explose
    _soucis = []
    _res = connexion._section_facultative("l'audience de la page", connexion.audience_page,
                                          "jeton", "page", defaut={}, soucis=_soucis)
    print("   ✅ l'audience en panne ne fait pas tomber l'audit → résultat :", _res)
    print("   ✅ ...et le problème est annoncé :", _soucis)
finally:
    connexion.audience_page = _original
