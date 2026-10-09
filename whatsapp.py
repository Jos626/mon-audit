#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""whatsapp.py — L'API WHATSAPP BUSINESS OFFICIELLE (Cloud API de Meta). La vraie.

═══════════════════════════════════════════════════════════════════════════════════════════════════
CE QUE CE MODULE FAIT, ET POURQUOI C'EST LA BONNE PORTE (et pas le code QR de WhatsApp Web).
═══════════════════════════════════════════════════════════════════════════════════════════════════

Avec la Cloud API, le client ne donne AUCUN mot de passe et ne prête AUCUNE session : il branche son
numéro professionnel chez Meta, et Meta envoie les messages à une adresse que nous contrôlons. Il
garde la main : il peut débrancher quand il veut, et son numéro continue de fonctionner normalement.

Trois pièces, et il faut les trois :

  1. **RECEVOIR** — Meta appelle une adresse HTTPS avec un JSON. La forme est FIXE et vérifiée :
     `entry[].changes[].value.messages[]` avec `from`, `id`, `timestamp`, `type`, `text.body`.
     Le même objet porte aussi `statuses[]` (envoyé / remis / lu) — ce ne sont pas des messages de
     client, et les compter comme tels ferait croire à des conversations qui n'existent pas.
  2. **ENVOYER** — un POST sur `/<phone_number_id>/messages`. ⚠️ Une règle réelle, et sévère : hors
     d'une fenêtre de 24 h après le dernier message DU CLIENT, on ne peut pas écrire librement — il
     faut un modèle approuvé par Meta (« template »). C'est ce qui empêche de relancer n'importe qui,
     n'importe quand, et ça protège aussi le client du harcèlement.
  3. **VÉRIFIER L'ADRESSE** — Meta commence par un appel GET avec un jeton de vérification qu'il faut
     renvoyer tel quel. Sans cette étape, aucun message n'arrive jamais : c'est le premier piège, et
     il se règle en trois lignes.

⚠️ CE QU'IL FAUT AVANT QUE ÇA SERVE À UN CLIENT RÉEL, dit sans enrobage :
  · **un serveur avec HTTPS** — Meta ne sait appeler qu'une adresse publique. Un téléphone, même avec
    de la bonne volonté, n'a pas d'adresse publique : c'est la seule dépense incompressible du projet.
  · **l'application Meta de José + la vérification d'entreprise** (nom, adresse, documents) ;
  · **la revue de l'application** donnant les droits avancés `whatsapp_business_messaging` et
    `whatsapp_business_management` ;
  · **une carte bancaire du client** sur son compte WhatsApp Business (Meta facture les conversations).
