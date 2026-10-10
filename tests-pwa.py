"""Garde-fou : l'application reste installable sur le téléphone du client.

POURQUOI CE FICHIER EXISTE. « Installable » dépend de trois choses que rien ne surveillait : un
manifeste servi au bon endroit, des icônes présentes, et un service worker. Si l'une disparaît
(un renommage, une route effacée), la page continue de s'afficher normalement — mais Chrome ne
propose plus « Ajouter à l'écran d'accueil », et personne ne s'en aperçoit avant un client.

On teste sur le VRAI serveur, lancé dans un fil, exactement comme en production.
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import serveur as S

PORT = 8951
reussis, rates = [], []


def controle(libelle, condition, detail=""):
    (reussis if condition else rates).append(libelle)
    print(("   ✅ " if condition else "   ❌ ") + libelle + ("" if condition else f" — {detail}"))


def get(chemin):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{chemin}", timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


print("📱 GARDE-FOU DE L'APPLICATION INSTALLABLE")
srv = S.fabriquer_serveur("1114320824585270", "", f"http://127.0.0.1:{PORT}", "essai", port=PORT)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(0.6)

code, corps = get("/manifeste.json")
controle("le manifeste répond 200", code == 200, f"code {code}")
try:
    m = json.loads(corps)
    controle("le manifeste est un JSON valide", True)
except Exception as e:
    m = {}
    controle("le manifeste est un JSON valide", False, str(e))
controle("il porte le nom de l'application", m.get("name") == "Mon Audit")
controle("il demande l'affichage en plein écran", m.get("display") == "standalone")
controle("il commence à la racine", m.get("start_url") == "/")
tailles = {i.get("sizes") for i in m.get("icons", [])}
controle("il propose une icône 192 et une 512", {"192x192", "512x512"} <= tailles, str(tailles))
controle("il propose une icône « masquable » (Android la redécoupe)",
         any(i.get("purpose") == "maskable" for i in m.get("icons", [])))

for icone in ("icone-192.png", "icone-512.png", "icone-masquable-512.png", "icone-apple-180.png"):
    code, corps = get("/" + icone)
    controle(f"{icone} existe et fait bien un PNG", code == 200 and corps[:4] == b"\x89PNG",
             f"code {code}")

code, corps = get("/sw.js")
controle("le service worker est servi (Chrome l'exige pour installer)", code == 200 and b"fetch" in corps)

code, page = get("/")
page = page.decode(errors="replace")
controle("la page déclare le manifeste", 'rel="manifest"' in page)
controle("la page a une icône pour iPhone", "apple-touch-icon" in page)
controle("la page dit au client comment l'installer", "Ajouter à l'écran" in page)

srv.shutdown()
print(f"\n{'✅' if not rates else '❌'} {len(reussis)} contrôles verts, {len(rates)} échec(s)")
sys.exit(1 if rates else 0)
