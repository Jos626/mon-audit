#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bot-audit.py — L'APPLICATION, côté client. C'est CE bot que le commerçant installe.

POURQUOI UN BOT TELEGRAM, ET PAS UNE APPLICATION À TÉLÉCHARGER. Le client n'a rien à installer, rien à
créer, aucun mot de passe à retenir : il appuie sur DÉMARRER, il envoie ses fichiers, il reçoit ses
rapports. C'est ce qui se fait de plus simple à utiliser sur un téléphone — et sur cette cible, la
simplicité d'accès vaut mieux que n'importe quelle interface graphique. Une véritable application web
(installable sur l'écran d'accueil) viendra par-dessus, servie par le même moteur, le jour où le
serveur existera pour la connexion WhatsApp en direct.

CE QUE CE BOT NE FERA JAMAIS, ET C'EST LE CŒUR DU PRODUIT :
  · il ne demande **aucun identifiant Facebook** — le client accorde un **jeton révocable** depuis
    l'outil de Meta, et le jeton **n'est jamais écrit sur le disque** : il vit le temps de l'audit ;
  · il ne demande **aucun code QR** de WhatsApp ;
  · il ne devine rien : ce qui manque, il le dit.

LES TROIS PORTES D'ENTRÉE : le jeton Meta (l'audit du compte), les fichiers de conversations
(WhatsApp, Messenger, commentaires → le portrait), le fichier des ventes (les chiffres qui tranchent).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
os.chdir(ICI)

import audit           # noqa: E402
import connexion       # noqa: E402
import conversations   # noqa: E402
import guide           # noqa: E402
import lecture         # noqa: E402
import portrait        # noqa: E402
import portrait_texte  # noqa: E402
import rapport         # noqa: E402

SECRETS = os.path.expanduser("~/.hermes/secrets/telegram-bot-audit-token.txt")
CLIENTS = os.path.join(ICI, "clients")
MAX_MESSAGE = 4000

# Un jeton Meta ressemble à « EAA… » et fait des dizaines de caractères. On ne le confond ni avec un
# message de client, ni avec un fichier.
MOTIF_JETON = re.compile(r"^EAA[A-Za-z0-9_\-]{30,}$")


def lire_jeton():
    with open(SECRETS, encoding="utf-8") as f:
        return f.read().strip()


def api(jeton, methode, donnees=None, timeout=60):
    url = f"https://api.telegram.org/bot{jeton}/{methode}"
    if donnees is None:
        return json.load(urllib.request.urlopen(url, timeout=timeout))
    charge = json.dumps(donnees).encode()
    requete = urllib.request.Request(url, data=charge,
                                     headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(requete, timeout=timeout))


def envoyer(jeton, chat, texte, clavier=None):
    """Envoie un message, découpé si besoin — et JAMAIS coupé au milieu d'un constat.

    ⚠️ Un rapport fait autour de 10 000 signes, soit trois messages. Couper à l'aveugle au 4 000e
    caractère trancherait un constat en deux et le client lirait la moitié d'une phrase d'argent.
    On coupe donc sur les lignes de séparation, et on garde le texte entier.
    """
    morceaux, courant = [], ""
    for bloc in texte.split("\n"):
        if len(courant) + len(bloc) + 1 > MAX_MESSAGE:
            morceaux.append(courant)
            courant = bloc
        else:
            courant = (courant + "\n" + bloc) if courant else bloc
    if courant:
        morceaux.append(courant)
    for i, morceau in enumerate(morceaux):
        donnees = {"chat_id": chat, "text": morceau, "parse_mode": "Markdown",
                   "disable_web_page_preview": True}
        if clavier and i == len(morceaux) - 1:
            donnees["reply_markup"] = clavier
        try:
            api(jeton, "sendMessage", donnees)
        except Exception:
            # le Markdown est la cause la plus fréquente d'un refus : on renvoie le texte brut plutôt
            # que de laisser le client sans réponse
            api(jeton, "sendMessage", {"chat_id": chat, "text": morceau,
                                       "disable_web_page_preview": True})
        time.sleep(0.4)


