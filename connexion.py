#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""connexion.py — LIRE LE COMPTE DU CLIENT SANS JAMAIS DEMANDER SON MOT DE PASSE.

═══════════════════════════════════════════════════════════════════════════════════════════════════
CE QUE CE MODULE REFUSE DE FAIRE, ET POURQUOI C'EST ÉCRIT ICI PLUTÔT QU'AILLEURS.
═══════════════════════════════════════════════════════════════════════════════════════════════════

José a demandé : « L'utilisateur enregistre ses identifiants Facebook puis son numéro WhatsApp et toi
tu rentres pour faire ton audit complet. » **Réponse : non, jamais — et pas par pudeur.**

  1. **C'est interdit par Meta.** Ses conditions et ses politiques développeur proscrivent de
     collecter les identifiants d'un utilisateur. Une application qui le fait se fait bannir, et son
     propriétaire avec elle. Un outil gratuit bâti sur un ban n'a aucune valeur — il détruit celle
     qui existait avant.
  2. **Ça ressemble trait pour trait à un vol de compte.** « Donne-moi ton Facebook et ton numéro,
     je m'occupe du reste » est le message type que reçoivent les commerçants d'Abidjan avant de
     perdre leur page. Le public de José est exactement celui-là. Un formateur qui le ferait aurait
     perdu la seule chose qui ne se rachète pas : sa parole.
  3. **C'est inutile.** Meta donne MOINS de droits à un mot de passe volé qu'à un jeton accordé :
     avec un jeton, on lit les comptes publicitaires, les campagnes, les statistiques, les
     commentaires de la page et l'audience — proprement, et l'utilisateur peut couper l'accès quand
     il veut. C'est le même audit, sans jamais voir un mot de passe.