Le module ci-dessous se teste intégralement AVANT tout ça (voir tests-whatsapp.py) : la réception, la
vérification et l'envoi se prouvent sur des charges réelles, sans attendre personne.
"""
import http.server
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VERSION_API = "v21.0"
BASE = f"https://graph.facebook.com/{VERSION_API}"
FENETRE_LIBRE = 24 * 3600          # la fenêtre de service : au-delà, seuls des modèles passent
BASE_DONNEES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whatsapp.sqlite3")


class ErreurWhatsApp(Exception):
    """L'erreur de Meta, avec son code — jamais réécrite, jamais résumée à « ça n'a pas marché »."""

    def __init__(self, message, code=None, sous_code=None):
        super().__init__(message)
        self.code = code
        self.sous_code = sous_code


# ─────────────────────────────────────────────────────────────── 1 · RECEVOIR
def recevoir(charge):
    """Une notification de Meta -> les messages de clients qu'elle contient.

    Rend {'messages': [...], 'statuts': [...], 'numero_affichage': str, 'numero_id': str}.
    Les STATUTS sont séparés des messages : ce sont des accusés de réception de NOS envois, pas des
    paroles de client. Les mélanger gonflerait le portrait avec nos propres phrases.
    """
    messages, statuts = [], []
    numero_affichage = numero_id = None
    if not isinstance(charge, dict) or charge.get("object") != "whatsapp_business_account":
        return {"messages": [], "statuts": [], "numero_affichage": None, "numero_id": None}

    for entree in charge.get("entry", []) or []:
        for changement in entree.get("changes", []) or []:
            valeur = changement.get("value") or {}
            if changement.get("field") != "messages":
                continue
            meta = valeur.get("metadata") or {}
            numero_affichage = meta.get("display_phone_number") or numero_affichage
            numero_id = meta.get("phone_number_id") or numero_id

            noms = {c.get("wa_id"): ((c.get("profile") or {}).get("name"))
                    for c in valeur.get("contacts", []) or []}

            for m in valeur.get("messages", []) or []:
                texte = _texte_du_message(m)
                messages.append({
                    "source": "whatsapp_api",
                    "auteur": noms.get(m.get("from")) or m.get("from") or "?",
                    "numero": m.get("from"),
                    "quand": _date(m.get("timestamp")),
                    "texte": texte,
                    "type": m.get("type"),
                    "identifiant": m.get("id"),
                })
            for s in valeur.get("statuses", []) or []:
                statuts.append({"identifiant": s.get("id"), "statut": s.get("status"),
                                "destinataire": s.get("recipient_id"),
                                "quand": _date(s.get("timestamp")),
                                "payant": ((s.get("pricing") or {}).get("billable"))})
    return {"messages": messages, "statuts": statuts,
            "numero_affichage": numero_affichage, "numero_id": numero_id}


def _texte_du_message(m):
    """Le texte d'un message, quel que soit son type.

    Un client qui envoie une PHOTO avec une légende pose une vraie question : ignorer la légende
    perdrait la demande. Et un message vocal transcrit n'existe pas ici (Meta donne un identifiant de
    média, pas le texte) — on le dit par une mention, jamais en inventant un contenu.
    """
    type_ = m.get("type")
    if type_ == "text":
        return ((m.get("text") or {}).get("body") or "").strip()
    if type_ == "button":
        return ((m.get("button") or {}).get("text") or "").strip()
    if type_ == "interactive":
        inter = m.get("interactive") or {}
        return ((inter.get("button_reply") or {}).get("title")
                or (inter.get("list_reply") or {}).get("title") or "").strip()
    for type_media in ("image", "video", "document"):
        t = m.get(type_media) or {}
        if t.get("caption"):
            return t["caption"].strip()
    return {"audio": "[message vocal — à écouter]",
            "sticker": "[autocollant]",
            "location": "[position partagée]",
            "contacts": "[contact partagé]"}.get(type_, f"[{type_}]")


def _date(horodatage):
    try:
        return datetime.fromtimestamp(int(horodatage), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


# ─────────────────────────────────────────────────────────────── 2 · ENVOYER
def envoyer(numero_id, jeton, destinataire, texte, delai=30):
    """Écrire à un client — utile SEULEMENT dans les 24 h suivant son dernier message.

    Au-delà, Meta refuse (erreur 131047) : il faut alors un modèle approuvé. C'est une règle de Meta,
    pas la nôtre, et le message d'erreur est remonté tel quel plutôt que traduit en « échec ».
    """
    donnees = {"messaging_product": "whatsapp", "to": str(destinataire), "type": "text",
               "text": {"preview_url": False, "body": texte[:4096]}}
    return _poster(f"{numero_id}/messages", jeton, donnees, delai)


def _poster(chemin, jeton, donnees, delai=30):
    requete = urllib.request.Request(
        f"{BASE}/{chemin}", data=json.dumps(donnees).encode(),
        headers={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=delai) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            err = (json.load(e) or {}).get("error", {})
            raise ErreurWhatsApp(err.get("message", f"HTTP {e.code}"), err.get("code"),
                                 err.get("error_subcode"))
        except (ValueError, TypeError):
            raise ErreurWhatsApp(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        raise ErreurWhatsApp(f"Réseau injoignable : {e.reason}")


def peut_ecrire_librement(dernier_message_client, maintenant=None):
    """La fenêtre de 24 h est-elle ouverte ? Rend (booléen, secondes restantes).

    On garde cette fonction séparée et testable : une relance qui part hors fenêtre est refusée par
    Meta, et le client croirait que le bot ne marche pas.
    """
    if not dernier_message_client:
        return False, 0
    maintenant = maintenant or datetime.now(timezone.utc)
    ecoule = (maintenant - dernier_message_client).total_seconds()
    reste = FENETRE_LIBRE - ecoule
    return reste > 0, int(max(0, reste))


# ─────────────────────────────────────────────────────────────── 3 · VÉRIFIER L'ADRESSE
def reponse_de_verification(parametres, jeton_verification):
    """Le GET de vérification de Meta -> (code HTTP, corps à renvoyer).

    Meta pose trois paramètres : `hub.mode`, `hub.verify_token`, `hub.challenge`. On renvoie le
    challenge TEL QUEL si le jeton correspond. Se tromper de jeton ici est le premier motif de
    « rien n'arrive » — le webhook n'est alors jamais validé, et Meta ne rappelle plus.
    """
    mode = parametres.get("hub.mode")
    jeton = parametres.get("hub.verify_token")
    defi = parametres.get("hub.challenge")
    if mode == "subscribe" and jeton == jeton_verification and defi:
        return 200, str(defi)
    return 403, "vérification refusée"


# ─────────────────────────────────────────────────────────────── 4 · GARDER (pour l'audit)
def ouvrir_base(chemin=None):
    """La mémoire des messages reçus : c'est ELLE qui alimente le portrait, comme un export.

    ⚠️ On y range aussi notre propre numéro (le numéro professionnel du client), pour que le portrait
    sache distinguer les paroles du client des réponses de la boutique — sans cette information, le
    comptage des « clients jamais rappelés » serait faux.
    """
    base = sqlite3.connect(chemin or BASE_DONNEES)
    base.execute("""CREATE TABLE IF NOT EXISTS messages (
        identifiant TEXT PRIMARY KEY, client TEXT, nom TEXT, texte TEXT,
        quand TEXT, type TEXT, recu_le TEXT)""")
    base.execute("""CREATE TABLE IF NOT EXISTS numeros (
        numero_id TEXT PRIMARY KEY, affichage TEXT, entreprise TEXT, vu_le TEXT)""")
    base.commit()
    return base


def enregistrer(base, recu):
    """Range les messages d'une notification. Un message déjà vu n'est PAS rangé deux fois.

    ⚠️ Meta réessaie ses notifications quand on ne répond pas assez vite : sans cette protection, le
    même message compterait plusieurs fois, et « 12 clients ont demandé le prix » deviendrait « 40 ».
    """
    maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
    neufs = 0
    for m in recu.get("messages", []):
        identifiant = m.get("identifiant") or f"{m.get('numero')}-{m.get('texte')[:40]}"
        try:
            base.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
                         (identifiant, m.get("numero"), m.get("auteur"), m.get("texte"),
                          m["quand"].isoformat() if m.get("quand") else None, m.get("type"),
                          maintenant))
            neufs += 1
        except sqlite3.IntegrityError:
            continue                       # déjà rangé : c'est une rediffusion de Meta
    if recu.get("numero_id"):
        base.execute("INSERT OR REPLACE INTO numeros VALUES (?,?,?,?)",
                     (recu["numero_id"], recu.get("numero_affichage"), None, maintenant))
    base.commit()
    return neufs


def vers_conversations(chemin=None, entreprise=None):
    """Les messages rangés, dans la MÊME forme que les exports — pour le portrait.

    C'est le point qui rend l'API utile à l'audit : `portrait.etudier()` ne sait pas si les paroles
    viennent d'un fichier exporté ou du direct. Une correction dans l'analyse profite aux deux.
    """
    base = ouvrir_base(chemin)
    base.row_factory = sqlite3.Row
    lignes = base.execute("SELECT * FROM messages ORDER BY quand").fetchall()
    messages = []
    for l in lignes:
        quand = None
        if l["quand"]:
            try:
                quand = datetime.fromisoformat(l["quand"])
            except ValueError:
                quand = None
        messages.append({"source": "whatsapp_api", "auteur": l["nom"] or l["client"],
                         "quand": quand, "texte": l["texte"]})
    return {"messages": messages, "vendeur": entreprise,
            "nb": len(messages), "sources": ["whatsapp_api"]}


# ─────────────────────────────────────────────────────────────── 5 · LE SERVEUR
def servir(jeton_verification, sur_message=None, port=8080, chemin_base=None, entreprise=None):
    """L'adresse que Meta appellera. Rend tout de suite (le service tourne dans un fil).

    ⚠️ CETTE ADRESSE DOIT ÊTRE PUBLIQUE ET EN HTTPS. Testable en local avec un tunnel ; en production,
    un serveur. C'est la dépense que le projet ne peut pas éviter — le reste est gratuit.
    """
    base = ouvrir_base(chemin_base)

    class Traitement(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):        # on ne pollue pas la sortie
            pass

        def do_GET(self):
            parametres = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            code, corps = reponse_de_verification(parametres, jeton_verification)
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(corps.encode())

        def do_POST(self):
            taille = int(self.headers.get("Content-Length") or 0)
            try:
                charge = json.loads(self.rfile.read(taille) or b"{}")
            except ValueError:
                self.send_response(400)
                self.end_headers()
                return
            recu = recevoir(charge)
            if recu["messages"]:
                enregistrer(base, recu)
                if sur_message:
                    for m in recu["messages"]:
                        try:
                            sur_message(m, base, entreprise)
                        except Exception:
                            pass
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"recu": true}')

    serveur = http.server.ThreadingHTTPServer(("0.0.0.0", port), Traitement)
    fil = threading.Thread(target=serveur.serve_forever, daemon=True)
    fil.start()
    return serveur, fil