def telecharger(jeton, identifiant_fichier, destination):
    fiche = api(jeton, "getFile", {"file_id": identifiant_fichier})["result"]
    url = f"https://api.telegram.org/file/bot{jeton}/{fiche['file_path']}"
    urllib.request.urlretrieve(url, destination)
    return destination


def dossier_client(chat):
    chemin = os.path.join(CLIENTS, str(chat))
    os.makedirs(chemin, exist_ok=True)
    return chemin


def classer_fichier(chemin, nom):
    """Reconnaître ce que le client vient d'envoyer, PAR LE CONTENU (jamais par le nom du fichier).

    Un « export(3).csv » peut être l'export d'Ads Manager comme la liste de ses ventes : c'est
    l'en-tête qui le dit. Se fier au nom ferait analyser des ventes comme un compte publicitaire.
    """
    minuscule = (nom or "").lower()
    if minuscule.endswith(".json"):
        return "messenger"
    try:
        debut = open(chemin, encoding="utf-8", errors="replace").read(4000).lower()
    except OSError:
        return "inconnu"
    if minuscule.endswith(".csv") or "\t" in debut[:200]:
        if any(m in debut for m in ("montant dépensé", "amount spent", "impressions", "cpm")):
            return "export_publicitaire"
        return "ventes"
    if minuscule.endswith(".txt") or " - " in debut[:400] or "[" in debut[:200]:
        return "conversations"
    return "commentaires"


def accumuler(chemin_dossier, categorie, texte):
    """Range ce qui arrive, source par source, pour que la mémoire du client s'enrichisse."""
    chemin = os.path.join(chemin_dossier, categorie + ".txt")
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(texte.rstrip() + "\n")
    return chemin


