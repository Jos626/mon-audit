#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""portrait_texte.py — LE PORTRAIT RENDU LISIBLE, ET LES GESTES QUI EN DÉCOULENT.

Le portrait ne sert à rien s'il reste une fiche de personnage. Chaque rubrique se termine donc par
ce qu'on EN FAIT : quel mot passe dans l'annonce, quelle objection on désarme, quelle zone on cible,
quelle heure on programme. Un portrait sans geste est un devoir d'école.
"""
JOURS_FR = {"Monday": "lundi", "Tuesday": "mardi", "Wednesday": "mercredi", "Thursday": "jeudi",
            "Friday": "vendredi", "Saturday": "samedi", "Sunday": "dimanche"}


def _fenetres_heures(heures):
    """Les heures d'affluence, en français lisible : « 12h-14h et 19h-22h »."""
    if not heures:
        return []
    # ⛔ CORRIGÉ le 09/10/2026 : avec un seuil à 15 % du maximum, presque toutes les heures sortaient
    # « actives » et le rapport annonçait « 8h et 10h-22h » — une plage qui ne dit rien et qu'aucun
    # commerçant ne peut utiliser. On garde la MOITIÉ du pic : ce sont de vraies heures d'affluence.
    plafond = max(n for _h, n in heures)
    actives = sorted(h for h, n in heures if n >= max(2, 0.5 * plafond))
    fenetres, debut = [], actives[0] if actives else None
    for i, h in enumerate(actives):
        if i + 1 < len(actives) and actives[i + 1] == h + 1:
            continue
        fenetres.append((debut, h))
        debut = actives[i + 1] if i + 1 < len(actives) else None
    return [f"{a}h-{b + 1}h" if a != b else f"{a}h" for a, b in fenetres if a is not None]


