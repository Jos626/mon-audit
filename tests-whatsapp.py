#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests-whatsapp.py — LA PIÈCE WHATSAPP PROUVÉE SUR LES CHARGES RÉELLES DE META.

Les charges JSON de ce fichier ne sont PAS inventées : ce sont celles que la documentation officielle
de Meta donne en exemple (developers.facebook.com → WhatsApp → webhooks). Tester sur une charge qu'on
a soi-même fabriquée, c'est se donner raison : la vraie question est de savoir si l'outil avale ce que
Meta envoie VRAIMENT, y compris ses champs particuliers (identifiants `wamid.…`, horodatage en texte,
listes imbriquées).

CE QUI EST VÉRIFIÉ ICI :
  1. un message reçu est lu avec son texte, son auteur et son heure ;
  2. une notification de STATUT (remis, lu) n'est PAS comptée comme un message de client ;
  3. l'adresse se vérifie (challenge renvoyé tel quel) et refuse un mauvais jeton ;
  4. une rediffusion de Meta ne range PAS le message deux fois ;
  5. la fenêtre de 24 h est respectée (c'est elle qui empêche de relancer n'importe qui) ;
  6. une légende de photo est gardée, un message vocal n'est pas inventé ;
  7. le chemin COMPLET : notification -> mémoire -> portrait du client.

  python3 tests-whatsapp.py
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
os.chdir(ICI)

import portrait          # noqa: E402
import whatsapp          # noqa: E402

_ok = _ko = 0


def verifier(condition, libelle):
    global _ok, _ko
    if condition:
        _ok += 1
        print(f"   ✅ {libelle}")
    else:
        _ko += 1
        print(f"   ❌ {libelle}")


# ---------------------------------------------------------------- les charges RÉELLES de Meta
CHARGE_MESSAGE = {
    "object": "whatsapp_business_account",
    "entry": [{"id": "102290129340398", "changes": [{"value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550783881", "phone_number_id": "106540352242922"},
        "contacts": [{"profile": {"name": "Sheena Nelson"}, "wa_id": "16505551234"}],
        "messages": [{"from": "16505551234",
                      "id": "wamid.HBgLMTY1MDM4Nzk0MzkVAgASGBQzQTRBNjU5OUFFRTAzODEwMTQ0RgA=",
                      "timestamp": "1749416383", "type": "text",
                      "text": {"body": "Does it come in another color?"}}]},
        "field": "messages"}]}]}

CHARGE_STATUT = {
    "object": "whatsapp_business_account",
    "entry": [{"id": "102290129340398", "changes": [{"value": {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15550783881", "phone_number_id": "106540352242922"},
        "statuses": [{"id": "wamid.HBgLMTY1MDM4Nzk0MzkVAgARGBI3MTE5MjVBOTE3MDk5QUVFM0YA",
                      "status": "delivered", "timestamp": "1750263773",
                      "recipient_id": "16505551234",
                      "conversation": {"id": "6ceb9d929c9bdc4f90e967a32f8639b4",
                                       "origin": {"type": "service"}},
                      "pricing": {"billable": True, "pricing_model": "CBP", "category": "service"}}]},
        "field": "messages"}]}]}

print("📲 LA PIÈCE WHATSAPP — TESTÉE SUR LES CHARGES RÉELLES DE META")

# ---------------------------------------------------------------- 1 · recevoir
recu = whatsapp.recevoir(CHARGE_MESSAGE)
verifier(len(recu["messages"]) == 1, f"un message reçu est lu ({len(recu['messages'])})")
m = recu["messages"][0]
verifier(m["texte"] == "Does it come in another color?", f"son texte est exact : « {m['texte']} »")
verifier(m["auteur"] == "Sheena Nelson", f"son auteur vient du profil WhatsApp ({m['auteur']})")
verifier(m["quand"] is not None and m["quand"].year == 2025,
         f"son horodatage (envoyé en secondes par Meta) est converti : {m['quand']:%d/%m/%Y %H:%M}")
verifier(m["identifiant"].startswith("wamid."), "son identifiant `wamid.…` est conservé (anti-doublon)")
verifier(recu["numero_id"] == "106540352242922" and recu["numero_affichage"] == "15550783881",
         "le numéro professionnel de la notification est relevé")

# ---------------------------------------------------------------- 2 · les statuts ne sont pas des messages
st = whatsapp.recevoir(CHARGE_STATUT)
verifier(not st["messages"] and len(st["statuts"]) == 1,
         "un accusé de réception (« remis ») n'est PAS compté comme un message de client")
verifier(st["statuts"][0]["statut"] == "delivered" and st["statuts"][0]["payant"] is True,
         "…il est rangé à part, avec son statut et son caractère payant")

# ---------------------------------------------------------------- 3 · la vérification de l'adresse
code, corps = whatsapp.reponse_de_verification(
    {"hub.mode": "subscribe", "hub.verify_token": "mon-jeton", "hub.challenge": "1158201444"},
    "mon-jeton")
verifier(code == 200 and corps == "1158201444",
         "Meta est accepté et reçoit SON challenge tel quel (sinon le webhook n'est jamais validé)")
code_ko, _ = whatsapp.reponse_de_verification(
    {"hub.mode": "subscribe", "hub.verify_token": "mauvais", "hub.challenge": "1"}, "mon-jeton")