def lancer_audit(jeton_bot, chat, dossier, jeton_meta=None, periode="last_30d", dire=None):
    """Le travail : les deux rapports, à partir de tout ce qui a été réuni pour ce client."""
    dires = dire or (lambda t: envoyer(jeton_bot, chat, t))
    sources = []
    for categorie, fichier in (("conversations", "conversations.txt"),
                               ("commentaires", "commentaires.txt"),
                               ("messenger", "messenger.txt")):
        chemin = os.path.join(dossier, fichier)
        if os.path.exists(chemin) and os.path.getsize(chemin) > 0:
            sources.append(chemin)
    export = os.path.join(dossier, "export_publicitaire.csv")
    ventes = os.path.join(dossier, "ventes.csv")

    fait_quelque_chose = False

    if jeton_meta:
        dires("⏳ *J'interroge ton compte publicitaire…* (quelques secondes)")
        try:
            resultat = connexion.audit_complet(jeton_meta, periode)
        except connexion.ErreurMeta as e:
            # ⚠️ SANS CE GARDE, UN JETON EXPIRÉ NE RÉPONDAIT RIEN DU TOUT. L'erreur remontait jusqu'à
            # la boucle, qui l'écrivait dans sa sortie — c'est-à-dire nulle part pour le client. Il
            # aurait attendu un rapport qui ne viendrait jamais, sans savoir pourquoi. Un jeton vit
            # une heure : le cas est fréquent, pas exceptionnel.
            detail = str(e)
            if "expir" in detail.lower() or "session" in detail.lower():
                conseil = ("Ton jeton a expiré — ils vivent environ une heure. Refais-le en trois "
                           "gestes (/guide) et renvoie-le.")
            else:
                conseil = "Vérifie que le jeton a bien été copié en entier, sans espace au début."
            dires(f"⛔ *Meta a refusé ce jeton.*\n\n_« {detail[:200]} »_\n\n{conseil}")
            return
        etat = resultat["etat_du_jeton"]
        if not etat["suffisant_pour_auditer"]:
            dires(f"⛔ *Je ne peux pas lire ton compte publicitaire.*\n\n"
                  f"J'ai reconnu : *{etat['qui']}*. Les droits accordés sont : "
                  f"{', '.join(etat['droits']) or 'aucun'}.\n\n"
                  f"Il manque le plus important : **`ads_read`** — celui qui autorise la lecture des "
                  f"comptes publicitaires et de leurs statistiques. Refais le jeton en cochant "
                  f"`ads_read` (voir /guide), et renvoie-le.")
            return
        if not resultat["lignes"]:
            dires("⛔ *Le jeton est bon, mais je ne vois aucune dépense sur 30 jours.*\n\n"
                  "Soit ce compte n'a rien dépensé sur la période, soit il n'est pas dans ceux que "
                  "ce jeton voit. Vérifie que tu as autorisé le compte qui diffuse.")
            return
        pseudo = {"total": {k: sum(l.get(k, 0) for l in resultat["lignes"])
                            for k in ("depense", "impressions", "clics", "resultats", "achats",
                                      "valeur_achats")} | {"lignes": len(resultat["lignes"])},
                  "absentes": [], "souhaitees_absentes": []}
        noms = ", ".join(c.get("name", "?") for c in resultat["comptes"][:3])
        dires(rapport.construire(audit.auditer(pseudo, {}), noms or "ton compte publicitaire")
              + "\n\n_Source : ton compte publicitaire, lu en direct (30 derniers jours). "
                "Ton jeton n'a pas été conservé._")
        fait_quelque_chose = True
    elif os.path.exists(export):
        lu = lecture.lire(export)
        dires(rapport.construire(audit.auditer(lu, {}), "ton export")
              + f"\n\n_Source : ton export Ads Manager ({lu['total']['lignes']} lignes)._")
        fait_quelque_chose = True

    if sources or os.path.exists(ventes):
        lues = conversations.lire(sources) if sources else {"messages": [], "nb": 0, "sources": []}
        etude = portrait.etudier(lues, fichier_clients=ventes if os.path.exists(ventes) else None)
        dires(portrait_texte.construire(etude))
        fait_quelque_chose = True

    if not fait_quelque_chose:
        dires(_a_envoyer())


def _a_envoyer():
    return ("🎯 *Il me faut au moins une chose à lire.*\n\n"
            "· **Ton jeton Meta** — un long texte qui commence par `EAA…` (voir /guide) : "
            "j'analyse ton compte publicitaire.\n"
            "· **L'export d'une discussion WhatsApp** (`.txt`) : je lis ce que tes clients demandent.\n"
            "· **Le dossier Messenger** (`message_1.json`) : la même chose, côté Facebook.\n"
            "· **Les commentaires de ta page** — colle-les ici, un par ligne.\n"
            "· **Ton fichier de ventes** (`.csv`) : il donne les chiffres qui tranchent.\n\n"
            "Envoie ce que tu as, puis écris /audit.")


CLAVIER = {"keyboard": [["/guide", "/audit"], ["/aide"]],
           "resize_keyboard": True, "is_persistent": True}


def _bienvenue():
    return ("👋 *Mon Audit* — je te dis pourquoi ta publicité ne rapporte pas.\n\n"
            "Je lis ton compte publicitaire et les paroles de tes clients, puis je te rends **deux "
            "rapports** :\n\n"
            "1️⃣ **L'audit du compte** — où part ton argent, ce qui bloque, ce qu'il ne faut surtout "
            "pas toucher.\n"
            "2️⃣ **Le portrait de ton client** — ce qu'il demande, ce qui le bloque, ses mots exacts, "
            "ses villes, ses horaires — et les clients jamais rappelés.\n\n"
            "⚠️ *Je ne te demanderai JAMAIS ton mot de passe Facebook, ni de scanner un code QR.* "
            "Tu accordes un **jeton révocable** (voir /guide), et je ne le conserve pas.\n\n"
            "👉 Appuie sur *Démarrer*, puis envoie ce que tu as. **/guide** t'explique quoi.\n"
            "_Rien n'est inventé : ce qui manque, je te dis que ça manque._")