def construire(etude):
    """Le portrait complet, prêt à envoyer."""
    if not etude.get("nb_clients"):
        return ("🔍 *PORTRAIT DU CLIENT*\n\n"
                + etude.get("raison", "Aucune conversation de client à lire."))

    L = ["🧑‍🤝‍🧑 *PORTRAIT DU CLIENT — bâti sur ses propres paroles*", ""]
    L.append(f"_**{etude['nb_clients']} messages de clients** analysés "
             f"({etude['nb_total']} au total) — sources : {', '.join(etude['sources'])}._")
    L.append("")

    if not etude["assez"]:
        L += [f"⚠️ *C'est trop peu pour un portrait sérieux.* Sous 30 messages, on n'a pas un "
              f"client : on a des impressions. Ce qui suit est donc à prendre comme une PISTE à "
              f"vérifier, pas comme une description de ta clientèle.", ""]

    # 1 · ce qu'ils demandent, dans l'ordre
    themes = list(etude["themes"].items())
    if themes:
        L += ["━━━━━━━━━━━━━━━━━━━", "❓ *CE QU'ILS DEMANDENT, DANS L'ORDRE*", ""]
        for i, (theme, d) in enumerate(themes[:6], 1):
            L.append(f"*{i}. {theme.capitalize()}* — {d['nombre']} messages "
                     f"({d['part'] * 100:.0f} % des messages de clients)")
            if d["exemples"]:
                L.append(f"   _« {d['exemples'][0][:95]} »_")
        premier = themes[0][0]
        L += ["", f"👉 *Le premier de la liste doit être répondu DANS l'annonce.* "
                  f"« {premier.capitalize()} » revient {themes[0][1]['nombre']} fois : c'est autant "
                  f"de conversations que tu peux éviter — et autant de gens qui écrivent déjà "
                  f"décidés."]

    # 2 · ce qui les bloque
    if etude["objections"]:
        L += ["", "━━━━━━━━━━━━━━━━━━━", "🚧 *CE QUI LES BLOQUE (leurs phrases)*", ""]
        for objection, d in list(etude["objections"].items())[:5]:
            L.append(f"• *{objection.capitalize()}* — {d['nombre']} fois")
            if d["citations"]:
                L.append(f"   _« {d['citations'][0][:95]} »_")
        L += ["", "👉 *Chaque objection se désarme dans l'annonce*, pas après : « trop cher » se "
                  "répond par le prix affiché et la qualité justifiée ; « je ne te connais pas » se "
                  "répond par des preuves visibles (avis, commandes livrées, vidéos de clients)."]

    # 3 · leurs mots
    if etude["vocabulaire"]:
        mots = ", ".join(f"{m} ({n})" for m, n in etude["vocabulaire"][:12])
        L += ["", "━━━━━━━━━━━━━━━━━━━", "💬 *LEURS MOTS — À RÉUTILISER TELS QUELS*", "",
              mots, "",
              "👉 *Écris l'annonce avec CE vocabulaire*, pas avec celui de ta profession. Le client "
              "se reconnaît dans ses propres mots — c'est le ciblage le plus précis qui reste."]

    # 4 · où ils sont
    if etude["lieux"]:
        lieux = ", ".join(f"{l} ({n})" for l, n in etude["lieux"][:8])
        L += ["", "━━━━━━━━━━━━━━━━━━━", "📍 *D'OÙ ILS ÉCRIVENT*", "", lieux, "",
              "👉 Deux usages : ta *carte de livraison* (dis-les dans l'annonce) et ta *zone de "
              "diffusion* (Meta permet encore de cibler ville par ville — c'est précis et gratuit)."]

    # 5 · quand ils écrivent
    fenetres = _fenetres_heures(etude["heures"])
    if fenetres:
        jours = ", ".join(JOURS_FR.get(j, j) for j, _n in etude["jours"][:3])
        L += ["", "━━━━━━━━━━━━━━━━━━━", "🕐 *QUAND ILS ÉCRIVENT*", "",
              f"Heures d'affluence : **{' et '.join(fenetres[:3])}**. Jours les plus actifs : {jours}.",
              "",
              "👉 *Programme tes annonces sur ces heures.* C'est le ciblage horaire : toujours "
              "disponible chez Meta, et personne ne s'en sert."]

    # 6 · les clients ignorés
    sr = etude.get("sans_reponse")
    if sr and sr["nombre"]:
        L += ["", "━━━━━━━━━━━━━━━━━━━", "🔇 *CE QUI EST LE PLUS CHER DANS TOUT ÇA*", "",
              f"**{sr['nombre']} message{'s' if sr['nombre'] > 1 else ''} de client"
              f"{'s' if sr['nombre'] > 1 else ''} n'a jamais reçu de réponse** "
              if sr["nombre"] == 1 else
              f"**{sr['nombre']} messages de clients n'ont jamais reçu de réponse** "
              f"({sr['part'] * 100:.0f} % de ce qui est arrivé).", ""]
        for exemple in sr["exemples"]:
            L.append(f"   _« {exemple[:95]} »_")
        L += ["", "👉 Ces gens ont écrit, ont été intéressés, et n'ont rien eu. Ils sont partis chez "
                  "un autre. Aucun réglage de campagne ne récupère ça — seule une réponse rapide le "
                  "fait."]

    # 7 · le ciblage réellement exploitable
    L += ["", "━━━━━━━━━━━━━━━━━━━", "🎯 *LE CIBLAGE QUI RESTE VRAIMENT PRÉCIS*", "",
          "Pour être clair : l'ultra-ciblage par centres d'intérêt n'existe plus chez Meta — les "
          "exclusions ont été retirées en 2024, puis les centres d'intérêt regroupés et supprimés "
          "(arrêt de diffusion en janvier 2026 pour ceux qui les utilisaient). Ce qui reste, et qui "
          "est précis, c'est ceci :", "",
          "1. **Tes acheteurs réels** → audience personnalisée. Ils ont payé : c'est la définition "
          "même de la bonne cible.",
          "2. **Une audience similaire à partir de ces acheteurs** (et non à partir des gens qui ont "
          "cliqué). C'est la différence entre cibler des curieux et cibler des payeurs.",
          "3. **Exclure ceux qui ont déjà acheté** (et ceux qui n'ont jamais répondu).",
          "4. **La zone** (ville par ville) et **les horaires** — ci-dessus, mesurés chez toi.",
          "5. **Le message** : le seul levier qui fait vraiment le tri, et il est gratuit."]

    # 8 · le fichier clients
    cf = etude.get("clients_fichier")
    if not cf:
        L += ["", "❓ *IL ME MANQUE UNE CHOSE POUR ALLER PLUS LOIN*", "",
              "**Ton fichier de commandes** (une ligne par vente : nom, ville, produit, montant, "
              "date). C'est lui qui donne les vrais chiffres : qui achète, où, combien, et quel est "
              "ton meilleur client. Envoie-le en CSV et je te sors le portrait chiffré — et la liste "
              "à téléverser dans Meta pour l'audience similaire."]
    else:
        villes = ", ".join(f"{v} ({n})" for v, n in cf["villes"][:6])
        L += ["", "━━━━━━━━━━━━━━━━━━━", "💰 *TES VRAIS ACHETEURS*", "",
              f"**{cf['nombre']} commandes** dans ton fichier. Villes : {villes}."]

    L += ["", "_Tout ce qui est écrit ici vient de tes conversations et de tes commandes. Aucun âge, "
          "aucun revenu, aucune personnalité inventés : ça ne se lit pas dans un fil de discussion._"]
    return "\n".join(L)
