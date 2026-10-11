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
import threading      # l'audit tourne dans un fil : le client n'attend pas dans une requête web
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

import audit           # noqa: E402
import connexion       # noqa: E402
import pages as pages_meta   # noqa: E402 — les Pages du client et leurs publications déjà en ligne
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


DROITS_AUDIT = ("ads_read", "business_management", "pages_show_list", "pages_read_engagement")
# ⛔⛔ POUR CREER ET DIFFUSER DES PUBLICITES, IL FAUT LE DROIT DE *GERER*, PAS SEULEMENT DE LIRE.
# José, le 10/10/2026 : « Crée un bouton qui génère des jetons. Aucun débutant n'ira chercher lui-même
# le jeton. » Ce parcours remplace l'explorateur de Meta par UN appui.
#
# ⚠️⚠️ « pages_manage_ads » A ETE RETIREE LE 10/10/2026 — ELLE BLOQUAIT TOUT LE DIALOGUE.
# José l'a constaté sur son téléphone : « Invalid Scopes: pages_manage_ads ». Une seule permission que
# l'application ne peut pas demander fait échouer TOUTE la page d'autorisation — le bouton ne mène
# nulle part, et le client, lui, ne verrait même pas le message (il n'est montré qu'aux développeurs).
# La documentation de Meta est claire : pour « créer et gérer des annonces », cette permission est
# OPTIONNELLE ; les permissions REQUISES sont celles ci-dessous. On demande le strict nécessaire.
DROITS_PUBLICATION = ("ads_management", "ads_read", "business_management", "pages_show_list",
                      "pages_read_engagement")


def url_de_connexion(app_id, adresse_publique, etat, droits=DROITS_AUDIT, page_de_retour="/callback"):
    """L'adresse du dialogue Facebook. C'est LE bouton que le commerçant appuie.

    Les permissions demandées sont exactement celles dont le travail a besoin, et Meta les présente au
    client sur SES pages — il voit ce qu'il accorde, et il peut refuser.
    """
    return ("https://www.facebook.com/" + VERSION_API + "/dialog/oauth?" +
            urllib.parse.urlencode({
                "client_id": app_id,
                "redirect_uri": adresse_publique.rstrip("/") + page_de_retour,
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
                "scope": ",".join(droits),
                "response_type": "code"}))


