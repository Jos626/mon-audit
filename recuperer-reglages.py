#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recuperer-reglages.py — le dernier maillon : le jeton arrive TOUT SEUL sur le téléphone.

POURQUOI CE FICHIER EXISTE. José, le 10/10/2026 : « Crée un bouton qui génère des jetons. Aucun
débutant n'ira chercher lui-même le jeton. » Le bouton existe (page « Créer mes publicités »), mais
obtenir un jeton ne suffit pas : il doit arriver jusqu'à la machine qui publiera les publicités —
ce téléphone. Le faire recopier à la main ruinerait tout l'intérêt du bouton.

CE SCRIPT VA DONC LE CHERCHER LUI-MÊME, et il est SILENCIEUX quand il n'y a rien à installer : il est
appelé par une tâche planifiée toutes les dix minutes, et une tâche qui parle pour ne rien dire se
fait couper par son destinataire.

⚠️ TROIS SILENCES ET UN SEUL CRI :
  · rien à récupérer        -> silence (le cas normal, 99 % du temps) ;
  · serveur endormi / réseau -> silence (le service gratuit s'endort : ce n'est pas une panne) ;
  · secret refusé (403)      -> SIGNALÉ : là, c'est vraiment cassé et il faut le savoir.

Usage : python3 recuperer-reglages.py
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ADRESSE = os.environ.get("PUBMETA_ADRESSE", "https://mon-audit.onrender.com")
CHEMIN_SECRET = os.path.expanduser("~/.hermes/secrets/audit-secret-liens.txt")
DESTINATION = os.path.expanduser("~/.hermes/secrets/meta-publicite.json")


def lire_secret():
    try:
        with open(CHEMIN_SECRET, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def main():
    secret = lire_secret()
    if not secret:
        print("⚠️ **Le secret partagé manque** : impossible de récupérer les réglages de publicité.")
        print("Dis-le à Laura : ce fichier doit exister — ~/.hermes/secrets/audit-secret-liens.txt")
        return 1

    url = f"{ADRESSE}/reglages?secret=" + urllib.parse.quote(secret)
    try:
        requete = urllib.request.Request(url, headers={"User-Agent": "Pubmeta/1.0"})
        with urllib.request.urlopen(requete, timeout=75) as reponse:
            charge = json.load(reponse)
    except urllib.error.HTTPError as erreur:
        if erreur.code == 403:
            print("⚠️ **Le serveur a refusé le secret partagé.** Rien ne peut s'installer tant que "
                  "ce secret ne correspond pas. Dis-le à Laura.")
            return 1
        return 0                      # autre refus : on ne réveille personne pour ça
    except Exception:                 # noqa: BLE001 — serveur endormi, réseau : silence
        return 0

    reglages = charge.get("reglages")
    if not reglages:
        return 0                      # rien à installer : SILENCE

    os.makedirs(os.path.dirname(DESTINATION), exist_ok=True)
    with open(DESTINATION, "w", encoding="utf-8") as f:
        json.dump(reglages, f, ensure_ascii=False, indent=2)
    os.chmod(DESTINATION, 0o600)

    print("✅ **Tes réglages de publicité sont installés.**")
    print(f"Compte : {reglages.get('compte_nom')} ({reglages.get('compte_publicitaire')})")
    print(f"Page : {reglages.get('page_nom')} ({reglages.get('page_id')})")
    print(f"Devise : {reglages.get('devise')}")
    print()
    print("Tu peux créer une publicité tout de suite — envoie-moi ta photo, ton idée, ton budget, "
          "ta durée et ta cible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
