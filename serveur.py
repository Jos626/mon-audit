#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""serveur.py — LA VRAIE PORTE D'ENTRÉE : « Continuer avec Facebook ». Un appui, l'audit démarre.

═══════════════════════════════════════════════════════════════════════════════════════════════════
POURQUOI CE FICHIER EXISTE.
═══════════════════════════════════════════════════════════════════════════════════════════════════

José l'a dit en une phrase : « Export WhatsApp et jeton Meta, c'est compliqué et long pour un débutant
et quelqu'un qui n'a pas le temps. Je veux que ça se passe en 1 clic vite fait et l'audit démarre. »

Il a raison. Le parcours par l'explorateur de Meta est un parcours de DÉVELOPPEUR (choisir une appli,
cocher cinq permissions, générer un jeton qui meurt en une heure). Un commerçant n'y va pas. Ce fichier
remplace ce parcours par le seul geste que tout le monde connaît : **appuyer sur « Continuer avec
Facebook »**.

TROIS CHOSES SONT VRAIES ET COMMANDENT TOUT LE RESTE :

  1. **Meta exige une adresse HTTPS PUBLIQUE de retour.** Un téléphone n'en a pas. C'est la seule vraie
     dépense du projet (un hébergement, à partir de gratuit ; ~5 $/mois pour du toujours-allumé utile au
     WhatsApp en direct). Sans elle, il n'existe AUCUN chemin en un appui — et on ne fera pas semblant.
  2. **Le mot de passe ne passe JAMAIS par nous.** Le commerçant le tape sur les pages de Facebook, et
     nous recevons un jeton révocable. C'est la même mécanique que « Se connecter avec Google ».
  3. **Le jeton est échangé contre un jeton LONG** (≈ 60 jours au lieu d'une heure). Sans cet échange,
     le client devrait recommencer chaque heure — ce qui ruinerait tout l'intérêt du un-appui.

COMMENT LE CLIENT REVIENT DANS SON TELEGRAM : le bot lui envoie un lien contenant son identifiant de
conversation, **signé**. Sans cette signature, n'importe qui pourrait fabriquer un lien et faire lire
le compte de quelqu'un d'autre (ou envoyer un rapport chez un autre). Le `state` est donc signé en
HMAC, et refusé s'il ne correspond pas.

AUCUNE DÉPENDANCE : tout est en bibliothèque standard. Un serveur qui a besoin de dix paquets est un
serveur qui tombe sur un hébergement minimal.
"""
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

import audit           # noqa: E402
import connexion       # noqa: E402
import rapport         # noqa: E402

VERSION_API = "v21.0"
GRAPH = f"https://graph.facebook.com/{VERSION_API}"

# ⚠️ JAMAIS DE SECRET DANS LE CODE. José les rangera dans ~/.hermes/secrets, et l'hébergement les
# fournira par variables d'environnement. Ici on lit, on ne code rien en dur.
SECRETS = os.path.expanduser("~/.hermes/secrets")


def _secret(nom, obligatoire=True):
    # ⚠️ CORRIGÉ le 09/10/2026 : `nom.upper()` seul cherchait « META-APP-ID », une variable
    # d'environnement IMPOSSIBLE à définir (les tirets sont interdits dans un nom de variable du
    # shell). Le serveur démarrait donc en annonçant qu'il manquait un réglage qu'on venait de lui
    # donner. Toute la configuration était inatteignable — trouvé en lançant la machine, pas en la
    # relisant.
    valeur = os.environ.get(nom.upper().replace("-", "_"))
    if not valeur:
        chemin = os.path.join(SECRETS, nom + ".txt")
        if os.path.exists(chemin):
            valeur = open(chemin, encoding="utf-8").read().strip()
    if not valeur and obligatoire:
        raise SystemExit(f"Il manque {nom} (variable d'environnement ou ~/.hermes/secrets/{nom}.txt)")
    return valeur


def url_de_connexion(app_id, adresse_publique, etat):
    """L'adresse du dialogue Facebook. C'est LE bouton que le commerçant appuie.

    Les permissions demandées sont exactement celles dont l'audit a besoin, et Meta les présente au
    client sur SES pages — il voit ce qu'il accorde, et il peut refuser.
    """
    return ("https://www.facebook.com/" + VERSION_API + "/dialog/oauth?" +
            urllib.parse.urlencode({
                "client_id": app_id,
                "redirect_uri": adresse_publique.rstrip("/") + "/callback",
                "state": etat,
                # ⛔ « read_insights » A ÉTÉ RETIRÉE LE 10/10/2026 — ELLE BLOQUAIT TOUT LE DIALOGUE.
                # Facebook répondait « Invalid Scopes: read_insights » et refusait d'afficher la page
                # d'autorisation : le bouton « Continuer avec Facebook » ne menait donc nulle part
                # (constaté par José sur son téléphone). Ce message n'apparaît qu'aux développeurs :
                # nos clients auraient vu une erreur incompréhensible, ou rien du tout.
                # read_insights n'est pas une permission de CONNEXION (elle se demande par une autre
                # voie). Les statistiques publicitaires, elles, viennent bien de « ads_read ».
                # LEÇON : une seule permission invalide fait échouer TOUTE la demande. Avant de
                # toucher à cette liste, tester le dialogue (voir tests-permissions-meta.py).
                "scope": ",".join(("ads_read", "business_management", "pages_show_list",
                                   "pages_read_engagement")),
                "response_type": "code"}))


def echanger_le_code(code, app_id, app_secret, adresse_publique):
    """Le code devient un jeton — d'abord court, puis LONG (≈ 60 jours)."""
    if not app_secret:
        raise ErreurGraph("La clé secrète de l'application n'est pas encore installée sur le "
                          "serveur : Meta ne peut pas échanger ce code contre un jeton.")
    court = _graph_get("oauth/access_token", {
        "client_id": app_id, "client_secret": app_secret, "code": code,
        "redirect_uri": adresse_publique.rstrip("/") + "/callback"})
    try:
        long_ = _graph_get("oauth/access_token", {
            "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
            "fb_exchange_token": court["access_token"]})
        return long_.get("access_token") or court["access_token"]
    except ErreurGraph:
        # ⚠️ L'ÉCHANGE LONG PEUT ÉCHOUER (application en développement, permission manquante) : on
        # garde alors le jeton court plutôt que d'échouer. Un audit qui marche une heure vaut mieux
        # qu'un écran d'erreur — et on le dira dans le rapport.
        return court["access_token"]


class ErreurGraph(Exception):
    pass


def _graph_get(chemin, parametres, timeout=40):
    url = f"{GRAPH}/{chemin}?" + urllib.parse.urlencode(parametres)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = (json.load(e) or {}).get("error", {})
            raise ErreurGraph(err.get("message", f"HTTP {e.code}"))
        except (ValueError, TypeError):
            raise ErreurGraph(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        raise ErreurGraph(f"Réseau injoignable : {e.reason}")


# ─────────────────────────────────────────────────────────── la signature du lien
def signer(chat_id, secret):
    """Le lien porte l'identifiant Telegram du client, SIGNÉ. Un lien forgé est refusé."""
    brut = f"{chat_id}.{int(time.time())}"
    signature = hmac.new(secret.encode(), brut.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{brut}.{signature}"


def verifier_etat(etat, secret, validite=3600):
    """Rend l'identifiant Telegram, ou None si le lien est forgé ou trop vieux."""
    try:
        chat_id, quand, signature = etat.rsplit(".", 2)
        attendu = hmac.new(secret.encode(), f"{chat_id}.{quand}".encode(),
                           hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(signature, attendu):
            return None
        if time.time() - int(quand) > validite:
            return None
        return chat_id
    except (ValueError, AttributeError):
        return None


# ─────────────────────────────────────────────────────────── les pages
PAGE_ACCUEIL = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mon Audit — pourquoi ta pub ne vend pas</title>
<link rel="manifest" href="/manifeste.json">
<meta name="theme-color" content="#f4f6fb">
<meta name="mobile-web-app-capable" content="yes">
<link rel="apple-touch-icon" href="/icone-apple-180.png">
<link rel="icon" type="image/png" href="/icone-192.png">
<!-- ⛔ CETTE PAGE EST EN THÈME CLAIR, ET LE RESTE MÊME SUR UN TÉLÉPHONE EN MODE SOMBRE.
     José, le 10/10/2026 : « Écris trop noir, faut revoir ! Je veux une vraie interface magnifique. »
     Le « color-scheme: light » ci-dessous est ce qui empêche le navigateur d'inverser les couleurs. -->
<style>
 :root{color-scheme:light}
 *{box-sizing:border-box}
 body{margin:0;background:
      radial-gradient(900px 420px at 50% -8%,#e5f6ec 0%,rgba(229,246,236,0) 62%),
      linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);
      color:#0f172a;min-height:100vh;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
      display:flex;align-items:center;justify-content:center;padding:26px 18px}
 .carte{width:100%;max-width:440px;background:#fff;border:1px solid #e8edf4;border-radius:22px;
        padding:34px 26px 26px;text-align:center;
        box-shadow:0 1px 2px rgba(15,23,42,.04),0 18px 44px -18px rgba(15,23,42,.18)}
 .logo{width:78px;height:78px;border-radius:20px;display:block;margin:0 auto 18px;
       box-shadow:0 10px 24px -10px rgba(15,23,42,.45)}
 .etiquette{display:inline-block;background:#e8f8ee;color:#15803d;font-size:12.5px;font-weight:700;
            padding:5px 12px;border-radius:999px;margin:0 0 14px;letter-spacing:.2px}
 h1{font-size:27px;line-height:1.2;margin:0 0 10px;letter-spacing:-.5px}
 .accroche{color:#475569;font-size:16px;line-height:1.6;margin:0 0 26px}
 .accroche b{color:#0f172a}
 .fb{display:flex;align-items:center;justify-content:center;gap:11px;width:100%;
     background:#1877f2;color:#fff;text-decoration:none;font-weight:700;font-size:17px;
     padding:17px 20px;border-radius:14px;box-shadow:0 10px 22px -10px rgba(24,119,242,.9);
     transition:transform .12s ease,box-shadow .12s ease}
 .fb:active{transform:translateY(1px);box-shadow:0 6px 14px -8px rgba(24,119,242,.9)}
 .fb svg{width:22px;height:22px;fill:#fff;flex:none}
 .rassurance{display:flex;gap:11px;text-align:left;margin:22px 0 0;padding:0;list-style:none}
 .rassurance li{color:#475569;font-size:14px;line-height:1.5}
 .coche{flex:none;width:20px;height:20px;border-radius:50%;background:#e8f8ee;color:#16a34a;
        font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center}
 .trait{height:1px;background:#eef2f7;margin:24px 0 16px}
 .petit{color:#8896a8;font-size:12.5px;line-height:1.6;margin:0 0 10px}
 .pied{color:#a3aebd;font-size:12px;margin:14px 0 0}
 .pied a{color:#8896a8}
</style></head><body><div class="carte">
<img class="logo" src="/icone-192.png" alt="Mon Audit" width="78" height="78">
<span class="etiquette">100 % gratuit</span>
<h1>Pourquoi ta pub ne vend pas</h1>
<p class="accroche">Je lis ton <b>compte publicitaire</b> et les <b>paroles de tes clients</b>.
Puis je te dis où part ton argent, ce qui bloque — et ce qu'il faut changer.</p>
<a class="fb" href="__LIEN__">
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9
  3.7-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12z"/></svg>
  Continuer avec Facebook
</a>
<ul class="rassurance">
 <li><span class="coche">✓</span><span>Rien n'est publié, rien n'est modifié chez toi, <b>pas un franc dépensé</b>.</span></li>
 <li><span class="coche">✓</span><span>Ton <b>mot de passe</b> Facebook ne passe jamais par ici.</span></li>
 <li><span class="coche">✓</span><span>Dès que tu accordes l'accès, tu peux le <b>retirer quand tu veux</b>.</span></li>
</ul>
<div class="trait"></div>
<p class="petit">📱 Pour la garder sous la main : menu ⋮ de ton navigateur →
« Ajouter à l'écran d'accueil ». Elle s'ouvrira comme une application.</p>
<p class="pied">Tes données restent les tiennes — <a href="/confidentialite">confidentialité</a>.</p>
</div></body></html>"""

PAGE_CONFIDENTIALITE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Confidentialité — Mon Audit</title>
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{color-scheme:light}
 body{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:26px 18px;line-height:1.65}
 .carte{max-width:560px;margin:0 auto;background:#fff;border:1px solid #e8edf4;border-radius:20px;
        padding:30px 26px;box-shadow:0 18px 44px -22px rgba(15,23,42,.18)}
 h1{font-size:23px;margin:0 0 4px} h2{font-size:16px;margin:24px 0 6px}
 p,li{color:#475569;font-size:14.5px} a{color:#1877f2}
 .date{color:#94a3b8;font-size:13px;margin:0 0 18px}
</style></head><body><div class="carte">
<h1>Confidentialité</h1>
<p class="date">Mon Audit — dernière mise à jour : 10 octobre 2026</p>
<h2>Ce que nous lisons</h2>
<p>Uniquement ce que le client autorise lui-même en se connectant avec Facebook : ses statistiques
publicitaires, la liste de ses pages et les commentaires de ses publications. Rien d'autre.</p>
<h2>Ce que nous ne faisons jamais</h2>
<p>Nous ne publions rien, ne modifions aucune campagne, ne dépensons aucun budget, et nous ne
demandons jamais le mot de passe Facebook. L'accès passe par les pages officielles de Facebook et
le client peut le retirer à tout moment.</p>
<h2>Où vont les données</h2>
<p>Le jeton d'accès vit le temps de l'audit et n'est pas conservé sur nos serveurs. Les rapports sont
envoyés par Telegram à la personne qui a lancé l'audit. Aucune donnée n'est revendue ni transmise à
un annonceur.</p>
<h2>Effacement</h2>
<p>La commande <b>/efface</b> du bot supprime les données enregistrées. Une demande peut aussi être
adressée directement à l'éditeur du service.</p>
</div></body></html>"""

PAGE_RESULTAT = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ton audit — Mon Audit</title>
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{color-scheme:light}
 body{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px 18px;line-height:1.65}
 .carte{max-width:620px;margin:0 auto;background:#fff;border:1px solid #e8edf4;border-radius:20px;
        padding:28px 24px;box-shadow:0 18px 44px -22px rgba(15,23,42,.18)}
 h1{font-size:22px;margin:0 0 14px}
 .ok{background:#e8f8ee;border-left:4px solid #22c55e;padding:14px 16px;border-radius:10px;
     color:#166534;font-size:15px}
 pre{white-space:pre-wrap;word-break:break-word;font-family:inherit;font-size:14.5px;color:#475569;
     background:#f7f9fc;border:1px solid #eef2f7;border-radius:12px;padding:16px;margin:16px 0 0}
</style></head><body><div class="carte"><h1>Ton audit est prêt</h1>
<div class="ok">Je te l'ai envoyé dans <b>Telegram</b>. Tu peux fermer cette page.</div>
<pre>__APERCU__</pre></div></body></html>"""


def faire_audit(jeton, periode="last_30d"):
    """Le même moteur que partout ailleurs, alimenté par le jeton obtenu par le bouton."""
    resultat = connexion.audit_complet(jeton, periode)
    etat = resultat["etat_du_jeton"]
    if not etat["suffisant_pour_auditer"]:
        # Message réécrit en français simple le 10/10/2026 : « Acccordés » (trois c) était une faute,
        # et « le droit ads_read » ne veut rien dire pour un e-commerçant.
        return None, ("⛔ Je n'ai pas pu lire tes statistiques : il manque l'autorisation de les "
                      "consulter.\n\n"
                      f"Compte reconnu : {etat['qui']}\n"
                      f"Autorisations reçues : {', '.join(etat['droits']) or 'aucune'}")
    if not resultat["lignes"]:
        return None, ("⛔ Je ne vois aucune dépense sur 30 jours — soit ce compte n'a rien dépensé, "
                      "soit il n'est pas dans ceux que tu as autorisés.")
    pseudo = {"total": {k: sum(l.get(k, 0) for l in resultat["lignes"])
                        for k in ("depense", "impressions", "clics", "resultats", "achats",
                                  "valeur_achats")} | {"lignes": len(resultat["lignes"])},
              "absentes": [], "souhaitees_absentes": []}
    noms = ", ".join(c.get("name", "?") for c in resultat["comptes"][:3])
    return (rapport.construire(audit.auditer(pseudo, {}), noms or "ton compte publicitaire")
            + "\n\n_Source : ton compte publicitaire, lu en direct (30 derniers jours). "
              "Ton jeton n'a pas été conservé._"), None


def _prevenir_telegram(chat_id, texte):
    """Envoyer le rapport dans la conversation Telegram du client. Se tait si le jeton du bot manque :
    un échec d'envoi ne doit pas casser l'audit, dont le résultat est déjà affiché à l'écran."""
    try:
        jeton_bot = _secret("telegram-bot-audit-token", obligatoire=False)
        if not jeton_bot:
            return False
        for i in range(0, len(texte), 3800):
            donnees = json.dumps({"chat_id": chat_id, "text": texte[i:i + 3800],
                                  "disable_web_page_preview": True}).encode()
            requete = urllib.request.Request(
                f"https://api.telegram.org/bot{jeton_bot}/sendMessage", data=donnees,
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(requete, timeout=40)
        return True
    except Exception:
        return False


# ─────────────────────────────────── l'application installable (PWA, 10/10/2026)
# CE QUE ÇA CHANGE POUR LE CLIENT, en une phrase : depuis son navigateur, deux appuis et « Mon Audit »
# s'ajoute à son écran d'accueil — avec son icône, en plein écran, comme une application. Sans magasin,
# sans rien à installer de compliqué, et sans frais. C'est ça, « l'appli installable » demandée.
# Chrome réclame trois choses pour l'autoriser : une adresse HTTPS (Render ✓), un MANIFESTE et un
# SERVICE WORKER. Les icônes sont de vrais PNG dessinés dans le projet (voir fabriquer-icones.py).
MANIFESTE = """{
 "name": "Mon Audit", "short_name": "Mon Audit", "lang": "fr",
 "start_url": "/", "scope": "/", "display": "standalone",
 "background_color": "#0f1115", "theme_color": "#0f1115",
 "description": "Dis pourquoi ta publicité ne te rapporte pas de commandes.",
 "icons": [
  {"src": "/icone-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
  {"src": "/icone-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
  {"src": "/icone-masquable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
 ]
}"""

# ⚠️ LE SERVICE WORKER NE MET RIEN EN CACHE — c'est un choix, pas un oubli. L'audit lit le compte
# publicitaire du client : une page resservie depuis un cache est une page qui peut mentir. Il ne sert
# qu'à rendre l'application installable.
SERVICE_WORKER = """self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});   // rien en cache : le réseau répond toujours
"""

FICHIERS_PWA = {"manifeste.json": ("application/manifest+json; charset=utf-8", MANIFESTE),
                "sw.js": ("text/javascript; charset=utf-8", SERVICE_WORKER)}
ICONES_PWA = ("icone-192.png", "icone-512.png", "icone-masquable-512.png",
              "icone-apple-180.png", "iparv.png")


def fabriquer_serveur(app_id, app_secret, adresse_publique, secret_liens, port=8080):
    class Traitement(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _envoyer_html(self, html, code=200):
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def _envoyer_octets(self, donnees, type_mime):
            self.send_response(200)
            self.send_header("Content-Type", type_mime)
            self.send_header("Content-Length", str(len(donnees)))
            self.end_headers()
            self.wfile.write(donnees)

        def do_GET(self):
            analyse = urllib.parse.urlparse(self.path)
            parametres = dict(urllib.parse.parse_qsl(analyse.query))

            # ── l'application installable : manifeste, service worker, icônes
            if analyse.path in ("/manifeste.json", "/sw.js"):
                type_mime, texte = FICHIERS_PWA[analyse.path.lstrip("/")]
                self._envoyer_octets(texte.encode(), type_mime)
                return

            if analyse.path.lstrip("/") in ICONES_PWA:
                try:
                    with open(os.path.join(ICI, analyse.path.lstrip("/")), "rb") as f:
                        self._envoyer_octets(f.read(), "image/png")
                except OSError:
                    self.send_error(404)
                return

            if analyse.path in ("/", "/index.html"):
                etat = signer(parametres.get("chat", ""), secret_liens)
                # ⚠️ ON REMPLACE UN JETON, ON NE FORMATTE PAS. La page contient de vraies accolades
                # CSS : un .format() dessus lèverait une KeyError (page cassée), et un .format() sans
                # ${} laisserait « __LIEN__ » en clair — le bouton « Continuer avec Facebook » ne
                # mènerait plus nulle part, exactement le défaut signalé par José.
                self._envoyer_html(PAGE_ACCUEIL.replace(
                    "__LIEN__", url_de_connexion(app_id, adresse_publique, etat)))
                return

            if analyse.path == "/confidentialite":
                self._envoyer_html(PAGE_CONFIDENTIALITE)
                return

            if analyse.path == "/callback":
                chat_id = verifier_etat(parametres.get("state", ""), secret_liens)
                if chat_id is None:
                    self._envoyer_html("<h1>Lien invalide ou expiré.</h1>"
                                       "<p>Demande un nouveau lien au bot.</p>", 403)
                    return
                if parametres.get("error"):
                    self._envoyer_html(f"<h1>Accès refusé</h1><p>{parametres['error']}</p>", 403)
                    return
                code = parametres.get("code")
                if not code:
                    self._envoyer_html("<h1>Réponse incomplète de Facebook.</h1>", 400)
                    return
                try:
                    jeton = echanger_le_code(code, app_id, app_secret, adresse_publique)
                    texte, erreur = faire_audit(jeton)
                except (ErreurGraph, connexion.ErreurMeta) as e:
                    texte, erreur = None, f"⛔ Facebook a refusé la demande : {str(e)[:200]}"
                if erreur or not texte:
                    self._envoyer_html(f"<h1>Je n'ai pas pu faire l'audit</h1><p>{erreur}</p>", 200)
                    return
                envoye = _prevenir_telegram(chat_id, texte)
                self._envoyer_html(PAGE_RESULTAT.replace(
                    apercu=(texte[:2200] if not envoye else "Rapport envoyé dans Telegram.")))
                return

            self._envoyer_html("<h1>Page introuvable</h1>", 404)

    return ThreadingHTTPServer(("0.0.0.0", port), Traitement)


if __name__ == "__main__":
    APP_ID = _secret("meta-app-id")
    # ⚠️ LA CLÉ SECRÈTE N'EST PAS EXIGÉE AU DÉMARRAGE (corrigé le 09/10/2026). Elle n'est utilisée
    # qu'à un seul endroit : l'échange du code contre un jeton, au retour du client. L'exiger ici
    # empêchait de Mettre le service en ligne avant de l'avoir — et le service aurait refusé de
    # démarrer pour une valeur dont il n'a pas besoin tant que personne ne se connecte. Elle est
    # désormais vérifiée au moment de l'usage, avec un message clair à ce moment-là.
    APP_SECRET = _secret("meta-app-secret", obligatoire=False)
    SECRET_LIENS = _secret("audit-secret-liens")
    ADRESSE = os.environ.get("ADRESSE_PUBLIQUE") or _secret("audit-adresse-publique")
    port = int(os.environ.get("PORT", "8080"))
    serveur = fabriquer_serveur(APP_ID, APP_SECRET, ADRESSE, SECRET_LIENS, port)
    print(f"Écoute sur le port {port} · adresse publique : {ADRESSE}", flush=True)
    serveur.serve_forever()