def echanger_le_code(code, app_id, app_secret, adresse_publique, page_de_retour="/callback"):
    """Le code devient un jeton — d'abord court, puis LONG (≈ 60 jours)."""
    if not app_secret:
        raise ErreurGraph("La clé secrète de l'application n'est pas encore installée sur le "
                          "serveur : Meta ne peut pas échanger ce code contre un jeton.")
    court = _graph_get("oauth/access_token", {
        "client_id": app_id, "client_secret": app_secret, "code": code,
        "redirect_uri": adresse_publique.rstrip("/") + page_de_retour})
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
def signer(chat_id, secret, mode="audit"):
    """Le lien porte le mode ET l'identifiant Telegram du client, SIGNÉS. Un lien forgé est refusé.

    ⚠️ POURQUOI LE MODE VOYAGE DANS LE LIEN SIGNÉ : Meta renvoie EXACTEMENT l'adresse de retour
    déclarée dans son tableau de bord. Ajouter un paramètre fixe (« ?pub=1 ») obligerait à déclarer
    une deuxième adresse — une manipulation de plus, et un dialogue qui échoue en silence si on
    l'oublie. Le mode passe donc par le `state`, qui revient intact.
    """
    brut = f"{mode}|{chat_id}|{int(time.time())}"
    signature = hmac.new(secret.encode(), brut.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{brut}|{signature}"


def mode_du_lien(etat):
    """Rend le mode porté par un lien signé (audit ou pub), ou None si le format est ancien."""
    morceaux = (etat or "").split("|")
    return morceaux[0] if len(morceaux) == 4 else None


def verifier_etat(etat, secret, validite=3600):
    """Rend l'identifiant Telegram, ou None si le lien est forgé ou trop vieux."""
    try:
        morceaux = (etat or "").split("|")
        if len(morceaux) == 4:                       # nouveau format : mode|chat|quand|signature
            mode, chat_id, quand, signature = morceaux
            brut = f"{mode}|{chat_id}|{quand}"
        else:                                        # ancien format : chat.quand.signature
            chat_id, quand, signature = (etat or "").rsplit(".", 2)
            brut = f"{chat_id}.{quand}"
        attendu = hmac.new(secret.encode(), brut.encode(), hashlib.sha256).hexdigest()[:32]
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
<title>Perform — pourquoi ta pub ne vend pas</title>
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
 /* ICÔNE AGRANDIE LE 10/10/2026 — José, capture à l'appui : « Pour l'icône, trop petit.
    Il faut que ce soit plus grand. » 78 px était timide sur un téléphone : c'est le premier
    élément que l'œil rencontre, il porte la promesse. 132 px, arrondi proportionnel, ombre
    plus profonde pour qu'elle se détache du fond clair. */
 .logo{width:132px;height:132px;border-radius:34px;display:block;margin:6px auto 20px;
       box-shadow:0 18px 38px -16px rgba(15,23,42,.5)}
 .etiquette{display:inline-block;background:#e8f8ee;color:#15803d;font-size:12.5px;font-weight:700;
            padding:5px 12px;border-radius:999px;margin:0 0 14px;letter-spacing:.2px}
 h1{font-size:30px;line-height:1.18;margin:0 0 12px;letter-spacing:-.6px}
 .accroche{color:#475569;font-size:16.5px;line-height:1.62;margin:0 0 28px}
 .accroche b{color:#0f172a}
 .fb{display:flex;align-items:center;justify-content:center;gap:11px;width:100%;
     background:#1877f2;color:#fff;text-decoration:none;font-weight:700;font-size:17px;
     padding:17px 20px;border-radius:14px;box-shadow:0 10px 22px -10px rgba(24,119,242,.9);
     transition:transform .12s ease,box-shadow .12s ease}
 .fb:active{transform:translateY(1px);box-shadow:0 6px 14px -8px rgba(24,119,242,.9)}
 /* la phrase de réassurance, seule et sobre : ni liste, ni coche, ni encadré */
 .serment{color:#8896a8;font-size:13.5px;margin:14px 0 0;text-align:center;letter-spacing:.1px}
 .fb svg{width:22px;height:22px;fill:#fff;flex:none}
 .fb.pub{background:#16a34a;margin-top:12px;box-shadow:0 10px 22px -10px rgba(22,163,74,.9)}
.fb.pub.verrouille{background:#cbd5e1;color:#64748b;box-shadow:none;pointer-events:none}
 .trait{height:1px;background:#eef2f7;margin:24px 0 16px}
 .petit{color:#8896a8;font-size:12.5px;line-height:1.6;margin:0 0 10px}
 .pied{color:#a3aebd;font-size:12px;margin:14px 0 0}
 .pied a{color:#8896a8}
 .signature{color:#94a3b8;font-size:12.5px;margin:14px 0 0;letter-spacing:.2px}
 .signature b{color:#64748b;font-weight:600}
</style></head><body><div class="carte">
<img class="logo" src="/icone-512.png" alt="Perform" width="132" height="132">
<h1>Pourquoi ta pub ne vend pas</h1>
<p class="accroche">Je lis ton <b>compte publicitaire</b> et les <b>paroles de tes clients</b>.
Puis je te dis où part ton argent, ce qui bloque — et ce qu'il faut changer.</p>
<a class="fb" href="__LIEN__">
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9
  3.7-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12z"/></svg>
  Continuer avec Facebook
</a>
<!-- ⛔⛔ LES TROIS POINTS NE REVIENNENT PAS (José les a fait retirer le 10/10/2026 : « Supprime cette
 partie »). Seule CETTE phrase revient, et parce qu'il l'a demandée explicitement le même soir : c'est
 la phrase qui rassure au moment précis où un client hésite à cliquer. Une phrase, pas une liste, pas
 de coches. -->
<p class="serment">🔒 Ton mot de passe Facebook ne passe jamais par ici.</p>
__BOUTON_PUB__
<p class="petit" style="margin-top:10px">Nouveau : je fabrique la publicité et je la mets en ligne
— ton image, ton idée, ton budget, ta durée, ta cible.</p>
<!-- ⛔ LE BLOC DES TROIS POINTS A ÉTÉ RETIRÉ LE 10/10/2026, SUR DEMANDE DE JOSÉ
 (capture annotée : « Supprime cette partie »). On ne le réintroduit pas sans son accord. -->
<p class="petit">📱 Pour la garder sous la main : menu ⋮ de ton navigateur →
« Ajouter à l'écran d'accueil ». Elle s'ouvrira comme une application.</p>
<p class="pied">Tes données restent les tiennes — <a href="/confidentialite">confidentialité</a></p>
<p class="signature">Perform — par <b>José Ledanite</b></p>
</div></body></html>"""

BOUTON_PUB_ACTIF = """<a class="fb pub" href="__LIEN_PUB__">
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 2 7l10 5 10-5-10-5zm0 7.2L4.6 5.9 12 2.2l7.4 3.7L12 9.2zM2 12l10 5 10-5-0.9-.5L12 15.6 2.9 11.5 2 12zm0 5 10 5 10-5-.9-.5L12 20.6 2.9 16.5 2 17z"/></svg>
  Créer mes publicités
</a>"""

BOUTON_PUB_VERROUILLE = """<a class="fb pub verrouille" aria-disabled="true">
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 2 7l10 5 10-5-10-5zm0 7.2L4.6 5.9 12 2.2l7.4 3.7L12 9.2zM2 12l10 5 10-5-0.9-.5L12 15.6 2.9 11.5 2 12zm0 5 10 5 10-5-.9-.5L12 20.6 2.9 16.5 2 17z"/></svg>
  Connecte-toi d'abord avec Facebook
</a>"""

PAGE_CONFIDENTIALITE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Confidentialité — Perform</title>
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
<p class="date">Perform — dernière mise à jour : 10 octobre 2026</p>
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
<h2>Ce que nous gardons, et combien de temps</h2>
<p><b>Rien.</b> Le rapport d'audit vit en mémoire le temps d'une heure, puis il est oublié. Il n'est
jamais écrit sur disque, jamais conservé, jamais transmis à un tiers ni revendu. Le service n'a donc
aucune donnée personnelle à effacer : il n'en détient pas. Si tu veux arrêter, il suffit de retirer
l'accès dans tes réglages Facebook — et tout s'arrête là.</p>
<h2>Nous joindre</h2>
<p>Pour toute question sur ces points, écris à l'éditeur du service, José Ledanite.</p>
<p class="date" style="margin-top:22px">Perform — par <b>José Ledanite</b></p>
</div></body></html>"""

PAGE_RESULTAT = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ton audit — Perform</title>
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


# ═══════════════════════════════════════════════════════════════════════════════════════════════
# LE BOUTON QUI GÉNÈRE LE JETON — la demande de José, le 10/10/2026 :
#   « Crée un bouton qui génère des jetons. Aucun débutant n'ira chercher lui-même le jeton. »
# ═══════════════════════════════════════════════════════════════════════════════════════════════
# TROIS PAGES, UN SEUL GESTE POUR L'UTILISATEUR : un bouton, il autorise, il choisit son compte et sa
# page dans une liste. Il ne voit JAMAIS un jeton, ne copie rien, ne cherche aucun identifiant.
#
# Le jeton est destiné à la machine qui publiera les publicités. C'est pourquoi le serveur l'envoie
# par TELEGRAM (au propriétaire de l'outil) : c'est un canal privé déjà en place, et ça évite le
# copier-coller qui fait renoncer un débutant.

PAGE_PUB_BOUTON = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Créer mes publicités — Perform</title>
<meta name="theme-color" content="#f4f6fb">
<link rel="apple-touch-icon" href="/icone-apple-180.png">
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{color-scheme:light}
 *{box-sizing:border-box}
 body{margin:0;background:
      radial-gradient(900px 420px at 50% -8%,#e5f6ec 0%,rgba(229,246,236,0) 62%),
      linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;min-height:100vh;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
      display:flex;align-items:center;justify-content:center;padding:26px 18px}
 .carte{width:100%;max-width:440px;background:#fff;border:1px solid #e8edf4;border-radius:22px;
        padding:34px 26px 26px;text-align:center;
        box-shadow:0 1px 2px rgba(15,23,42,.04),0 18px 44px -18px rgba(15,23,42,.18)}
 .logo{width:132px;height:132px;border-radius:34px;display:block;margin:6px auto 20px;
       box-shadow:0 18px 38px -16px rgba(15,23,42,.5)}
 .etiquette{display:inline-block;background:#e8f8ee;color:#15803d;font-size:12.5px;font-weight:700;
            padding:5px 12px;border-radius:999px;margin:0 0 14px;letter-spacing:.2px}
 h1{font-size:29px;line-height:1.18;margin:0 0 12px;letter-spacing:-.6px}
 .accroche{color:#475569;font-size:16.5px;line-height:1.62;margin:0 0 28px}
 .accroche b{color:#0f172a}
 .fb{display:flex;align-items:center;justify-content:center;gap:11px;width:100%;
     background:#1877f2;color:#fff;text-decoration:none;font-weight:700;font-size:17px;
     padding:17px 20px;border-radius:14px;box-shadow:0 10px 22px -10px rgba(24,119,242,.9)}
 .fb svg{width:22px;height:22px;fill:#fff;flex:none}
 .serment{color:#8896a8;font-size:13.5px;margin:14px 0 0}
 .trait{height:1px;background:#eef2f7;margin:24px 0 16px}
 .petit{color:#8896a8;font-size:12.5px;line-height:1.6;margin:0 0 10px}
 .signature{color:#94a3b8;font-size:12.5px;margin:14px 0 0}
 .signature b{color:#64748b;font-weight:600}
</style></head><body><div class="carte">
<img class="logo" src="/icone-512.png" alt="Perform" width="132" height="132">
<span class="etiquette">Publication automatique</span>
<h1>Créer mes publicités</h1>
<p class="accroche">Tu donnes <b>ton image</b>, <b>ton idée</b>, ton budget, ta durée et ta cible.
Je fabrique la publicité et je la mets en ligne — <b>sans que tu touches au gestionnaire de pubs</b>.</p>
<a class="fb" href="__LIEN__">
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M22 12a10 10 0 1 0-11.6 9.9v-7H7.9V12h2.5V9.8c0-2.5 1.5-3.9
  3.7-3.9 1.1 0 2.2.2 2.2.2v2.4h-1.2c-1.2 0-1.6.8-1.6 1.6V12h2.7l-.4 2.9h-2.3v7A10 10 0 0 0 22 12z"/></svg>
  Autoriser la création de mes publicités
</a>
<p class="serment">🔒 Ton mot de passe Facebook ne passe jamais par ici. Tu peux retirer cet accès
quand tu veux, dans tes réglages Facebook.</p>
<div class="trait"></div>
<p class="petit">Ce que tu autorises : gérer tes annonces, voir tes pages, publier au nom de ta page.
Ce que tu vois ensuite : tes comptes publicitaires et tes pages, en liste — tu choisis, c'est tout.</p>
<p class="signature">Perform — par <b>José Ledanite</b></p>
</div></body></html>"""

PAGE_PUB_FIN = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>C'est prêt — Perform</title>
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{color-scheme:light}
 body{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:26px 18px;line-height:1.65}
 .carte{max-width:560px;margin:0 auto;background:#fff;border:1px solid #e8edf4;border-radius:20px;
        padding:30px 26px;box-shadow:0 18px 44px -22px rgba(15,23,42,.18)}
 h1{font-size:23px;margin:0 0 12px}
 .ok{background:#e8f8ee;border-left:4px solid #22c55e;padding:14px 16px;border-radius:10px;color:#166534}
 p,li{color:#475569;font-size:15px}
 .signature{color:#94a3b8;font-size:12.5px;margin-top:22px}
 .signature b{color:#64748b;font-weight:600}
</style></head><body><div class="carte">
<h1>C'est réglé ✅</h1>
<div class="ok">__MESSAGE__</div>
<p>Tu peux fermer cette page. La suite se passe dans <b>Telegram</b> : tu envoies ta photo, ton idée,
ton budget, ta durée et ta cible — et la publicité part.</p>
<p class="signature">Perform — par <b>José Ledanite</b></p>
</div></body></html>"""


class ErreurPublication(Exception):
    pass


def lire_comptes_et_pages(jeton):
    """Ce que l'utilisateur a le droit de piloter : ses comptes publicitaires et ses pages.

    On ne lui fait pas chercher un « act_123… » : on lui montre une liste et il choisit.
    """
    comptes = _graph_get("me/adaccounts", {
        "access_token": jeton, "limit": 50,
        "fields": "name,account_id,currency,account_status"}).get("data", [])
    pages = _graph_get("me/accounts", {
        "access_token": jeton, "limit": 50, "fields": "name,id"}).get("data", [])
    return comptes, pages


def page_de_choix(identifiant, comptes, pages):
    """La page où l'utilisateur choisit son compte et sa page. Deux listes, deux réponses."""
    def options(entrees, valeur, libelle):
        morceaux = []
        for i, entree in enumerate(entrees, 1):
            morceaux.append(f'<option value="{i}">{i}. {libelle(entree)}</option>')
        return "\n".join(morceaux) or '<option value="">— aucun —</option>'

    etat_compte = {1: "actif", 2: "désactivé", 3: "non réglé", 7: "en revue",
                   9: "en grâce", 101: "fermé"}
    choix_comptes = options(comptes, "account_id",
                            lambda c: f"{c.get('name') or 'compte sans nom'} · "
                                      f"{c.get('currency')} · "
                                      f"{etat_compte.get(c.get('account_status'), '?')}")
    choix_pages = options(pages, "id", lambda p: p.get("name") or "page sans nom")
    manque = ""
    if not comptes or not pages:
        manque = ("<p class=\"petit\">⚠️ Il manque un compte publicitaire ou une page : "
                  "vérifie que tu as bien un compte d'annonces, et qu'il est rattaché à ta page.</p>")
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Tu choisis — Perform</title>
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{{color-scheme:light}}
 body{{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px 18px;line-height:1.6}}
 .carte{{max-width:560px;margin:0 auto;background:#fff;border:1px solid #e8edf4;border-radius:20px;
        padding:28px 24px;box-shadow:0 18px 44px -22px rgba(15,23,42,.18)}}
 h1{{font-size:22px;margin:0 0 6px}} label{{display:block;font-weight:700;color:#334155;
      font-size:14px;margin:18px 0 6px}}
 select{{width:100%;padding:13px;border:1px solid #dfe5ef;border-radius:12px;font-size:15px;background:#fff}}
 button{{margin-top:22px;width:100%;padding:16px;border:0;border-radius:13px;background:#1877f2;
        color:#fff;font-size:16.5px;font-weight:700}}
 .petit{{color:#8896a8;font-size:13px;margin:8px 0 0}}
 .signature{{color:#94a3b8;font-size:12.5px;margin:22px 0 0;text-align:center}}
 .signature b{{color:#64748b;font-weight:600}}
</style></head><body><div class="carte">
<h1>Dernière étape</h1>
<p class="petit">Tu es bien connecté. Dis-moi avec quel compte et quelle page je travaille.</p>
{manque}
<form method="get" action="/publicite-valider">
<input type="hidden" name="id" value="{identifiant}">
<label for="compte">Ton compte publicitaire</label>
<select id="compte" name="compte">{choix_comptes}</select>
<label for="page">Ta page Facebook</label>
<select id="page" name="page">{choix_pages}</select>
<button>Terminer</button>
</form>
<p class="signature">Perform — par <b>José Ledanite</b></p>
</div></body></html>"""


PAGE_CONTENU = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ta publicité — Perform</title>
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{color-scheme:light}
 body{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px 18px;line-height:1.6}
 .carte{max-width:600px;margin:0 auto;background:#fff;border:1px solid #e8edf4;border-radius:20px;
        padding:28px 24px;box-shadow:0 18px 44px -22px rgba(15,23,42,.18)}
 h1{font-size:22px;margin:0 0 6px}
 .petit{color:#8896a8;font-size:13px;margin:8px 0 0}
 .offre{border:2px solid #e8edf4;border-radius:16px;padding:16px;margin:16px 0;cursor:pointer;display:block}
 .offre.actif{border-color:#1877f2;background:#f5f9ff}
 .offre b{display:block;font-size:16px;color:#0f172a}
 .offre span{color:#5a6b80;font-size:14px}
 .liste{margin-top:10px;max-height:260px;overflow:auto}
 .pub{border:1px solid #e8edf4;border-radius:12px;padding:10px;margin:8px 0;display:flex;gap:10px;
      align-items:center}
 .pub img{width:54px;height:54px;object-fit:cover;border-radius:9px;flex:0 0 auto;background:#eef2f8}
 .pub div{font-size:13.5px;color:#334155}
 button{margin-top:22px;width:100%;padding:16px;border:0;border-radius:13px;background:#1877f2;
        color:#fff;font-size:16.5px;font-weight:700}
 .signature{color:#94a3b8;font-size:12.5px;margin:22px 0 0;text-align:center}
 .signature b{color:#64748b;font-weight:600}
</style></head><body><div class="carte">
<h1>Ta publicité</h1>
<p class="petit">Dernière question : de quoi parle ta publicité ?</p>
__SOUCI__
<form method="get" action="/publicite-fin">
<input type="hidden" name="id" value="__ID__">
<input type="hidden" name="compte" value="__COMPTE__">
<input type="hidden" name="page" value="__PAGE__">
<label class="offre actif"><b>① Je crée une publicité neuve</b>
<span>Je te donne une image et une idée, l'outil écrit le texte et fabrique la publicité.</span></label>
<label class="offre"><b>② J'utilise une publication déjà en ligne</b>
<span>Choisis une publication de ta page : la publicité s'appuiera dessus, sans rien refabriquer.</span></label>
<div class="liste" id="liste">__PUBLICATIONS__</div>
<button>Terminer</button>
</form>
<p class="signature">Perform — par <b>José Ledanite</b></p>
</div>
<script>
// Cocher une publication revient à choisir l'option « publication déjà en ligne » : deux gestes pour
// une seule intention, c'est un geste de trop pour un débutant.
document.querySelectorAll('input[name=contenu]').forEach(function (r) {
  r.addEventListener('change', function () {
    document.querySelectorAll('.offre').forEach(function (o) { o.classList.remove('actif'); });
    document.querySelectorAll('.offre')[1].classList.add('actif');
  });
});
// ⛔ AUCUN CHAMP CACHÉ ICI (défaut trouvé par test le 10/10/2026) : un champ caché du même nom que
// les cases à cocher aurait envoyé « rien » en même temps que le choix du client, et le serveur
// aurait pu lire « rien » — donc créer une publicité neuve alors que le client avait désigné sa
// publication. Ne rien cocher veut DÉJÀ dire « publicité neuve » : c'est le serveur qui le déduit.
document.querySelectorAll('.offre')[0].addEventListener('click', function () {
  document.querySelectorAll('input[name=contenu]').forEach(function (r) { r.checked = false; });
});
</script>
</body></html>"""


def page_du_contenu(identifiant, index_compte, index_page, fiche):
    """L'écran où le client dit COMMENT il veut sa publicité (demande de José, 10/10/2026).

    Deux chemins, et il choisit :
      ① l'outil fabrique le contenu (image + idée) — la voie de base ;
      ② la publicité s'appuie sur une publication DÉJÀ en ligne sur sa page — la voie qui marche
         même quand l'application Meta est encore en développement.

    ⚠️ ON MONTRE LE TEXTE ET LA PHOTO des publications, pas leurs identifiants : un client reconnaît
    « la photo de la nappe bleue », pas « 104084798748794_1091154536706350 ».
    """
    compte = fiche["comptes"][index_compte - 1]
    page = fiche["pages"][index_page - 1]
    souci = ""
    morceaux = []
    try:
        pages_avec_jeton = pages_meta.lister_pages(fiche["jeton"])
        la_page = next((p for p in pages_avec_jeton if p.get("id") == page.get("id")), None)
        publications = pages_meta.lister_publications(la_page, 12) if la_page else []
        for publication in publications:
            image = (f'<img src="{publication["image"]}" alt="" loading="lazy">'
                     if publication.get("image") else '<img alt="">')
            texte = publication["apercu"] or "(publication sans texte)"
            case = (f'<label class="pub"><input type="radio" name="contenu" '
                    f'value="{publication["id"]}">{image}<div>{texte}</div></label>')
            morceaux.append(case)
        if not morceaux:
            morceaux.append('<p class="petit">Aucune publication trouvée sur cette page : prends la '
                            'première option.</p>')
    except Exception as erreur:  # noqa: BLE001 — on informe, on ne bloque pas le parcours
        souci = (f'<p class="petit">⚠️ Impossible de lire les publications de cette page : '
                 f'{erreur} Tu peux quand même créer une publicité neuve.</p>')
    return (PAGE_CONTENU
            .replace("__ID__", identifiant)
            .replace("__COMPTE__", str(index_compte))
            .replace("__PAGE__", str(index_page))
            .replace("__PUBLICATIONS__", "\n".join(morceaux))
            .replace("__SOUCI__", souci))


PUBLICATIONS = {}          # identifiant -> {jeton, comptes, pages}, le temps du parcours
CONNEXIONS = {}            # chat_id -> True, une fois la connexion Facebook réussie
# ⚠️ LES REGLAGES ATTENDENT ICI QUE LE TELEPHONE VIENNE LES PRENDRE. C'est ce qui évite le
# copier-coller : l'utilisateur ne voit jamais un jeton, et la machine qui publie les publicités le
# récupère elle-même (voir recuperer-reglages.py côté téléphone). Consommés une seule fois, puis
# effacés — un jeton qui traîne est un jeton qui fuite.
REGLAGES_A_RECUPERER: dict = {"en_attente": None}
FICHIER_ATTENTE = os.path.join(ICI, "reglages-en-attente.json")


def garder_reglages(reglages):
    """Garde les réglages EN MÉMOIRE **et sur le disque**.

    ⚠️ LE DISQUE COMPTE : l'hébergement gratuit redémarre l'instance (mise en veille, ou simple
    redéploiement). En mémoire seule, un jeton autorisé par un client serait perdu sans que personne
    ne comprenne pourquoi — et le client devrait recommencer. Vécu le 10/10/2026.
    """
    REGLAGES_A_RECUPERER["en_attente"] = reglages
    try:
        with open(FICHIER_ATTENTE, "w", encoding="utf-8") as f:
            json.dump(reglages, f, ensure_ascii=False)
        os.chmod(FICHIER_ATTENTE, 0o600)
    except OSError:
        pass


def prendre_reglages():
    """Rend les réglages en attente, et n'en laisse AUCUNE trace (un jeton qui traîne est un jeton
    qui fuite) : mémoire vidée, fichier effacé."""
    reglages = REGLAGES_A_RECUPERER.get("en_attente")
    REGLAGES_A_RECUPERER["en_attente"] = None
    if reglages is None:
        try:
            with open(FICHIER_ATTENTE, encoding="utf-8") as f:
                reglages = json.load(f)
        except (OSError, ValueError):
            reglages = None
    if reglages:
        try:
            os.remove(FICHIER_ATTENTE)
        except OSError:
            pass
    return reglages


def envoyer_telegram(jeton_bot, chat, texte):
    """Prévient par Telegram. C'est le canal privé déjà en place — pas de copier-coller."""
    if not jeton_bot or not chat:
        return False
    donnees = urllib.parse.urlencode({"chat_id": chat, "text": texte,
                                      "disable_web_page_preview": "true"}).encode()
    try:
        requete = urllib.request.Request(f"https://api.telegram.org/bot{jeton_bot}/sendMessage",
                                         data=donnees)
        urllib.request.urlopen(requete, timeout=20).read()
        return True
    except Exception as erreur:  # noqa: BLE001 — l'échec ne doit pas casser le parcours
        print(f"[publication] Telegram injoignable : {erreur}", flush=True)
        return False


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
    # ⛔ ON PASSE PAR LA CONSTRUCTION PARTAGÉE (connexion.fiche_pour_le_moteur). Recopier cette
    # construction ici est exactement ce qui a produit le bug du 10/10/2026 : deux copies, la même
    # faute, et un rapport qui plante chez le client.
    pseudo = connexion.fiche_pour_le_moteur(resultat)
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
# CE QUE ÇA CHANGE POUR LE CLIENT, en une phrase : depuis son navigateur, deux appuis et « Perform »
# s'ajoute à son écran d'accueil — avec son icône, en plein écran, comme une application. Sans magasin,
# sans rien à installer de compliqué, et sans frais. C'est ça, « l'appli installable » demandée.
# Chrome réclame trois choses pour l'autoriser : une adresse HTTPS (Render ✓), un MANIFESTE et un
# SERVICE WORKER. Les icônes sont de vrais PNG dessinés dans le projet (voir fabriquer-icones.py).
MANIFESTE = """{
 "name": "Perform", "short_name": "Perform", "lang": "fr",
 "start_url": "/", "scope": "/", "display": "standalone",
 "background_color": "#0f1115", "theme_color": "#0f1115",
 "description": "Dis pourquoi ta publicité ne te rapporte pas de commandes. Par José Ledanite.",
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

# ─────────────────────────────────────────── les deux petites aides des pages
def _page_simple(titre, texte, code_entete="200"):
    """Une petite page claire pour les impasses : message court, jamais de page blanche."""
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{titre} — Perform</title><style>'
            ':root{color-scheme:light}'
            'body{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;'
            'font-family:system-ui,-apple-system,sans-serif;min-height:100vh;display:flex;'
            'align-items:center;justify-content:center;padding:26px 18px}'
            '.carte{width:100%;max-width:440px;background:#fff;border:1px solid #e8edf4;'
            'border-radius:22px;padding:32px 24px;box-shadow:0 18px 44px -18px rgba(15,23,42,.18)}'
            'h1{font-size:21px;margin:0 0 10px}p{color:#475569;font-size:15px;line-height:1.6;margin:0}'
            'a{color:#1877f2}'
            '</style></head><body><div class="carte">'
            f'<h1>{titre}</h1><p>{texte}</p></div></body></html>')


def _enrichir(texte):
    """Rend le rapport affichable dans une page : échappé, puis le gras markdown mis en forme.

    ⚠️ ON ÉCHAPPE D'ABORD, ON MET EN FORME ENSUITE. Le rapport contient des noms de pages, de
    campagnes et des commentaires de clients : si un commentaire contient « < », non échappé, il
    casserait la page — voire y injecterait du code. L'échappement d'abord est la seule bonne
    manière, même si le texte vient de nos propres fonctions.
    """
    import html as _html
    import re as _re
    protege = _html.escape(texte or "")
    protege = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", protege)
    protege = _re.sub(r"`([^`]+)`", r"<code>\1</code>", protege)
    return protege


# ─────────────────────── LES RAPPORTS, GARDÉS EN MÉMOIRE (10/10/2026)
# POURQUOI CE CHANGEMENT. José, le 10/10/2026 : « Le bot audit va me fatiguer, également mes
# clients. Je vais le supprimer. » Il a raison sur le fond : le client devait ouvrir Telegram, écrire
# au bot, puis revenir sur le site. Trois gestes pour un seul service. Or le bot ne servait qu'à UNE
# chose : LIVRER le rapport. Donc on livre le rapport là où le client est déjà — sur la page.
#
# ⚠️ EN MÉMOIRE, JAMAIS SUR DISQUE, ET ÇA SE PÉRIME. L'audit parle du compte publicitaire de
# quelqu'un : le garder au chaud dans une dict de RAM, effacé au bout d'une heure, est le
# comportement le plus honnête possible — et cohérent avec la page /confidentialite qui promet
# qu'aucun jeton ne survit à l'audit. Un redémarrage du service perd les rapports en cours : le
# client relance, c'est tout. On sacrifie un peu de confort pour ne rien stocker.
RAPPORTS = {}
RAPPORTS_DUREE = 3600          # une heure, puis oubliés
RAPPORTS_MAX = 200             # borne de sécurité : la mémoire d'un service gratuit


def _ranger(jeton, **etat):
    """Range l'état d'un audit. Purge au passage ce qui a expiré."""
    maintenant = time.time()
    for cle in [k for k, v in RAPPORTS.items() if maintenant - v.get("quand", 0) > RAPPORTS_DUREE]:
        RAPPORTS.pop(cle, None)
    while len(RAPPORTS) > RAPPORTS_MAX:
        RAPPORTS.pop(next(iter(RAPPORTS)), None)
    RAPPORTS.setdefault(jeton, {})
    RAPPORTS[jeton].update(etat, quand=maintenant)


PAGE_ATTENTE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Analyse en cours — Perform</title>
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{color-scheme:light}
 body{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;min-height:100vh;
      display:flex;align-items:center;justify-content:center;padding:26px 18px}
 .carte{width:100%;max-width:440px;background:#fff;border:1px solid #e8edf4;border-radius:22px;
        padding:36px 26px;text-align:center;box-shadow:0 18px 44px -18px rgba(15,23,42,.18)}
 .ronde{width:52px;height:52px;margin:0 auto 20px;border:4px solid #e8f8ee;border-top-color:#22c55e;
        border-radius:50%;animation:tourne 1s linear infinite}
 @keyframes tourne{to{transform:rotate(360deg)}}
 h1{font-size:21px;margin:0 0 8px}
 p{color:#475569;font-size:15px;line-height:1.6;margin:0}
 .compte{color:#94a3b8;font-size:13px;margin-top:16px}
 .echec{background:#fff7ed;border-left:4px solid #f97316;color:#9a3412;border-radius:10px;
        padding:12px 14px;font-size:14px;text-align:left;margin-top:16px}
</style></head><body><div class="carte">
<div class="ronde" id="ronde"></div>
<h1 id="titre">J'analyse ton compte…</h1>
<p id="dit">Je lis tes statistiques sur 30 jours, ta liste de pages et les commentaires de tes publications. Cela prend quelques dizaines de secondes.</p>
<p class="compte" id="compte">Ne ferme pas cette page.</p>
</div>
<script>
 var essais = 0, jeton = "__JETON__";
 function verifie() {
   essais++;
   fetch("/etat?jeton=" + encodeURIComponent(jeton)).then(function (r) { return r.json(); }).then(function (d) {
     if (d.etat === "pret") { window.location.href = "/resultat?jeton=" + encodeURIComponent(jeton); return; }
     if (d.etat === "erreur") {
       document.getElementById("ronde").style.display = "none";
       document.getElementById("titre").textContent = "Je n'ai pas pu terminer";
       document.getElementById("compte").style.display = "none";
       document.getElementById("dit").outerHTML = '<div class="echec">' + (d.message || "Réessaie dans un instant.") + '</div>';
       return;
     }
     document.getElementById("compte").textContent = "Analyse en cours… (" + (essais * 3) + " s)";
     if (essais < 60) { setTimeout(verifie, 3000); }
     else {
       document.getElementById("ronde").style.display = "none";
       document.getElementById("titre").textContent = "C'est plus long que prévu";
       document.getElementById("dit").textContent = "Facebook répond lentement. Recharge la page dans un instant.";
     }
   }).catch(function () { if (essais < 60) { setTimeout(verifie, 3000); } });
 }
 setTimeout(verifie, 1200);
</script></body></html>"""


PAGE_RAPPORT = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ton audit — Perform</title>
<link rel="icon" type="image/png" href="/icone-192.png">
<style>
 :root{color-scheme:light}
 body{margin:0;background:linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);color:#0f172a;
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:22px 16px 40px;line-height:1.65}
 .carte{max-width:640px;margin:0 auto;background:#fff;border:1px solid #e8edf4;border-radius:20px;
        padding:26px 22px;box-shadow:0 18px 44px -22px rgba(15,23,42,.18)}
 h1{font-size:22px;margin:0 0 4px}
 .sous{color:#64748b;font-size:14px;margin:0 0 18px}
 .ok{background:#e8f8ee;border-left:4px solid #22c55e;padding:12px 14px;border-radius:10px;
     color:#166534;font-size:14px;margin:0 0 18px}
 .signature{color:#94a3b8;font-size:12.5px;margin:16px 0 0}
 .signature b{color:#64748b;font-weight:600}
 pre{white-space:pre-wrap;word-break:break-word;font-family:inherit;font-size:14.5px;color:#334155;
     background:#f7f9fc;border:1px solid #eef2f7;border-radius:12px;padding:16px;margin:0}
 .bouton{display:inline-block;margin:18px 0 0;background:#0f172a;color:#fff;text-decoration:none;
         font-weight:600;font-size:14px;padding:12px 20px;border-radius:12px;border:0;cursor:pointer}
 @media print{.bouton,.sous{display:none}body{background:#fff}.carte{border:0;box-shadow:none}}
</style></head><body><div class="carte">
<h1>Ton audit</h1>
<p class="sous">Voici ce que disent tes chiffres.</p>
<div class="ok">Ton rapport est complet ci-dessous. Tu peux l'imprimer ou l'enregistrer en PDF.</div>
<pre>__RAPPORT__</pre>
<button class="bouton" onclick="window.print()">Imprimer / enregistrer en PDF</button>
<p class="signature">Perform — par <b>José Ledanite</b></p>
</div></body></html>"""


DETAILS = {"etat": "en_cours"}

FICHIERS_PWA = {"manifeste.json": ("application/manifest+json; charset=utf-8", MANIFESTE),
                "sw.js": ("text/javascript; charset=utf-8", SERVICE_WORKER)}
ICONES_PWA = ("icone-192.png", "icone-512.png", "icone-masquable-512.png",
              "icone-apple-180.png", "iparv.png")


def fabriquer_serveur(app_id, app_secret, adresse_publique, secret_liens, port=8080, jeton_bot=None):
    class Traitement(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _envoyer_html(self, html, code=200):
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def _envoyer_octets(self, donnees, type_mime, code=200):
            self.send_response(code)
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

            # ── la livraison du rapport, dans la page (le bot Telegram n'est plus nécessaire)
            if analyse.path == "/attente":
                jeton_attente = parametres.get("jeton", "")
                if jeton_attente not in RAPPORTS:
                    self._envoyer_html(_page_simple("Cette analyse a expiré",
                        "Reviens au début et appuie de nouveau sur « Continuer avec Facebook »."), 404)
                    return
                self._envoyer_html(PAGE_ATTENTE.replace("__JETON__", jeton_attente))
                return

            if analyse.path == "/etat":
                d = RAPPORTS.get(parametres.get("jeton", ""))
                corps = ({"etat": d.get("etat"), "message": d.get("message", "")} if d
                         else {"etat": "inconnu", "message": "Cette analyse a expiré."})
                self._envoyer_octets(json.dumps(corps).encode(), "application/json; charset=utf-8")
                return

            if analyse.path == "/resultat":
                jeton_res = parametres.get("jeton", "")
                d = RAPPORTS.get(jeton_res)
                if not d:
                    self._envoyer_html(_page_simple("Ce lien a expiré",
                        "Les rapports ne sont gardés qu'une heure, et le service oublie tout quand il "
                        "s'endort. Recommence : ouvre le lien et appuie sur « Continuer avec "
                        "Facebook »."), 404)
                    return
                if d.get("etat") != "pret":
                    self._envoyer_html(_page_simple("Ton audit n'est pas encore prêt",
                        "Suis l'analyse ici : <a href=\"/attente?jeton=" + jeton_res +
                        "\">voir où j'en suis</a>."))
                    return
                self._envoyer_html(PAGE_RAPPORT.replace("__RAPPORT__", _enrichir(d["texte"])))
                return

            # ── LE BOUTON QUI GÉNÈRE LE JETON (José : « aucun débutant n'ira le chercher lui-même »)
            if analyse.path == "/publicite":
                chat_id = verifier_etat(parametres.get("state", ""), secret_liens) if \
                    parametres.get("state") else (parametres.get("chat") or "")
                etat = signer(chat_id, secret_liens, mode="pub")
                self._envoyer_html(PAGE_PUB_BOUTON.replace("__LIEN__", url_de_connexion(
                    app_id, adresse_publique, etat, droits=DROITS_PUBLICATION)))
                return

            if analyse.path == "/publicite-valider":
                fiche = PUBLICATIONS.get(parametres.get("id", ""))
                if not fiche:
                    self._envoyer_html(_page_simple("Cette étape a expiré",
                        "Rouvre la page « Créer mes publicités » et recommence : cela prend "
                        "dix secondes."), 404)
                    return
                try:
                    compte = fiche["comptes"][int(parametres.get("compte", "1")) - 1]
                    page = fiche["pages"][int(parametres.get("page", "1")) - 1]
                except (ValueError, IndexError, KeyError):
                    self._envoyer_html(_page_simple("Choix incomplet",
                        "Reviens en arrière et choisis un compte et une page dans les listes."), 400)
                    return
                # ⚠️ ON NE TERMINE PLUS ICI (José, 10/10/2026) : le client choisit d'abord COMMENT il
                # veut sa publicité — neuve, fabriquée par l'outil, ou appuyée sur une publication
                # déjà en ligne. Le parcours reste « je choisis, et le job commence ».
                self._envoyer_html(page_du_contenu(parametres.get("id", ""),
                                                   int(parametres.get("compte", "1") or 1),
                                                   int(parametres.get("page", "1") or 1), fiche))
                return

            if analyse.path == "/publicite-fin":
                fiche = PUBLICATIONS.get(parametres.get("id", ""))
                if not fiche:
                    self._envoyer_html(_page_simple("Cette étape a expiré",
                        "Rouvre la page « Créer mes publicités » et recommence : cela prend "
                        "dix secondes."), 404)
                    return
                try:
                    compte = fiche["comptes"][int(parametres.get("compte", "1")) - 1]
                    page = fiche["pages"][int(parametres.get("page", "1")) - 1]
                except (ValueError, IndexError, KeyError):
                    self._envoyer_html(_page_simple("Choix incomplet",
                        "Reviens en arrière et choisis un compte et une page dans les listes."), 400)
                    return
                contenu = (parametres.get("contenu") or "").strip()
                reglages = {"jeton": fiche["jeton"], "compte_publicitaire": f"act_{compte['account_id']}",
                            "page_id": page["id"], "but": "trafic",
                            "devise": compte.get("currency", "XOF"),
                            "compte_nom": compte.get("name"), "page_nom": page.get("name")}
                if contenu:
                    # La publicité s'appuiera sur cette publication : rien à fabriquer, donc rien que
                    # Meta puisse refuser — c'est la voie qui fonctionne même en mode développement.
                    reglages["object_story_id"] = contenu
                # Le jeton part par Telegram : c'est le canal privé déjà en place, et l'utilisateur
                # n'a RIEN à copier. Le message porte un repère lisible par la machine locale.
                message = ("✅ Autorisation réussie.\n\n"
                           f"Compte : {reglages['compte_nom']} ({reglages['compte_publicitaire']})\n"
                           f"Page : {reglages['page_nom']} ({reglages['page_id']})\n"
                           f"Devise : {reglages['devise']}\n"
                           + (f"Contenu : publication existante {contenu}\n" if contenu
                              else "Contenu : publicité neuve (l'outil écrit le texte)\n")
                           + "\nTon outil s'installe tout seul — tu n'as rien à copier.")
                envoye = envoyer_telegram(jeton_bot, fiche["chat"], message)
                garder_reglages(reglages)
                del PUBLICATIONS[parametres.get("id", "")]
                # ⚠️ MESSAGE SANS CONDITION, ET SANS MENTION DE TELEGRAM (José, 10/10/2026 : « Le
                # client sélectionne son compte, sa page et le job commence »). L'installation ne
                # dépend PAS de Telegram : le téléphone vient chercher les réglages tout seul. Lui
                # demander d'appuyer sur DÉMARRER au milieu de son parcours, c'était ajouter une
                # inquiétude et une étape là où il n'y en avait pas.
                suite = ("Tes réglages sont enregistrés. Ton téléphone les installe tout seul — "
                         "tu n'as rien à faire.")
                if not envoye and jeton_bot:
                    print("[publication] message Telegram non délivré (bot jamais démarré ?)",
                          flush=True)
                self._envoyer_html(PAGE_PUB_FIN.replace("__MESSAGE__", suite))
                return

            if analyse.path == "/reglages":
                # ⚠️ RÉSERVÉ À LA MACHINE DE JOSÉ : sans le secret partagé, rien du tout. Le jeton
                # part, et il ne reste RIEN sur le serveur (consommé une seule fois).
                if not parametres.get("secret") or \
                        not hmac.compare_digest(parametres.get("secret", ""), secret_liens):
                    self._envoyer_octets(json.dumps({"erreur": "secret invalide"}).encode(),
                                         "application/json; charset=utf-8", 403)
                    return
                reglages = prendre_reglages()
                self._envoyer_octets(
                    json.dumps({"reglages": reglages}, ensure_ascii=False).encode(),
                    "application/json; charset=utf-8")
                return

            if analyse.path in ("/", "/index.html"):
                etat = signer(parametres.get("chat", ""), secret_liens)
                # ⚠️ ON REMPLACE UN JETON, ON NE FORMATTE PAS. La page contient de vraies accolades
                # CSS : un .format() dessus lèverait une KeyError (page cassée), et un .format() sans
                # ${} laisserait « __LIEN__ » en clair — le bouton « Continuer avec Facebook » ne
                # mènerait plus nulle part, exactement le défaut signalé par José.
                bouton_pub = (BOUTON_PUB_ACTIF if CONNEXIONS.get(parametres.get("chat", ""))
                              else BOUTON_PUB_VERROUILLE)
                self._envoyer_html(PAGE_ACCUEIL.replace(
                    "__LIEN__", url_de_connexion(app_id, adresse_publique, etat)).replace(
                    "__BOUTON_PUB__", bouton_pub).replace(
                    "__LIEN_PUB__", "/publicite?state=" + urllib.parse.quote(etat)))
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
                # ── LE MÊME RETOUR SERT AUX DEUX MÉTIERS, ET C'EST VOULU : Meta n'accepte que les
                # adresses de retour déclarées dans son tableau de bord. Le mode voyage dans le lien
                # signé, donc créer des publicités n'exige AUCUNE manipulation chez Meta.
                if mode_du_lien(parametres.get("state", "")) == "pub":
                    if parametres.get("error"):
                        self._envoyer_html(_page_simple("Accès refusé",
                            f"Facebook a répondu : {parametres['error'][:160]}"), 403)
                        return
                    code = parametres.get("code")
                    if not code:
                        self._envoyer_html(_page_simple("Réponse incomplète de Facebook",
                            "Aucun code d'autorisation n'est revenu."), 400)
                        return
                    try:
                        jeton = echanger_le_code(code, app_id, app_secret, adresse_publique)
                        comptes, pages = lire_comptes_et_pages(jeton)
                    except (ErreurGraph, connexion.ErreurMeta) as erreur:
                        self._envoyer_html(_page_simple("Je n'ai pas pu me connecter",
                            f"Facebook a refusé la demande : {str(erreur)[:220]}"), 500)
                        return
                    identifiant = secrets.token_urlsafe(12)
                    PUBLICATIONS[identifiant] = {"jeton": jeton, "comptes": comptes, "pages": pages,
                                                 "chat": chat_id}
                    CONNEXIONS[chat_id] = True
                    self._envoyer_html(page_de_choix(identifiant, comptes, pages))
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
                except (ErreurGraph, connexion.ErreurMeta) as e:
                    self._envoyer_html(_page_simple("Je n'ai pas pu me connecter",
                                                    f"Facebook a refusé la demande : {str(e)[:200]}"))
                    return

                # ⚠️ L'AUDIT PART DANS UN FIL, ET LE CLIENT REÇOIT TOUT DE SUITE UNE PAGE.
                # Deux raisons, toutes les deux vécues : un audit interroge Meta plusieurs fois
                # (5 à 30 secondes), et un navigateur de téléphone abandonne la requête bien avant
                # la fin — le client verrait une page blanche après avoir autorisé l'accès, ce qui
                # est la pire des impressions. On lui donne donc une page qui se met à jour seule.
                cle = hashlib.sha256((jeton + str(time.time())).encode()).hexdigest()[:24]
                _ranger(cle, etat="en_cours")
                CONNEXIONS[chat_id] = True

                def _auditer():
                    try:
                        texte, erreur = faire_audit(jeton)
                        if erreur or not texte:
                            print(f"[audit] refus de Facebook : {str(erreur)[:300]}", flush=True)
                            _ranger(cle, etat="erreur", message=erreur or "L'audit est revenu vide.")
                        else:
                            _ranger(cle, etat="pret", texte=texte)
                    except Exception:
                        # ⛔⛔ CE BLOC A ÉTÉ CORRIGÉ LE 10/10/2026, APRÈS LE PREMIER VRAI ESSAI DE JOSÉ.
                        # Il avait lu : « Une erreur inattendue est survenue (ErreurMeta) » — un
                        # message qui ne dit RIEN, avec un mot de développeur en prime. Et quand j'ai
                        # ouvert les journaux de Render pour comprendre : AUCUNE TRACE. Mon code
                        # attrapait l'erreur, la transformait en phrase vague et la jetait.
                        # Deux corrections, et les deux comptent : on TRACE (pour pouvoir réparer),
                        # et on parle au client en français, sans nom de classe.
                        import traceback as _tb
                        print("[audit] ERREUR INATTENDUE\n" + _tb.format_exc(), flush=True)
                        _ranger(cle, etat="erreur",
                                message="Quelque chose n'a pas répondu comme prévu chez Facebook. "
                                        "Réessaie dans un instant — et si ça recommence, dis-le à "
                                        "Laura, elle verra exactement ce qui s'est passé.")

                threading.Thread(target=_auditer, daemon=True).start()
                self.send_response(303)
                self.send_header("Location", "/attente?jeton=" + cle)
                self.end_headers()
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
    serveur = fabriquer_serveur(APP_ID, APP_SECRET, ADRESSE, SECRET_LIENS, port,
                                jeton_bot=_secret("telegram-bot-audit-token", obligatoire=False))
    print(f"Écoute sur le port {port} · adresse publique : {ADRESSE}", flush=True)
    serveur.serve_forever()