def _aide():
    return ("❓ *Comment ça se passe*\n\n"
            "1. Envoie-moi tes fichiers (ou ton jeton) — ils s'ajoutent au fur et à mesure.\n"
            "2. Écris **/audit** : je te rends les rapports.\n"
            "3. Tu peux m'envoyer d'autres conversations plus tard, et redemander /audit.\n\n"
            "*Les commandes*\n"
            "   /guide — comment obtenir chaque chose (5 étapes par source)\n"
            "   /audit — lance les rapports sur ce que tu m'as envoyé\n"
            "   /mesdonnees — ce que j'ai reçu de toi\n"
            "   /efface — supprime tout ce que tu m'as envoyé\n\n"
            "*Ce que je ne fais pas*\n"
            "   · aucun mot de passe, aucun code QR\n"
            "   · aucun âge, revenu ou intention inventés\n"
            "   · rien n'est partagé avec un autre client")


def traiter(jeton_bot, maj):
    message = maj.get("message") or maj.get("edited_message")
    if not message:
        return
    chat = message["chat"]["id"]
    dossier = dossier_client(chat)
    texte = (message.get("text") or "").strip()

    if texte.startswith("/start"):
        envoyer(jeton_bot, chat, _bienvenue(), CLAVIER)
        return
    if texte.startswith("/guide"):
        envoyer(jeton_bot, chat, guide.resume())
        for bloc in guide.TOUT:
            envoyer(jeton_bot, chat, bloc)
        return
    if texte.startswith("/aide"):
        envoyer(jeton_bot, chat, _aide())
        return
    if texte.startswith("/mesdonnees"):
        envoyer(jeton_bot, chat, _mes_donnees(dossier))
        return
    if texte.startswith("/efface"):
        import shutil
        shutil.rmtree(dossier, ignore_errors=True)
        envoyer(jeton_bot, chat, "🗑️ *C'est effacé.* Tout ce que tu m'avais envoyé est supprimé. "
                                 "Tu peux recommencer quand tu veux.")
        return
    if texte.startswith("/audit"):
        lancer_audit(jeton_bot, chat, dossier)
        return

    # ── UN JETON META ────────────────────────────────────────────────────────────────────────────
    if MOTIF_JETON.match(texte):
        # ⚠️ LE JETON N'EST PAS ÉCRIT SUR LE DISQUE : il ne vit que le temps de cet appel. Le
        # commerçant devra donc le renvoyer pour un nouvel audit — c'est le prix de la tranquillité.
        lancer_audit(jeton_bot, chat, dossier, jeton_meta=texte)
        return

    # ── UN FICHIER ───────────────────────────────────────────────────────────────────────────────
    document = message.get("document")
    if document:
        nom = document.get("file_name") or "fichier"
        destination = os.path.join(dossier, "recu-" + str(int(time.time())) + "-" + nom)
        try:
            telecharger(jeton_bot, document["file_id"], destination)
        except Exception as e:
            envoyer(jeton_bot, chat, f"⚠️ Je n'ai pas réussi à récupérer ce fichier ({e}). "
                                     f"Réessaie, ou colle le contenu ici.")
            return
        categorie = classer_fichier(destination, nom)
        if categorie == "messenger":
            lues = conversations.lire([destination])
            accumuler(dossier, "messenger", "\n".join(
                f"[{m['quand']:%d/%m/%Y %H:%M}] {m['auteur']}: {m['texte']}"
                if m["quand"] else f"{m['auteur']}: {m['texte']}" for m in lues["messages"]))
            envoyer(jeton_bot, chat, f"✅ *Messenger reçu* : {lues['nb']} messages de cette "
                                     f"conversation. Envoie les autres si tu veux, puis /audit.")
        elif categorie == "conversations":
            # on garde le fichier tel quel : le lecteur WhatsApp reconnaît son format, et le lecteur
            # de commentaires reconnaît le sien. Reconstruire risquerait de perdre les dates.
            with open(os.path.join(dossier, "conversations.txt"), "a", encoding="utf-8") as f:
                f.write(open(destination, encoding="utf-8", errors="replace").read() + "\n")
            lues = conversations.lire([destination])
            envoyer(jeton_bot, chat,
                    f"✅ *Conversation reçue* : {lues['nb']} messages "
                    f"({', '.join(lues['sources']) or 'vide'}). "
                    f"{'Envoie les autres discussions, puis ' if lues['nb'] < 40 else ''}/audit.")
        elif categorie == "export_publicitaire":
            import shutil
            shutil.copy(destination, os.path.join(dossier, "export_publicitaire.csv"))
            lu = lecture.lire(destination)
            envoyer(jeton_bot, chat,
                    f"✅ *Export publicitaire reçu* : {lu['total']['lignes']} lignes, "
                    f"{lu['total']['depense']:,.0f} F de dépenses. Écris /audit."
                    .replace(",", " "))
        elif categorie == "ventes":
            import shutil
            shutil.copy(destination, os.path.join(dossier, "ventes.csv"))
            envoyer(jeton_bot, chat, "✅ *Fichier de ventes reçu.* Il me donne tes vrais chiffres. "
                                     "Écris /audit.")
        else:
            envoyer(jeton_bot, chat, "🤔 Je n'ai pas reconnu ce fichier. Envoie-moi : un export "
                                     "WhatsApp (.txt), le dossier Messenger (.json), un export Ads "
                                     "Manager (.csv), ou ton fichier de ventes (.csv).")
        return

    # ── DU TEXTE : les commentaires, ou autre chose ──────────────────────────────────────────────
    if texte and not texte.startswith("/"):
        if len(texte) > 12:
            accumuler(dossier, "commentaires", texte)
            envoyer(jeton_bot, chat, "📝 *Noté* comme commentaires de ta page. "
                                     "Colle-les à la suite, un par ligne, puis /audit.")
        else:
            envoyer(jeton_bot, chat, _a_envoyer())


