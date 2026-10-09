#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rapport.py — LE TEXTE QUE LE COMMERÇANT LIT.

Trois principes d'écriture, tous appris à ses dépens.

  1. **ON COMMENCE PAR SON ARGENT.** Le premier écran répond à la seule question qu'il se pose :
     combien ça me coûte, et où. Les bonnes pratiques viennent après, jamais avant.

  2. **CHAQUE CONSTAT FINIT PAR UN GESTE.** Pas « améliore ton ciblage » — quel geste, dans quel
     ordre, où le faire. Un audit qui laisse le client devant sa page sans savoir quoi toucher ne
     vaut pas mieux qu'un devis.

  3. **LE TEXTE DIT AUSSI CE QU'IL NE SAIT PAS.** Les colonnes absentes de l'export, la marge
     inconnue, le volume insuffisant : tout ce qui empêche une conclusion est écrit noir sur blanc.
     C'est ce qui distingue un audit d'une brochure commerciale — et c'est exactement ce que José
     exige de tout ce qu'il publie.
"""
from audit import GRAVITES
from lecture import argent

PASTILLE = {"critique": "🔴", "élevé": "🟠", "moyen": "🟡", "faible": "⚪",
            "pour information": "ℹ️"}
NOM_GRAVITE = {"critique": "À RÉPARER TOUT DE SUITE", "élevé": "À TRAITER CETTE SEMAINE",
               "moyen": "À AMÉLIORER", "faible": "DÉTAIL", "pour information": "BON À SAVOIR"}


def fcfa(valeur):
    """Un montant lisible : « 1 250 000 F CFA », jamais « 1250000.0 ».

    ⚠️ ELLE PASSE PAR LA MÊME FONCTION QUE LE MOTEUR (09/10/2026). Les deux écrivaient les milliers
    différemment — rapport avec une espace normale, moteur avec une espace fine insécable. Les deux
    sont françaises, mais un rapport qui mélange les deux écritures a l'air traduit par une machine,
    et un client qui doute de la langue doute des chiffres. Une seule fonction décide désormais.
    """
    if valeur is None:
        return "—"
    return argent(valeur) + " F CFA"


def _entete(audit, nom_compte=""):
    total = audit["total"]
    lignes = ["📊 *AUDIT DE TON COMPTE PUBLICITAIRE*"]
    if nom_compte:
        lignes.append(f"_{nom_compte}_")
    lignes.append("")
    faits = [f"**{fcfa(total['depense'])}** dépensés"]
    if total.get("impressions"):
        faits.append(f"{total['impressions']:,.0f} affichages".replace(",", " "))
    if total.get("resultats"):
        faits.append(f"**{int(total['resultats'])}** résultats")
    if total.get("achats"):
        faits.append(f"**{int(total['achats'])}** achats")
    lignes.append(" · ".join(faits))
    if audit["argent_en_jeu"]:
        lignes.append("")
        lignes.append(f"💰 **{fcfa(audit['argent_en_jeu'])} sont en jeu** dans ce que je te montre "
                      f"ci-dessous.")
    return "\n".join(lignes)


def _bloc(trouvaille, numero):
    t = trouvaille
    lignes = [f"*{numero}. {t['titre']}*",
              f"{PASTILLE.get(t['gravite'], '•')} _{NOM_GRAVITE.get(t['gravite'], '')}_",
              ""]
    if t["argent"]:
        lignes.append(f"💸 **{fcfa(t['argent'])}** concernés")
    lignes.append(t["constat"])
    lignes.append("")
    lignes.append(t["pourquoi"])
    if t["action"]:
        lignes.append("")
        lignes.append("*Ce que tu fais :*")
        for i, geste in enumerate(t["action"], 1):
            lignes.append(f"   {i}. {geste}")
    return "\n".join(lignes)


def construire(audit, nom_compte=""):
    """Le rapport complet, prêt à envoyer."""
    morceaux = [_entete(audit, nom_compte)]

    problemes = [t for t in audit["trouvailles"] if t["gravite"] in ("critique", "élevé")]
    secondaires = [t for t in audit["trouvailles"] if t["gravite"] in ("moyen", "faible")]
    infos = [t for t in audit["trouvailles"] if t["gravite"] == "pour information"]
    positif = [t for t in audit["trouvailles"] if t["code"] == "CE_QUI_MARCHE"]
    infos = [t for t in infos if t["code"] != "CE_QUI_MARCHE"]

    if not problemes and not secondaires:
        morceaux.append("")
        morceaux.append("✅ *Aucun problème structurel dans cet export.*\n"
                        "Rien de ce que je sais chercher ne déclenche sur tes chiffres : la mesure "
                        "des ventes est là, le budget vise la vente, et rien ne brûle "
                        "anormalement. C'est rare, et ça mérite d'être dit.")

    if problemes:
        morceaux.append("")
        morceaux.append("━━━━━━━━━━━━━━━━━━━")
        morceaux.append("🔎 *CE QUI NE MARCHE PAS*")
        for i, t in enumerate(problemes, 1):
            morceaux.append("")
            morceaux.append(_bloc(t, i))

    if secondaires:
        morceaux.append("")
        morceaux.append("━━━━━━━━━━━━━━━━━━━")
        morceaux.append("🔧 *CE QUI PEUT MIEUX FAIRE*")
        for i, t in enumerate(secondaires, len(problemes) + 1):
            morceaux.append("")
            morceaux.append(_bloc(t, i))

    if positif:
        morceaux.append("")
        morceaux.append("━━━━━━━━━━━━━━━━━━━")
        morceaux.append("✅ *CE QUI MARCHE — N'Y TOUCHE PAS*")
        for t in positif:
            morceaux.append("")
            morceaux.append(_bloc(t, 1))

    if infos:
        morceaux.append("")
        morceaux.append("━━━━━━━━━━━━━━━━━━━")
        morceaux.append("ℹ️ *À SAVOIR SUR CE RAPPORT*")
        for t in infos:
            morceaux.append("")
            morceaux.append(f"• *{t['titre']}*\n{t['constat']}\n{t['pourquoi']}")
            for geste in t["action"]:
                morceaux.append(f"   → {geste}")

    profil = audit.get("profil") or {}
    manques = []
    if not profil.get("marge"):
        manques.append("**ta marge par vente** (ce qu'il te reste sur une commande) — sans elle, "
                       "je ne peux pas te dire si une commande te fait gagner ou perdre")
    if not profil.get("fermeture"):
        manques.append("**où tes ventes se ferment** (sur ton site, sur WhatsApp, en boutique) — "
                       "cela change ce qu'il faut demander à Meta")
    if not profil.get("panier"):
        manques.append("**ton panier moyen** — il donne le plafond à ne pas dépasser par commande")
    if manques:
        morceaux.append("")
        morceaux.append("━━━━━━━━━━━━━━━━━━━")
        morceaux.append("❓ *CE QUI ME MANQUE POUR ÊTRE PLUS PRÉCIS*")
        for m in manques:
            morceaux.append(f"   • {m}")

    morceaux.append("")
    morceaux.append("_Audit automatique, sur les chiffres de ton export. Aucune estimation : tout ce "
                    "qui est écrit ici vient de ton fichier._")
    return "\n".join(morceaux)


def en_phrases(audit):
    """Le même audit en version courte : pour un premier message ou une notification."""
    problemes = [t for t in audit["trouvailles"] if t["gravite"] in ("critique", "élevé")]
    if not problemes:
        return "✅ Rien de grave dans cet export : la mesure des ventes est en place et le budget vise la vente."
    premier = problemes[0]
    return (f"🔎 {len(problemes)} problème(s) important(s). Le premier, et le plus cher : "
            f"{premier['titre'].lower()} — {fcfa(premier['argent'])} concernés."
            if premier["argent"] else
            f"🔎 {len(problemes)} problème(s) important(s). Le premier : {premier['titre'].lower()}.")