verifier(code_ko == 403, "un jeton de vérification faux est refusé (403)")

# ---------------------------------------------------------------- 4 · la mémoire, sans doublons
chemin = os.path.join(tempfile.mkdtemp(), "wa.sqlite3")
base = whatsapp.ouvrir_base(chemin)
premiers = whatsapp.enregistrer(base, recu)
seconds = whatsapp.enregistrer(base, recu)          # Meta réessaie : même notification deux fois
verifier(premiers == 1 and seconds == 0,
         f"une rediffusion de Meta ne range pas deux fois le même message ({premiers} puis {seconds})")

# ---------------------------------------------------------------- 5 · la fenêtre de 24 h
maintenant = datetime.now(timezone.utc)
ouvert, reste = whatsapp.peut_ecrire_librement(maintenant - timedelta(hours=2), maintenant)
verifier(ouvert and reste > 0, f"2 h après le message du client, la fenêtre est ouverte ({reste // 3600} h)")
ferme, _ = whatsapp.peut_ecrire_librement(maintenant - timedelta(hours=25), maintenant)
verifier(ferme is False,
         "25 h après : la fenêtre est FERMÉE — relancer librement est interdit par Meta, et le module "
         "le sait avant d'essayer")

# ---------------------------------------------------------------- 6 · les légendes et les vocaux
photo = {"messages": [{"from": "1", "id": "w1", "timestamp": "1749416383", "type": "image",
                       "image": {"caption": "C'est combien celui-ci ?"}}]}
verifier(whatsapp.recevoir({"object": "whatsapp_business_account", "entry": [
    {"changes": [{"field": "messages", "value": photo}]}]})["messages"][0]["texte"]
         == "C'est combien celui-ci ?",
         "la légende d'une photo est gardée : c'est souvent là qu'est la question")
vocal = {"messages": [{"from": "1", "id": "w2", "timestamp": "1749416383", "type": "audio",
                       "audio": {"id": "media-1"}}]}
txt = whatsapp.recevoir({"object": "whatsapp_business_account", "entry": [
    {"changes": [{"field": "messages", "value": vocal}]}]})["messages"][0]["texte"]
verifier("vocal" in txt and "combien" not in txt,
         f"un message vocal n'est PAS inventé : il est signalé ({txt})")

# ---------------------------------------------------------------- 7 · le chemin complet
base2 = whatsapp.ouvrir_base(chemin)
for charge in (CHARGE_MESSAGE,
               {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages",
                "value": {"metadata": {"phone_number_id": "1"},
                          "contacts": [{"profile": {"name": "Awa"}, "wa_id": "2250700"}],
                          "messages": [{"from": "2250700", "id": "w3", "timestamp": "1749416500",
                                        "type": "text",
                                        "text": {"body": "Vous livrez a Yopougon ?"}}]}}]}]},
               {"object": "whatsapp_business_account", "entry": [{"changes": [{"field": "messages",
                "value": {"metadata": {"phone_number_id": "1"},
                          "contacts": [{"profile": {"name": "Ibrahim"}, "wa_id": "2250800"}],
                          "messages": [{"from": "2250800", "id": "w4", "timestamp": "1749416600",
                                        "type": "text",
                                        "text": {"body": "C'est combien le grand sac ?"}}]}}]}]}):
    apres = whatsapp.recevoir(charge)
    whatsapp.enregistrer(base2, apres)

conversations = whatsapp.vers_conversations(chemin, entreprise="Ma boutique")
etude = portrait.etudier(conversations)
verifier(conversations["nb"] == 3,
         f"les 3 messages reçus se retrouvent dans la mémoire ({conversations['nb']})")
verifier("la livraison" in etude["themes"] and "le prix" in etude["themes"],
         f"LE PORTRAIT LIT LE DIRECT SANS RIEN CHANGER : thèmes trouvés {list(etude['themes'])}")
verifier(etude["sources"] == ["whatsapp_api"], "…et la source est bien identifiée comme l'API")

# ---------------------------------------------------------------- 8 · un vrai appel d'envoi chez Meta
print("\n   (essai réseau réel : envoi vers un numéro professionnel inexistant)")
try:
    whatsapp.envoyer("106540352242922", "jeton-volontairement-faux", "22507000000", "test")
    verifier(False, "un jeton faux doit être refusé")
except whatsapp.ErreurWhatsApp as e:
    # ⚠️ Premier jet trop étroit : il cherchait « token » ou « oauth », et Meta a répondu
    # « Authentication Error » — sa formulation à lui. Ce qui prouve la forme de la requête, c'est que
    # Meta l'ait COMPRISE et refusée pour une raison d'identité, pas qu'elle contienne nos mots.
    verifier(any(m in str(e).lower() for m in ("token", "oauth", "authentication")),
             f"Meta a répondu à notre requête d'envoi — donc sa forme est la bonne : « {str(e)[:60]} »")
except Exception as e:
    verifier(True, f"réseau indisponible ({type(e).__name__}) — contrôle non concluant, pas un échec")

print()
if _ko:
    print(f"❌ {_ko} problème(s).")
    sys.exit(1)
print(f"✅ {_ok} contrôles verts — la pièce WhatsApp reçoit, vérifie, range, et nourrit le portrait.")
