"""Garde-fou de la LIVRAISON DU RAPPORT DANS LA PAGE (10/10/2026).

POURQUOI. José a décidé de supprimer le bot Telegram : « il va me fatiguer, également mes clients ».
Le bot ne servait qu'à livrer le rapport — la livraison est donc passée dans la page elle-même. Ce
fichier vérifie que le client reçoit bien quelque chose, et surtout que le contenu de son rapport ne
peut pas casser la page.

⚠️ LE CONTRÔLE LE PLUS IMPORTANT ICI EST CELUI DE L'ÉCHAPPEMENT. Le rapport contient des commentaires
de clients et des noms de campagnes écrits par d'autres. Affichés sans échappement, un simple « < »
casse la page, et un commentaire bavard peut y injecter du code. On le teste avec un vrai cas hostile.
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

PORT = 8971
JETON = "essai-de-livraison"
reussis, rates = [], []


def controle(libelle, condition, detail=""):
    (reussis if condition else rates).append(libelle)
    print(("   ✅ " if condition else "   ❌ ") + libelle + ("" if condition else f" — {detail}"))


def get(chemin):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{chemin}", timeout=15) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


print("📨 GARDE-FOU DE LA LIVRAISON DU RAPPORT DANS LA PAGE")
srv = S.fabriquer_serveur("1114320824585270", "secret-de-test", f"http://127.0.0.1:{PORT}", "essai",
                          port=PORT)
threading.Thread(target=srv.serve_forever, daemon=True).start()
time.sleep(0.6)

S.RAPPORTS[JETON] = {"etat": "en_cours", "quand": time.time()}
code, page = get(f"/attente?jeton={JETON}")
controle("la page d'analyse s'affiche", code == 200, f"code {code}")
controle("elle porte le jeton de l'analyse", JETON in page)
controle("aucun jeton de gabarit resté en clair", "__JETON__" not in page)
controle("elle se met à jour toute seule (le script de suivi est là)", "/etat?jeton=" in page)

code, corps = get(f"/etat?jeton={JETON}")
try:
    d = json.loads(corps)
    controle("l'état de l'analyse est un JSON lisible", d.get("etat") == "en_cours", corps[:80])
except Exception as e:
    controle("l'état de l'analyse est un JSON lisible", False, str(e))

# LE RAPPORT, AVEC UN CAS HOSTILE DEDANS
S.RAPPORTS[JETON] = {"etat": "pret", "quand": time.time(),
                     "texte": "Mon audit\n\n**Le problème** : ta campagne coûte trop cher.\n"
                              "Un client a écrit : <script>alert(1)</script> et ça compte."}
code, page = get(f"/resultat?jeton={JETON}")
controle("le rapport s'affiche dans la page", code == 200, f"code {code}")
controle("le gras est mis en forme", "<b>Le problème</b>" in page)
controle("le contenu du rapport ne peut pas exécuter de code (<script> échappé)",
         "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page)
controle("on peut l'enregistrer en PDF", "window.print()" in page)
controle("aucun jeton de gabarit resté en clair", "__RAPPORT__" not in page)

# ⚠️ ATTENTE RETOURNÉE le 10/10/2026 : un jeton inconnu n'est PAS un audit « en cours », c'est un
# lien EXPIRÉ (le rapport est oublié au bout d'une heure). Dire « pas encore prêt » à quelqu'un dont
# le rapport n'existe plus l'enverrait attendre pour rien. Les deux cas sont donc testés séparément.
code, page = get("/resultat?jeton=JETON-QUI-N-EXISTE-PAS")
controle("un lien expiré est annoncé comme tel", code == 404 and "expiré" in page, f"code {code}")
S.RAPPORTS[JETON] = {"etat": "en_cours", "quand": time.time()}
code, page = get(f"/resultat?jeton={JETON}")
controle("un audit encore en cours invite à le suivre", "pas encore prêt" in page and "/attente" in page,
         f"code {code}")
code, page = get("/attente?jeton=JETON-QUI-N-EXISTE-PAS")
controle("une analyse expirée est annoncée clairement", code == 404 and "expiré" in page, f"code {code}")

srv.shutdown()
print(f"\n{'✅' if not rates else '❌'} {len(reussis)} contrôles verts, {len(rates)} échec(s)")
sys.exit(1 if rates else 0)
