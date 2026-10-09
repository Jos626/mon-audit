#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests-portrait.py — LES RÈGLES DU PORTRAIT, VERROUILLÉES.

CE QUE CE FICHIER EMPÊCHE DE REVENIR. Chaque contrôle vient d'un défaut RÉEL rencontré en construisant
le module, pas d'une bonne intention :

  · un fichier de commentaires pris pour un export WhatsApp et rendant ZÉRO message en silence ;
  · les lignes système de WhatsApp (« chiffrés de bout en bout ») comptées comme des paroles de client ;
  · un message écrit sur trois lignes compté comme trois questions ;
  · un client qui écrit trois fois d'affilée compté comme trois clients ignorés ;
  · le mot « cadeau » compté comme une demande de remise ;
  · un vendeur DEVINÉ quand on ne peut pas le savoir — et donc des chiffres bâtis sur un rôle faux ;
  · un portrait qui décrit un âge ou un revenu, qu'aucune conversation ne contient.

Le dernier est le plus important : c'est la règle de José (« jamais de donnée inventée ») appliquée à
un portrait client. Un persona inventé produit des annonces inventées.
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
os.chdir(ICI)

import conversations   # noqa: E402
import portrait        # noqa: E402
import portrait_texte  # noqa: E402

_ok = _ko = 0


def verifier(condition, libelle):
    global _ok, _ko
    if condition:
        _ok += 1
        print(f"   ✅ {libelle}")
    else:
        _ko += 1
        print(f"   ❌ {libelle}")


WA = "exemples/whatsapp-boutique.txt"
ME = "exemples/messenger"
CO = "exemples/commentaires-page.txt"

print("🧑‍🤝‍🧑 LE PORTRAIT CLIENT — TROIS SOURCES, DES CHIFFRES, AUCUNE INVENTION")

# 1 · les trois sources, et le routage par le CONTENU (pas par l'extension)
c = conversations.lire([WA, ME, CO], vendeur="Boutique")
verifier(set(c["sources"]) == {"whatsapp", "messenger", "commentaires"},
         f"les trois sources sont lues ({', '.join(c['sources'])})")
c_wa = conversations.lire([WA], vendeur="Boutique")
verifier(c_wa["nb"] > 0, f"l'export WhatsApp donne bien des messages ({c_wa['nb']})")
c_co_seul = conversations.lire([CO])
verifier(c_co_seul["nb"] == 5,
         f"un fichier de commentaires en .txt n'est PAS pris pour du WhatsApp ({c_co_seul['nb']} lus)")

# 2 · les lignes système écartées
textes = " ".join(m["texte"].lower() for m in c["messages"])
verifier("chiffrés de bout en bout" not in textes and "a ajouté" not in textes,
         "les lignes système de WhatsApp ne sont pas comptées comme des paroles")
verifier(not any("a ajouté" in m["texte"].lower() for m in c["messages"]),
         "…y compris les ajouts de contact")

# 3 · le message sur plusieurs lignes compte UNE fois
multi = [m for m in c["messages"] if "je suis a Yopougon" in m["texte"] or "je suis à Yopougon" in m["texte"]]
verifier(len(multi) == 1 and "combien avec la livraison" in multi[0]["texte"],
         "un message écrit sur trois lignes reste UN SEUL message, entier")

# 4 · le vendeur n'est pas inventé
sans = conversations.lire([WA])
verifier(sans["vendeur"] is None,
         "sans que le commerçant le dise, le vendeur n'est PAS deviné quand le doute existe")
etude_sans = portrait.etudier(sans)
verifier(etude_sans["sans_reponse"] is None,
         "…et le comptage des clients ignorés est alors ANNONCÉ comme non établi, pas inventé")

# 5 · les ignorés : la fin de rafale, pas chaque message
etude = portrait.etudier(c)
if etude["sans_reponse"]:
    verifier(etude["sans_reponse"]["nombre"] < etude["nb_clients"] / 3,
             f"un client qui écrit plusieurs fois n'est compté qu'UNE fois ignoré "
             f"({etude['sans_reponse']['nombre']} sur {etude['nb_clients']})")

# 6 · « cadeau » n'est pas une demande de remise
exemple_cadeau = conversations.lire(["C'est combien le petit ? Je cherche un cadeau"])
e_cadeau = portrait.etudier(exemple_cadeau)
verifier("le dernier prix" not in e_cadeau["themes"],
         "« je cherche un cadeau » n'est pas compté comme une demande de remise")

# 7 · aucune invention dans le texte rendu
# ⚠️ PREMIER JET FAUX, ET IL FAUT LE DIRE : le contrôle cherchait « ans » comme une sous-chaîne, et
# tombait sur « dANS ». Il accusait le portrait d'une invention qui n'existait pas. Un contrôle qui
# crie au loup se fait désactiver « pour ne plus déranger » — donc on cherche des MOTS ENTIERS, et on
# écarte la seule phrase où ces mots ont le droit d'apparaître : l'avertissement lui-même.
import re  # noqa: E402

texte = portrait_texte.construire(etude)
AVERTISSEMENT = "aucun âge, aucun revenu"
corps = "\n".join(l for l in texte.splitlines() if AVERTISSEMENT not in l.lower())
for interdit in ("ans", "âge", "revenu", "salaire", "célibataire"):
    trouve = re.findall(r"(?<!\w)" + interdit + r"(?!\w)", corps, re.I)
    verifier(not trouve,
             f"le portrait ne décrit pas « {interdit} » ({len(trouve)} occurrence(s) hors "
             f"avertissement) — ça ne se lit pas dans un fil de discussion")
verifier(AVERTISSEMENT in texte.lower(),
         "…et l'avertissement qui dit ce qu'il REFUSE d'inventer est bien écrit au client")

# 8 · la prudence de volume
petit = conversations.lire(["C'est combien ?", "Vous livrez ?"])
e_petit = portrait.etudier(petit)
verifier(e_petit["assez"] is False and "trop peu" in portrait_texte.construire(e_petit).lower(),
         "sous 30 messages de clients, l'outil dit « trop peu pour un portrait sérieux »")

# 9 · le portrait s'appuie sur les chiffres réels
verifier(etude["themes"] and list(etude["themes"])[0] in ("la livraison", "le prix"),
         f"les demandes de prix et de livraison arrivent en tête ({list(etude['themes'])[:2]})")
verifier(etude["lieux"] and any(l in ("Yopougon", "Cocody", "Bouaké") for l, _n in etude["lieux"]),
         "les villes citées par les clients sont relevées")

print()
if _ko:
    print(f"❌ {_ko} problème(s) — un portrait faux fait écrire des annonces fausses.")
    sys.exit(1)
print(f"✅ {_ok} contrôles verts — trois sources lues, des chiffres, et rien d'inventé.")