═══════════════════════════════════════════════════════════════════════════════════════════════════
COMMENT ÇA MARCHE ALORS (et ça marche aujourd'hui, sans attendre Meta).
═══════════════════════════════════════════════════════════════════════════════════════════════════

Le client va sur **l'outil de Meta lui-même** (Graph API Explorer), se connecte SUR LES PAGES DE
FACEBOOK — son mot de passe ne sort jamais de chez Meta — puis génère un jeton aux droits choisis et
le colle ici. Le jeton :

  · est LISIBLE : on peut dire exactement ce qu'il permet, et rien de plus ;
  · est RÉVOCABLE en un clic par le client, sans nous prévenir ;
  · EXPIRE tout seul (une heure pour un jeton d'utilisateur court) ;
  · ne permet JAMAIS de publier, supprimer, ni dépenser.

C'est la même mécanique que « Se connecter avec Facebook », version sans application à faire valider.

═══════════════════════════════════════════════════════════════════════════════════════════════════
CE QUE LE JETON DOIT PORTER, ET CE QUE CHAQUE DROIT APPORTE À L'AUDIT.
═══════════════════════════════════════════════════════════════════════════════════════════════════

  `ads_read`               → les comptes publicitaires et les statistiques par annonce. SANS LUI, PAS
                             D'AUDIT : c'est la matière principale.
  `business_management`    → les actifs du Business Manager (quand le compte y est rattaché).
  `pages_show_list`        → la liste des pages du client.
  `pages_read_engagement`  → les publications et leurs COMMENTAIRES — la troisième source de paroles.
  `read_insights`          → l'audience de la page : âge, sexe, villes. ⚠️ C'EST LA SEULE SOURCE
                             HONNÊTE des données démographiques. Sans elle, on ne les devine pas :
                             un âge lu dans une conversation n'existe pas, et ce module ne l'invente
                             pas (voir portrait.py).

⚠️ CE QUE CE MODULE NE FAIT PAS ENCORE, ET QU'IL FAUT SAVOIR : au-delà du compte de José, servir les
comptes de TIERS demande à Meta une validation (« App Review ») + une vérification d'entreprise. Tant
que ce n'est pas fait, chaque client passe par le jeton temporaire ci-dessus. Ce n'est pas un détail
de confort : c'est la différence entre un outil qui marche pour dix commerçants accompagnés et un
service ouvert à tous.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

VERSION_API = "v21.0"
BASE = f"https://graph.facebook.com/{VERSION_API}"

# Ce qu'on demande, et à quoi ça sert — écrit ici pour que le guide au client soit fabriqué à partir
# de la même liste, jamais recopié à la main.
DROITS = {
    "ads_read": "lire tes comptes publicitaires et tes statistiques",
    "business_management": "voir les actifs de ton Business Manager",
    "pages_show_list": "voir la liste de tes pages",
    "pages_read_engagement": "lire les commentaires de tes publications",
    "read_insights": "voir l'audience de ta page (âge, sexe, villes)",
}


class ErreurMeta(Exception):
    """Une erreur de l'API Meta, avec son code et son message d'origine — jamais réécrits."""

    def __init__(self, message, code=None, sous_code=None):
        super().__init__(message)
        self.code = code
        self.sous_code = sous_code


def appel(chemin, jeton, parametres=None, timeout=45):
    """Un appel à l'API Graph. Rend le JSON, ou lève `ErreurMeta` avec le message de Meta tel quel."""
    parametres = dict(parametres or {})
    parametres["access_token"] = jeton
    url = f"{BASE}/{chemin}?" + urllib.parse.urlencode(parametres)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            corps = json.load(e)
            err = corps.get("error", {})
            raise ErreurMeta(err.get("message", str(e)), err.get("code"), err.get("error_subcode"))
        except (ValueError, TypeError):
            raise ErreurMeta(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        raise ErreurMeta(f"Réseau injoignable depuis ce poste : {e.reason}")


def verifier_jeton(jeton):
    """Qui est ce jeton, et que peut-il faire ? C'est le PREMIER appel : avant toute lecture de données,
    on dit au client ce qu'on voit et ce qu'on ne voit pas."""
    moi = appel("me", jeton, {"fields": "id,name"})
    droits = appel("me/permissions", jeton).get("data", [])
    accordes = sorted(d["permission"] for d in droits if d.get("status") == "granted")
    return {
        "qui": moi.get("name"),
        "id": moi.get("id"),
        "droits": accordes,
        "manquants": [d for d in DROITS if d not in accordes],
        "suffisant_pour_auditer": "ads_read" in accordes,
    }


def comptes_publicitaires(jeton):
    """Les comptes publicitaires visibles par ce jeton."""
    r = appel("me/adaccounts", jeton,
              {"fields": "name,account_id,currency,account_status,amount_spent", "limit": 100})
    return r.get("data", [])


def statistiques(jeton, compte, periode="last_30d"):
    """Les statistiques PAR ANNONCE, converties dans la MÊME forme que l'export CSV.

    ⚠️ C'est le point d'articulation de tout l'outil : le moteur d'audit et le portrait ne savent pas
    d'où viennent les chiffres. Ce convertisseur rend exactement les mêmes champs qu'`lecture.py`,
    donc les mêmes contrôles s'appliquent — et une correction dans le moteur profite aux deux chemins.
    """
    champs = ("campaign_name,adset_name,ad_name,objective,spend,impressions,reach,frequency,clicks,"
              "ctr,cpm,cpc,actions,cost_per_action_type,purchase_roas")
    lignes, suite = [], True
    parametres = {"level": "ad", "date_preset": periode, "fields": champs, "limit": 200}
    while suite:
        r = appel(f"{compte}/insights", jeton, parametres)
        for d in r.get("data", []):
            lignes.append(_convertir(d))
        suivant = (r.get("paging") or {}).get("next")
        if not suivant:
            break
        # on suit la pagination fournie par Meta telle quelle — la reconstruire à la main est une
        # source classique de doublons dans les totaux
        try:
            with urllib.request.urlopen(suivant, timeout=45) as rep:
                r = json.load(rep)
            for d in r.get("data", []):
                lignes.append(_convertir(d))
            suite = bool((r.get("paging") or {}).get("next"))
        except Exception:
            suite = False
    return lignes


def _convertir(d):
    """Une ligne d'API -> une ligne de la même forme que l'export CSV.

    DEUX PIÈGES, tous les deux dans « actions » : Meta range dans cette liste TOUT ce qui s'est passé
    (achats, messages, clics sur le lien…) et il n'y a pas de champ « résultats » ni « achats »
    universel. Il faut donc y chercher les bonnes clés — et si l'achat n'y est pas, laisser la valeur
    à zéro SANS conclure : c'est le contrôle « rien ne mesure tes ventes » qui parle ensuite, pas ce
    convertisseur.
    """
    actions = {a.get("action_type"): float(a.get("value", 0)) for a in d.get("actions", []) or []}
    achats = 0.0
    for cle in ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase"):
        if cle in actions:
            achats = actions[cle]
            break
    messages = sum(v for k, v in actions.items() if "messaging" in k or "message" in k)
    resultats = achats or messages or float(d.get("clicks", 0))
    depense = float(d.get("spend", 0) or 0)
    return {
        "campagne": d.get("campaign_name", ""), "ensemble": d.get("adset_name", ""),
        "pub": d.get("ad_name", ""), "objectif": d.get("objective", ""),
        "type_resultat": ("achat" if achats else "message" if messages else "clic"),
        "depense": depense, "impressions": float(d.get("impressions", 0) or 0),
        "portee": float(d.get("reach", 0) or 0), "frequence": float(d.get("frequency", 0) or 0),
        "clics": float(d.get("clicks", 0) or 0), "ctr": float(d.get("ctr", 0) or 0),
        "cpm": float(d.get("cpm", 0) or 0), "cpc": float(d.get("cpc", 0) or 0),
        "resultats": resultats, "cout_resultat": round(depense / resultats, 2) if resultats else 0.0,
        "achats": achats, "valeur_achats": 0.0,
    }


def pages(jeton):
    """Les pages du client."""
    return appel("me/accounts", jeton, {"fields": "name,id,category,fan_count", "limit": 100}).get("data", [])


def commentaires(jeton, page_id, limite=200):
    """Les commentaires des publications d'une page — la troisième source de paroles du client."""
    r = appel(f"{page_id}/feed", jeton,
              {"fields": "message,created_time,comments.limit(50){message,from,created_time}",
               "limit": 50})
    sortis = []
    for publication in r.get("data", []):
        for c in (publication.get("comments") or {}).get("data", []):
            texte = (c.get("message") or "").strip()
            if texte:
                sortis.append(texte)
        if len(sortis) >= limite:
            break
    return sortis


def audience_page(jeton, page_id):
    """L'audience de la page : âge, sexe, villes. LA SEULE SOURCE HONNÊTE DES DONNÉES DÉMOGRAPHIQUES.

    Hmm — et elle peut revenir VIDE : Meta a fortement réduit ces mesures, et une page récente n'a
    souvent rien. On rend alors un dictionnaire vide, jamais des valeurs inventées.
    """
    try:
        r = appel(f"{page_id}/insights", jeton, {"metric": "page_fans_gender_age,page_fans_city",
                                                 "period": "lifetime"})
    except ErreurMeta:
        return {}
    sortie = {}
    for bloc in r.get("data", []):
        nom = bloc.get("name")
        valeurs = (bloc.get("values") or [{}])[0].get("value") or {}
        if isinstance(valeurs, dict):
            sortie[nom] = sorted(valeurs.items(), key=lambda kv: -kv[1])[:12]
    return sortie


def _section_facultative(nom, fonction, *args, defaut=None, soucis=None):
    """Appelle une section FACULTATIVE de l'audit sans jamais faire tomber le rapport.

    ⛔ LA LEÇON, ET ELLE A COÛTÉ UN VRAI ESSAI RATÉ DEVANT LE PROPRIÉTAIRE (10/10/2026).
    José a connecté son compte, Facebook a accepté, et la page a affiché : « Une erreur inattendue
    est survenue (ErreurMeta) ». Cause : l'audit lisait l'AUDIENCE de la page, qui exige
    read_insights — précisément la permission qu'il avait fallu RETIRER pour que la connexion
    fonctionne. Une section de confort emportait tout le rapport avec elle.

    Règle qui en découle : ce qui est indispensable (les statistiques publicitaires) a le droit de
    faire échouer l'audit. Ce qui est un BONUS (audience, commentaires, liste des pages) se contente
    d'être annoncé comme indisponible, et le rapport continue. Un rapport incomplet et honnête vaut
    mille fois un rapport mort.
    """
    try:
        return fonction(*args)
    except Exception as e:
        detail = f"{type(e).__name__}: {str(e)[:200]}"
        print(f"[audit] section facultative « {nom} » indisponible — {detail}", flush=True)
        if soucis is not None:
            soucis.append(f"{nom} : indisponible")
        return defaut


def audit_complet(jeton, periode="last_30d", page_id=None):
    """Tout l'audit, depuis le compte du client : jetons -> données -> lignes prêtes pour le moteur."""
    etat = verifier_jeton(jeton)
    resultat = {"etat_du_jeton": etat, "comptes": [], "lignes": [], "commentaires": [],
                "audience": {}, "pages": [], "soucis": []}
    if not etat["suffisant_pour_auditer"]:
        # ON S'ARRÊTE LÀ, ET ON LE DIT. Continuer donnerait un rapport vide que le client lirait comme
        # « tout va bien » — le pire des mensonges, parce qu'il est silencieux.
        return resultat

    print(f"[audit] jeton accepté pour {etat.get('qui')} — autorisations : "
          f"{', '.join(etat.get('droits') or []) or 'aucune'}", flush=True)

    # ── LE CŒUR : sans ça, il n'y a pas d'audit, et on doit le dire clairement
    resultat["comptes"] = comptes_publicitaires(jeton)
    print(f"[audit] {len(resultat['comptes'])} compte(s) publicitaire(s) accessible(s)", flush=True)
    for compte in resultat["comptes"]:
        resultat["lignes"] += statistiques(jeton, "act_" + compte["account_id"], periode)
    print(f"[audit] {len(resultat['lignes'])} ligne(s) de statistiques", flush=True)

    # ── LES BONUS : jamais au prix du rapport
    resultat["pages"] = _section_facultative("la liste des pages", pages, jeton,
                                             defaut=[], soucis=resultat["soucis"])
    cible = page_id or (resultat["pages"][0]["id"] if resultat["pages"] else None)
    if cible:
        resultat["commentaires"] = _section_facultative(
            "les commentaires", commentaires, jeton, cible, defaut=[], soucis=resultat["soucis"])
        resultat["audience"] = _section_facultative(
            "l'audience de la page", audience_page, jeton, cible, defaut={},
            soucis=resultat["soucis"])
    return resultat
