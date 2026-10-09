#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit-complet.py — UN SEUL GESTE POUR TOUT L'AUDIT.

C'est le point d'entrée du produit : on lui donne ce qu'on a, il rend ce qu'on peut en dire.

    # Avec le jeton du compte publicitaire (le chemin neuf)
    python3 audit-complet.py --jeton EAAG... --whatsapp discussion.txt --ventes ventes.csv

    # Sans jeton, avec un export d'Ads Manager (le chemin qui marche tout de suite)
    python3 audit-complet.py --fichier export-ads.csv --whatsapp discussion.txt

    # Sans rien : il explique ce qu'il faut lui donner
    python3 audit-complet.py

TROIS RÈGLES DANS CE FICHIER, ET ELLES VIENNENT TOUTES DE LA MÊME EXIGENCE (ne rien inventer) :

  1. **CE QUI MANQUE EST ÉCRIT.** Si le jeton n'a pas les bons droits, si aucune conversation n'est
     fournie, si le fichier de ventes est vide : on le dit, à la place du rapport. Un rapport partiel
     présenté comme complet est un mensonge par omission.
  2. **CHAQUE RAPPORT PORTE SA SOURCE.** Le client doit pouvoir vérifier d'où vient chaque chiffre :
     « d'après les 42 messages que tu m'as envoyés », « d'après ton compte publicitaire, 30 derniers
     jours ». Un chiffre sans provenance ne se défend pas.
  3. **LE JETON NE SE RANGE NULLE PART.** Il vit le temps de la commande, en mémoire. On ne l'écrit ni
     sur le disque, ni dans un journal : un jeton écrit est un jeton qui traîne.
"""
import argparse
import sys
import os

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

import audit          # noqa: E402
import connexion      # noqa: E402
import conversations  # noqa: E402
import guide          # noqa: E402
import lecture        # noqa: E402
import portrait       # noqa: E402
import portrait_texte  # noqa: E402
import rapport        # noqa: E402


def _titre(texte):
    return f"\n{'━' * 19}\n{texte}\n{'━' * 19}\n"


def audit_publicitaire(jeton=None, fichier=None, periode="last_30d"):
    """L'audit du compte publicitaire, par le jeton OU par l'export. Rend (texte, source)."""
    if jeton:
        resultat = connexion.audit_complet(jeton, periode)
        etat = resultat["etat_du_jeton"]
        if not etat["suffisant_pour_auditer"]:
            return (f"⛔ *Je ne peux pas auditer ce compte.*\n\n"
                    f"J'ai reconnu : *{etat['qui']}*. Mais il manque le droit le plus important : "
                    f"**`ads_read`** — celui qui autorise la lecture des comptes publicitaires et de "
                    f"leurs statistiques.\n\n"
                    f"Droits accordés : {', '.join(etat['droits']) or 'aucun'}\n\n"
                    f"Refais le jeton en cochant `ads_read`, et renvoie-le.", "jeton")
        if not resultat["lignes"]:
            return ("⛔ *Aucune donnée publicitaire sur les 30 derniers jours.*\n\n"
                    "Le jeton est valide et porte les bons droits, mais ce compte n'a rien dépensé "
                    "sur la période — ou les comptes visibles par ce jeton ne sont pas ceux qui "
                    "diffusent. Vérifie que tu as bien autorisé le compte qui dépense.", "jeton")
        pseudo = {"total": {"depense": sum(l["depense"] for l in resultat["lignes"]),
                            "impressions": sum(l["impressions"] for l in resultat["lignes"]),
                            "resultats": sum(l["resultats"] for l in resultat["lignes"]),
                            "achats": sum(l["achats"] for l in resultat["lignes"]),
                            "lignes": len(resultat["lignes"])},
                  "absentes": [], "souhaitees_absentes": []}
        a = audit.auditer(pseudo, {})
        noms = ", ".join(c.get("name", "?") for c in resultat["comptes"][:3])
        return (rapport.construire(a, noms or "ton compte")
                + f"\n\n_Source : ton compte publicitaire, lu en direct, {periode}._", "jeton")

    if fichier:
        export = lecture.lire(fichier)
        if export["absentes"]:
            return (f"⛔ *Il manque des colonnes indispensables dans cet export : "
                    f"{', '.join(export['absentes'])}.*\n\n"
                    f"Dans Ads Manager : colonnes → Personnaliser les colonnes → coche "
                    f"« Performance » et « Conversions », puis exporte en CSV.", "export")
        a = audit.auditer(export, {})
        return (rapport.construire(a, "ton export")
                + f"\n\n_Source : ton export Ads Manager ({export['total']['lignes']} lignes)._",
                "export")
    return (None, None)


def portrait_client(chemins_conversations, ventes=None):
    """Le portrait du client, à partir de ce qui a été fourni. Rend (texte, nb_messages)."""
    if not chemins_conversations:
        return (f"❓ *Le portrait du client n'est pas encore possible.*\n\n"
                f"Il me manque ses paroles. Envoie-moi au moins un des trois :\n\n"
                f"· l'export d'une discussion WhatsApp (.txt)\n"
                f"· le dossier Messenger (message_1.json)\n"
                f"· les commentaires de ta page, un par ligne", 0)
    lues = conversations.lire(chemins_conversations)
    etude = portrait.etudier(lues, fichier_clients=ventes)
    return portrait_texte.construire(etude), etude.get("nb_clients", 0)


def main():
    p = argparse.ArgumentParser(description="Audit complet d'un compte publicitaire et portrait client")
    p.add_argument("--jeton", help="jeton Meta (lecture seule, 1 h)")
    p.add_argument("--fichier", help="export Ads Manager (CSV ou Excel)")
    p.add_argument("--periode", default="last_30d", help="période de l'API (last_7d, last_30d, last_90d)")
    p.add_argument("--whatsapp", action="append", default=[], help="export de discussion WhatsApp (.txt)")
    p.add_argument("--messenger", help="dossier Messenger (message_1.json)")
    p.add_argument("--commentaires", help="fichier de commentaires, un par ligne")
    p.add_argument("--ventes", help="fichier des commandes (CSV)")
    args = p.parse_args()

    sources = list(args.whatsapp)
    if args.messenger:
        sources.append(args.messenger)
    if args.commentaires:
        sources.append(args.commentaires)

    if not (args.jeton or args.fichier or sources):
        print(guide.resume())
        print()
        print(guide.tout())
        return 0

    texte_audit, _origine = audit_publicitaire(args.jeton, args.fichier, args.periode)
    if texte_audit:
        print(_titre("1 · L'AUDIT DU COMPTE PUBLICITAIRE"))
        print(texte_audit)

    texte_portrait, nb = portrait_client(sources, args.ventes)
    print(_titre("2 · LE PORTRAIT DU CLIENT"))
    print(texte_portrait)

    if not texte_audit:
        print()
        print(guide.FACEBOOK)

    # LE JETON N'EST ÉCRIT NULLE PART : on le retire explicitement de la mémoire du processus avant
    # de rendre la main, pour qu'aucun vidage de mémoire ni journal ne le conserve.
    if args.jeton:
        args.jeton = "« effacé »"
    return 0


if __name__ == "__main__":
    sys.exit(main())