def _mes_donnees(dossier):
    if not os.path.isdir(dossier):
        return "📂 Tu ne m'as encore rien envoyé. /guide t'explique quoi m'envoyer."
    lignes = ["📂 *Ce que tu m'as envoyé*", ""]
    for fichier in sorted(os.listdir(dossier)):
        if fichier.startswith("recu-"):
            continue
        taille = os.path.getsize(os.path.join(dossier, fichier))
        lignes.append(f"   · **{fichier}** — {taille / 1024:.0f} Ko")
    if len(lignes) == 2:
        lignes.append("   _(rien pour l'instant)_")
    lignes += ["", "Écris /audit pour lancer les rapports, ou /efface pour tout supprimer."]
    return "\n".join(lignes)


def battre():
    dossier = os.path.join(ICI, "battement.json")
    with open(dossier, "w", encoding="utf-8") as f:
        json.dump({"vu": time.time(), "vu_lisible": time.strftime("%Y-%m-%d %H:%M:%S")}, f)


def boucle():
    jeton = lire_jeton()
    moi = api(jeton, "getMe")["result"]
    print(f"Mon Audit démarré : @{moi['username']} ({moi['id']})", flush=True)
    decalage = 0
    while True:
        try:
            reponse = api(jeton, "getUpdates",
                          {"offset": decalage, "timeout": 50,
                           "allowed_updates": ["message", "edited_message"]}, timeout=70)
            for maj in reponse.get("result", []):
                decalage = maj["update_id"] + 1
                try:
                    traiter(jeton, maj)
                except Exception as e:
                    print("erreur sur un message :", type(e).__name__, str(e)[:160], flush=True)
            battre()
        except Exception as e:
            print("boucle :", type(e).__name__, str(e)[:160], flush=True)
            time.sleep(5)


if __name__ == "__main__":
    boucle()
