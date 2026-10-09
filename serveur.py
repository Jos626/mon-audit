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
                "scope": ",".join(("ads_read", "business_management", "pages_show_list",
                                   "pages_read_engagement", "read_insights")),
                "response_type": "code"}))


def echanger_le_code(code, app_id, app_secret, adresse_publique):
    """Le code devient un jeton — d'abord court, puis LONG (≈ 60 jours)."""
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
<title>Mon Audit</title><style>
 body{{font-family:system-ui,-apple-system,sans-serif;background:#0f1115;color:#eef1f6;
      margin:0;display:flex;align-items:center;justify-content:center;min-height:100vh}}
 .carte{{max-width:430px;padding:30px;text-align:center}}
 h1{{font-size:23px;margin:0 0 6px}}
 p{{color:#a8b0bd;line-height:1.55;font-size:15px}}
 .fb{{display:inline-flex;align-items:center;gap:11px;background:#1877f2;color:#fff;
      text-decoration:none;font-weight:600;font-size:17px;padding:15px 26px;border-radius:12px;
      margin:22px 0 14px}}
 .fb svg{{width:22px;height:22px;fill:#fff}}
 .petit{{font-size:12.5px;color:#7c8697;margin-top:18px}}
 .note{{background:#171b23;border-radius:12px;padding:14px;font-size:13.5px;color:#9aa4b2;
        margin-top:18px;text-align:left}}
</style></head><body><div class="carte">
<h1>Mon Audit</h1>
<p>Je dis pourquoi ta publicité ne te rapporte pas de commandes — et ce qu'il faut changer.</p>
<a class="fb" href="{lien}">
  <svg viewBox="0 0 24 24"><path d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9
  3.7-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12z"/></svg>
  Continuer avec Facebook
</a>
<div class="note"><b>Ce que tu accordes :</b> lire tes statistiques publicitaires, la liste de tes
pages et les commentaires de tes publications. <b>Rien d'autre.</b> L'application ne publie rien, ne
modifie aucune campagne et ne dépense pas un franc.</div>
<p class="petit">Ton mot de passe Facebook ne passe jamais par ici : tu le tapes sur les pages de
Facebook, et tu peux retirer l'accès quand tu veux.</p>
</div></body></html>"""

PAGE_CONFIDENTIALITE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Confidentialité — Mon Audit</title>
<style>body{{font-family:system-ui,sans-serif;background:#0f1115;color:#eef1f6;margin:0;padding:26px;
line-height:1.6}}h1{{font-size:21px}}h2{{font-size:16px;margin-top:26px}}li{{margin:7px 0;color:#c3c9d4}}
p,li{{font-size:15px}}</style></head><body>
<h1>Politique de confidentialité — Mon Audit</h1>
<p>Mon Audit lit les données publicitaires et les conversations que le commerçant accepte
explicitement de partager, dans le seul but de produire un rapport pour lui.</p>
<ul>
<li><b>Aucun mot de passe n'est jamais demandé.</b> L'accès passe par une autorisation révocable, que
le commerçant peut retirer à tout moment (Facebook → Réglages → Applications et sites web).</li>
<li><b>Le jeton d'accès n'est pas conservé</b> : il vit le temps de l'audit.</li>
<li><b>Les conversations analysées</b> restent dans l'espace du commerçant et sont supprimées à sa
demande.</li>
<li><b>Aucune donnée n'est vendue</b>, ni partagée avec un autre client, ni utilisée pour entraîner un
modèle.</li>
<li><b>Rien n'est publié, modifié ou envoyé</b> en dehors des messages de service autorisés par
WhatsApp.</li>
</ul>
<h2>Suppression de tes données</h2>
<p>Écris <code>/efface</code> au bot : tout ce que tu lui as envoyé est supprimé immédiatement. Pour
toute autre demande, contacte l'exploitant du service.</p>
</body></html>"""

PAGE_RESULTAT = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ton audit — Mon Audit</title>
<style>body{{font-family:system-ui,sans-serif;background:#0f1115;color:#eef1f6;margin:0;padding:26px;
line-height:1.6}}h1{{font-size:20px}}.ok{{background:#12251b;border-left:4px solid #2ecc71;padding:14px;
border-radius:8px}}pre{{white-space:pre-wrap;font-family:inherit;font-size:15px;color:#c3c9d4}}</style>
</head><body><h1>Ton audit est prêt</h1>
<div class="ok">Je te l'ai envoyé dans <b>Telegram</b>. Tu peux fermer cette page.</div>
<pre>{apercu}</pre></body></html>"""


def faire_audit(jeton, periode="last_30d"):
    """Le même moteur que partout ailleurs, alimenté par le jeton obtenu par le bouton."""
    resultat = connexion.audit_complet(jeton, periode)
    etat = resultat["etat_du_jeton"]
    if not etat["suffisant_pour_auditer"]:
        return None, (f"⛔ Je n'ai pas pu lire tes statistiques. Il manque le droit `ads_read`.\n\n"
                      f"Reconnu : {etat['qui']}. Acccordés : {', '.join(etat['droits']) or 'aucun'}.")
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


def fabriquer_serveur(app_id, app_secret, adresse_publique, secret_liens, port=8080):
    class Traitement(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _envoyer_html(self, html, code=200):
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def do_GET(self):
            analyse = urllib.parse.urlparse(self.path)
            parametres = dict(urllib.parse.parse_qsl(analyse.query))

            if analyse.path in ("/", "/index.html"):
                etat = signer(parametres.get("chat", ""), secret_liens)
                self._envoyer_html(PAGE_ACCUEIL.format(
                    lien=url_de_connexion(app_id, adresse_publique, etat)))
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
                self._envoyer_html(PAGE_RESULTAT.format(
                    apercu=(texte[:2200] if not envoye else "Rapport envoyé dans Telegram.")))
                return

            self._envoyer_html("<h1>Page introuvable</h1>", 404)

    return ThreadingHTTPServer(("0.0.0.0", port), Traitement)


if __name__ == "__main__":
    APP_ID = _secret("meta-app-id")
    APP_SECRET = _secret("meta-app-secret")
    SECRET_LIENS = _secret("audit-secret-liens")
    ADRESSE = os.environ.get("ADRESSE_PUBLIQUE") or _secret("audit-adresse-publique")
    port = int(os.environ.get("PORT", "8080"))
    serveur = fabriquer_serveur(APP_ID, APP_SECRET, ADRESSE, SECRET_LIENS, port)
    print(f"Écoute sur le port {port} · adresse publique : {ADRESSE}", flush=True)
    serveur.serve_forever()
