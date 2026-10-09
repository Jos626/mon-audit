#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit.py — LE CERVEAU DE L'AUDIT : ce qui ne va pas, pourquoi, et combien ça coûte.

CE QUI SÉPARE CET AUDIT D'UN AUDIT QUI NE VAUT RIEN.

Un audit qui énumère des bonnes pratiques est inutile : le commerçant les connaît déjà, il les a lues
cent fois, et il n'a rien changé. Trois règles gouvernent les contrôles ci-dessous.

  1. **UN CONSTAT SANS CHIFFRE N'EST PAS UN CONSTAT.** Chaque trouvaille porte la valeur qui l'a
     déclenchée. « Ta fréquence est trop haute » ne se discute pas ; « 41 % de ton budget tourne à
     une fréquence de 4,2, donc la même personne a vu ton annonce quatre fois » se vérifie et se
     corrige.

  2. **LE COÛT SE DONNE EN FRANCS, ET SEULEMENT QUAND IL EST CALCULABLE.** Quand on peut chiffrer
     l'argent en jeu (le budget d'annonces qui n'ont rien vendu), on le chiffre. Quand on ne peut pas,
     on écrit `None` — jamais un chiffre inventé pour faire sérieux. Un montant faux, une seule fois,
     et le client coupe une campagne qui marchait.

  3. **UN CONTRÔLE QUI CRIE AU LOUP DÉTRUIT L'OUTIL.** Les seuils sont prudents, et le volume est
     vérifié AVANT de juger : sous ~30 résultats, aucun classement n'est défendable, et l'audit doit
     le dire au lieu de désigner un « mauvais visuel » qui est en réalité du bruit. Même leçon que la
     mesure des paris : un écart sur quelques dizaines de cas n'est pas une découverte.

Et une règle de produit, la plus importante : **l'audit dit aussi ce qui MARCHE.** Un rapport qui ne
sait que reprocher ne fait pas agir — il décourage. Les annonces qui portent les ventes sont nommées,
avec leur chiffre, et la consigne est de ne pas y toucher.
"""
from lecture import argent as _argent
from lecture import fr_nombre, nombre, pourcent

# --------------------------------------------------------------------------- seuils
# Tous décidés, pas devinés : chacun est commenté par ce qu'il protège.
SEUIL_DEPENSE_SERIEUSE = 10_000      # F CFA. En dessous, le compte n'a pas encore assez tourné pour
                                     # qu'un diagnostic structurel ait un sens.
SEUIL_RESULTATS_STAT = 30            # Au-delà, un écart commence à tenir. En dessous : personne n'est
                                     # déclaré gagnant ou perdant (règle héritée de la mesure des paris).
FREQUENCE_ALERTE = 3.0               # À 3, la même personne a vu l'annonce trois fois : à ce stade,
                                     # l'audience se fatigue avant que le message ait convaincu.
RATIO_QUI_BRULE = 2.5                # Une annonce qui coûte 2,5 fois le coût moyen du compte pour son
                                     # résultat est une annonce qui ponctionne les autres.
CTR_FAIBLE = 0.8                     # % — sous 1 %, le visuel ne retient pas le pouce. Le seuil est
                                     # mis à 0,8 pour ne pas accuser les campagnes « messages », dont
                                     # le CTR est naturellement plus bas.
PART_BUDGET_QUI_BRULE = 0.25         # On ne parle d'un problème de budget que s'il dépasse un quart
                                     # des dépenses : sous ce niveau, c'est de l'ajustement, pas un
                                     # chantier.

GRAVITES = {"critique": 0, "élevé": 1, "moyen": 2, "faible": 3, "pour information": 4}


def _trouvaille(code, gravite, titre, constat, pourquoi, action, argent=None, preuves=None):
    return {"code": code, "gravite": gravite, "titre": titre, "constat": constat,
            "pourquoi": pourquoi, "action": action, "argent": argent, "preuves": preuves or {}}


def _somme(lignes, champ):
    return round(sum(l.get(champ, 0.0) for l in lignes), 2)


def _mediane(valeurs):
    propres = sorted(v for v in valeurs if v is not None)
    if not propres:
        return None
    milieu = len(propres) // 2
    return propres[milieu] if len(propres) % 2 else (propres[milieu - 1] + propres[milieu]) / 2


def _cout_par(ligne, champ_cout="cout_resultat", champ_nombre="resultats"):
    """Le coût d'un résultat sur une ligne, calculé si absent, JAMAIS deviné."""
    cout = ligne.get(champ_cout, 0.0)
    if cout:
        return cout
    combien = ligne.get(champ_nombre, 0.0)
    return round(ligne.get("depense", 0.0) / combien, 2) if combien else None


def _libelle(ligne):
    return ligne.get("pub") or ligne.get("ensemble") or ligne.get("campagne") or "(sans nom)"


# --------------------------------------------------------------------------- contrôles
def _controle_mesure(export, profil):
    """1. LE CONTRÔLE QUI PASSE AVANT TOUS LES AUTRES : le compte sait-il compter ses ventes ?"""
    trouvailles = []
    total, lignes = export["total"], export["lignes"]
    ferme_en_ligne = profil.get("fermeture")          # "site" | "whatsapp" | "boutique"
    achats_colonne_absente = "achats" in export["absentes"]
    valeur_absente = "valeur_achats" in export["absentes"]

    if total["depense"] < SEUIL_DEPENSE_SERIEUSE:
        return trouvailles

    if achats_colonne_absente or total.get("achats", 0) == 0:
        if ferme_en_ligne == "whatsapp":
            trouvailles.append(_trouvaille(
                "VENTES_NON_MESUREES", "critique",
                "Tes ventes ne sont pas comptées dans ton compte publicitaire",
                f"Tu as dépensé {_argent(total['depense'])} F CFA et le compte enregistre "
                f"{int(total.get('achats', 0))} achat. Que tu vendes sur WhatsApp n'y change rien : "
                f"Meta voit des conversations, il ne voit aucune vente.",
                "Sans la vente dans tes chiffres, Meta cherche des gens qui ÉCRIVENT — pas des gens "
                "qui PAIENT. C'est exactement le problème des « beaucoup de messages, zéro commande » : "
                "l'algorithme fait très bien son travail, mais sur le mauvais objectif.",
                ["Enregistre chaque vente (même conclue sur WhatsApp) comme un événement « achat » "
                 "avec sa valeur, via l'API de conversions",
                 "Vérifie dans le gestionnaire d'événements que l'achat remonte bien, avec un vrai "
                 "achat de test",
                 "Ensuite seulement, passe tes campagnes en optimisation sur l'achat"],
                argent=total["depense"],
                preuves={"dépense": total["depense"], "achats_enregistrés": int(total.get("achats", 0)),
                         "colonne_achats": "absente" if achats_colonne_absente else "présente"}))
        else:
            trouvailles.append(_trouvaille(
                "MESURE_VENTE_ABSENTE", "critique",
                "Rien ne mesure tes ventes",
                f"{_argent(total['depense'])} F CFA dépensés, "
                f"{0 if achats_colonne_absente else int(total.get('achats', 0))} achat enregistré.",
                "Tu pilotes à l'aveugle : le compte peut t'annoncer de bons résultats (clics, "
                "messages) pendant que tu perds de l'argent. C'est la première chose à réparer, avant "
                "tout le reste — le reste n'a pas de sens sans elle.",
                ["Installe ou vérifie le pixel sur la page de remerciement / la page de commande",
                 "Ajoute l'API de conversions côté serveur (les navigateurs bloquent de plus en plus "
                 "le pixel seul)",
                 "Fais un achat de test et vérifie qu'il apparaît dans le gestionnaire d'événements"],
                argent=total["depense"],
                preuves={"dépense": total["depense"], "colonne_achats":
                         "absente" if achats_colonne_absente else "présente"}))

    if valeur_absente and not achats_colonne_absente and total.get("achats", 0) > 0:
        trouvailles.append(_trouvaille(
            "VALEUR_MANQUANTE", "moyen",
            "Tu comptes les commandes, mais pas ce qu'elles rapportent",
            f"{int(total['achats'])} achat(s) enregistré(s), mais aucune valeur d'achat dans l'export.",
            "Sans le montant, impossible de savoir si une commande te rapporte plus qu'elle ne te "
            "coûte. C'est pourtant le seul chiffre qui décide : au-dessus, tu gagnes ; en dessous, tu "
            "paies pour travailler.",
            ["Envoie la valeur de la commande avec l'événement d'achat",
             "Réexporte le fichier en cochant « Valeur d'achat » et « ROAS des achats »"],
            argent=None))
    return trouvailles


def _controle_objectif(export, profil):
    """2. Le budget vise-t-il la vente, ou quelque chose qui y ressemble ?"""
    trouvailles = []
    lignes, total = export["lignes"], export["total"]
    if total["depense"] < SEUIL_DEPENSE_SERIEUSE:
        return trouvailles

    def _est_vente(l):
        texte = f"{l.get('objectif', '')} {l.get('type_resultat', '')}".lower()
        return any(m in texte for m in ("achat", "purchase", "vente", "conversion", "catalog",
                                        "catalogue", "panier"))

    def _est_message(l):
        texte = f"{l.get('objectif', '')} {l.get('type_resultat', '')}".lower()
        return any(m in texte for m in ("message", "conversation"))

    dehors = [l for l in lignes if l.get("depense", 0) and not _est_vente(l)]
    argent_dehors = _somme(dehors, "depense")
    part = argent_dehors / total["depense"] if total["depense"] else 0
    messages = _est_message and sum(l.get("depense", 0) for l in lignes if _est_message(l))
    ferme_en_ligne = profil.get("fermeture")

    if part >= PART_BUDGET_QUI_BRULE and dehors:
        if ferme_en_ligne == "whatsapp" and messages:
            trouvailles.append(_trouvaille(
                "PILOTAGE_SUR_LA_CONVERSATION", "élevé",
                f"{pourcent(part)} de ton budget optimise la conversation, pas la commande",
                f"{_argent(argent_dehors)} F CFA sur {_argent(total['depense'])} visent un résultat qui n'est "
                f"pas l'achat (messages ou clics).",
                "Vendre sur WhatsApp est un bon choix — mais tant que Meta optimise sur « obtenir un "
                "message », il te livre les gens les plus bavards, pas les plus solvables. C'est la "
                "cause directe des « plein de messages, zéro commande ».",
                ["Garde les campagnes messages pour discuter, mais pilote-les sur le coût par "
                 "commande réelle, pas sur le coût par message",
                 "Ajoute une campagne dont l'optimisation est l'achat (une fois l'achat mesuré)",
                 "Compare les deux sur un seul chiffre : coût par commande"],
                argent=argent_dehors,
                preuves={"budget_hors_achat": argent_dehors, "part": round(part, 3)}))
        else:
            trouvailles.append(_trouvaille(
                "OBJECTIF_LOIN_DE_LA_VENTE", "élevé",
                f"{pourcent(part)} de ton budget ne vise pas la vente",
                f"{_argent(argent_dehors)} F CFA sur {_argent(total['depense'])} ont pour objectif autre "
                f"chose que l'achat.",
                "Optimiser un clic ou une visite, c'est demander à Meta de trouver des gens qui "
                "cliquent — c'est ce qu'il fait, et il le fait très bien. Tu obtiens exactement ce "
                "que tu demandes : du trafic, pas des clients.",
                ["Regroupe le budget sur une campagne dont l'objectif est la vente",
                 "Ne garde du budget sur les autres objectifs que pour une raison écrite"],
                argent=argent_dehors,
                preuves={"budget_hors_achat": argent_dehors, "part": round(part, 3)}))
    return trouvailles


def _controle_annonces_qui_brulent(export, profil):
    """3. OÙ PART L'ARGENT : les annonces qui coûtent cher sans rien donner."""
    trouvailles = []
    lignes, total = export["lignes"], export["total"]
    avec_resultat = [l for l in lignes if (l.get("cout_resultat") or _cout_par(l))]
    if not avec_resultat or total["depense"] < SEUIL_DEPENSE_SERIEUSE:
        return trouvailles

    couts = [l["cout_resultat"] or _cout_par(l) for l in avec_resultat]
    median = _mediane(couts)
    if not median:
        return trouvailles

    brulees = [l for l in lignes
               if l.get("depense", 0) > 0
               and ((l.get("resultats", 0) or 0) <= 1
                    or (_cout_par(l) or 0) >= RATIO_QUI_BRULE * median)]
    argent = _somme(brulees, "depense")
    noms = ", ".join(f"« {_libelle(l)[:38]} » ({_argent(l['depense'])} F)"
                     for l in sorted(brulees, key=lambda l: -l.get("depense", 0))[:3])

    if argent >= 0.05 * total["depense"] and brulees:
        # AVANT D'ACCUSER : y a-t-il assez de volume pour juger ? C'est la règle héritée de la mesure
        # des paris — sous 30 cas, un « mauvais visuel » peut être du hasard pur.
        assez = total.get("resultats", 0) >= SEUIL_RESULTATS_STAT
        trouvailles.append(_trouvaille(
            "ANNONCES_QUI_BRULENT", "élevé" if assez else "moyen",
            f"{_argent(argent)} F CFA partent sur des annonces qui ne rapportent rien",
            f"{len(brulees)} annonces sur {len(lignes)} coûtent plus de "
            f"{fr_nombre(RATIO_QUI_BRULE)} fois le coût moyen du compte ({_argent(median)} F) pour un résultat, "
            f"ou n'ont rien produit du tout. Les plus lourdes : {noms}.",
            ("Cet argent est déjà dépensé. La question est de savoir s'il continue : tant que ces "
             "annonces tournent, elles prennent la place des autres dans la diffusion — c'est du "
             "budget prélevé sur ce qui vend."
             if assez else
             "Attention : ton compte n'a pas encore assez de résultats pour juger un visuel à coup "
             "sûr. Ces montants méritent d'être surveillés, pas encore condamnés — couper maintenant "
             "risque d'éliminer un gagnant qui n'a pas eu sa chance."),
            ["Coupe les annonces qui n'ont produit aucun résultat après un budget égal à 3 fois ton "
             "coût par commande",
             "Regroupe le budget sur les deux ou trois annonces qui portent tes résultats",
             "Si une annonce a produit un seul résultat très cher, refais-la avec un autre visuel "
             "plutôt que de l'éteindre"],
            argent=argent,
            preuves={"argent_qui_brule": argent, "nombre_annonces": len(brulees),
                     "cout_moyen_du_compte": median, "assez_de_volume": assez}))
    return trouvailles


def _controle_concentration(export, profil):
    """4. CE QUI MARCHE — un audit qui ne montre que les défauts ne fait pas agir."""
    trouvailles = []
    lignes, total = export["lignes"], export["total"]
    avec_resultat = [l for l in lignes if (l.get("resultats", 0) or 0) >= 3
                     and (_cout_par(l) or 0) > 0]
    if not avec_resultat or total["depense"] < SEUIL_DEPENSE_SERIEUSE:
        return trouvailles

    median = _mediane([_cout_par(l) for l in avec_resultat])
    gagnantes = sorted([l for l in avec_resultat if (_cout_par(l) or 0) < median], key=_cout_par)
    if not gagnantes or total.get("resultats", 0) < SEUIL_RESULTATS_STAT:
        return trouvailles

    argent = _somme(gagnantes, "depense")
    meilleure = gagnantes[0]
    trouvailles.append(_trouvaille(
        "CE_QUI_MARCHE", "pour information",
        f"Tes gagnantes portent {pourcent(argent / total['depense'])} de ton budget",
        f"{len(gagnantes)} annonce(s) obtiennent leurs résultats sous le coût moyen du compte. La "
        f"meilleure : « {_libelle(meilleure)[:45]} » à {_argent(_cout_par(meilleure))} F le résultat "
        f"({int(meilleure.get('resultats', 0))} résultats).",
        "C'est ici que se trouve la croissance. Une annonce gagnante qu'on n'augmente pas est de "
        "l'argent laissé sur la table — et la tentation est de la modifier, ce qui la casse.",
        ["N'ÉDITE PAS les annonces gagnantes : toute modification repart la phase d'apprentissage à zéro",
         "Augmente progressivement le budget du meilleur ensemble (20 à 30 % par palier)",
         "Déclines le visuel gagnant en deux ou trois variantes proches, pas en changeant tout"],
        argent=argent,
        preuves={"budget_gagnant": argent, "part": round(argent / total["depense"], 3),
                 "meilleur_cout": _cout_par(meilleure)}))
    return trouvailles


def _controle_frequence(export, profil):
    """5. La fatigue d'audience : la même personne voit l'annonce trop souvent."""
    trouvailles = []
    lignes, total = export["lignes"], export["total"]
    fatiguees = [l for l in lignes if l.get("depense", 0) >= 0.05 * total["depense"]
                 and (l.get("frequence") or 0) >= FREQUENCE_ALERTE]
    if not fatiguees:
        return trouvailles
    argent = _somme(fatiguees, "depense")
    pire = max(fatiguees, key=lambda l: l.get("frequence") or 0)
    trouvailles.append(_trouvaille(
        "AUDIENCE_FATIGUEE", "élevé",
        f"{_argent(argent)} F CFA tournent sur une audience saturée",
        f"{len(fatiguees)} annonces dépassent une fréquence de {fr_nombre(FREQUENCE_ALERTE)}. La plus haute : "
        f"{fr_nombre(pire.get('frequence'), 1)} — la même personne a vu l'annonce {fr_nombre(pire.get('frequence'), 0)} "
        f"fois (« {_libelle(pire)[:40]} »).",
        "À partir de trois passages, l'annonce n'informe plus : elle agace. Le coût par clic monte, "
        "et tu paies pour être vu par des gens qui ne te découvrent plus.",
        ["Change le visuel ou l'accroche sur ces lignes (garder le même message publicitaire)",
         "Élargis l'audience plutôt que d'augmenter la fréquence",
         "Exclue les personnes ayant déjà acheté pour ne pas payer deux fois pour la même"],
        argent=argent,
        preuves={"frequence_max": pire.get("frequence"), "argent_concerné": argent}))
    return trouvailles


def _controle_emiettement(export, profil):
    """6. Le budget dispersé : trop d'ensembles pour que l'un atteigne son rythme."""
    trouvailles = []
    lignes, total = export["lignes"], export["total"]
    ensembles = [l for l in lignes if l.get("ensemble")]
    if len(ensembles) < 4 or total["depense"] < SEUIL_DEPENSE_SERIEUSE:
        return trouvailles
    couts = [_cout_par(l) for l in lignes if _cout_par(l)]
    median = _mediane(couts)
    if not median:
        return trouvailles

    maigres = [l for l in ensembles if l.get("depense", 0) < 3 * median and l.get("depense", 0) > 0]
    if len(maigres) < 3:
        return trouvailles
    part = len(maigres) / len(ensembles)
    trouvailles.append(_trouvaille(
        "BUDGET_EMIETTE", "moyen",
        f"{len(maigres)} ensembles sur {len(ensembles)} n'ont pas dépensé de quoi savoir",
        f"Le coût moyen d'un résultat sur ton compte est de {_argent(median)} F. Ces {len(maigres)} "
        f"ensembles sont restés sous trois fois ce montant : ils n'ont mathématiquement pas pu "
        f"produire assez de résultats pour être jugés.",
        "Trop d'ensembles, c'est aucun ensemble qui apprend. Meta a besoin d'un volume par ensemble "
        "pour trouver les bons acheteurs ; divisé en dix, ce volume n'existe nulle part.",
        [f"Regroupe ces {len(maigres)} ensembles en deux ou trois",
         "Garde chaque ensemble au-dessus de trois fois ton coût par résultat",
         "Attends une semaine avant de juger, et ne touche à rien pendant ce temps"],
        argent=_somme(maigres, "depense"),
        preuves={"ensembles_maigres": len(maigres), "ensembles": len(ensembles),
                 "cout_moyen": median}))
    return trouvailles


def _controle_marge(export, profil):
    """7. LE CHIFFRE QUI TRANCHE : ce que coûte une commande face à ce qu'elle rapporte."""
    trouvailles = []
    total = export["total"]
    marge, panier = profil.get("marge"), profil.get("panier")
    if not marge or not total.get("achats"):
        return trouvailles
    cout = total["depense"] / total["achats"]
    if cout <= marge:
        return trouvailles
    pertes = (cout - marge) * total["achats"]
    trouvailles.append(_trouvaille(
        "MARGE_DEPASSEE", "critique",
        f"Chaque commande te coûte plus qu'elle ne te rapporte",
        f"Tu paies {_argent(cout)} F CFA pour obtenir une commande, et une commande te laisse "
        f"{_argent(marge)} F de marge. Sur {int(total['achats'])} commande(s), cela fait "
        f"{_argent(pertes)} F CFA perdus.",
        "Ce n'est ni le visuel ni le ciblage : c'est l'arithmétique. Tant que ce chiffre est "
        "au-dessus de ta marge, chaque vente te rapproche de la faillite — et plus tu dépenses, plus "
        "tu perds vite.",
        [f"Ton plafond est de {_argent(marge)} F par commande : au-dessus, tu perds",
         "Soit tu fais baisser ce coût (offre, page, relance), soit tu montes le panier moyen "
         "(lot, livraison offerte au-delà d'un montant)",
         "En attendant, ne scale pas : arrête d'augmenter le budget n'aggraverait que la perte"],
        argent=round(pertes, 2),
        preuves={"cout_par_commande": round(cout, 2), "marge": marge,
                 "commandes": int(total["achats"])}))
    return trouvailles


def _controle_visuel(export, profil):
    """8. Le visuel qui ne retient pas le pouce — prudence, le CTR dépend de l'objectif."""
    trouvailles = []
    lignes, total = export["lignes"], export["total"]
    if total["depense"] < SEUIL_DEPENSE_SERIEUSE:
        return trouvailles
    faibles = [l for l in lignes if l.get("ctr", 0) > 0 and l["ctr"] < CTR_FAIBLE
               and l.get("impressions", 0) >= 3000]
    if not faibles:
        return trouvailles
    poids = _somme(faibles, "depense")
    if poids < 0.1 * total["depense"]:
        return trouvailles
    prix_clic = _mediane([l.get("cpc", 0) for l in lignes if l.get("cpc")])
    trouvailles.append(_trouvaille(
        "VISUEL_QUI_NE_RETIENT_PAS", "moyen",
        f"{len(faibles)} annonces sur {len(lignes)} sont sous {fr_nombre(CTR_FAIBLE)} % de clics",
        f"{_argent(poids)} F CFA diffusés pour moins de {fr_nombre(CTR_FAIBLE)} % de clics"
        + (f", à {_argent(prix_clic)} F le clic" if prix_clic else "") + ".",
        "À ce niveau, le problème n'est pas qui voit l'annonce mais l'annonce elle-même : elle ne "
        "donne pas envie d'en savoir plus. Le message publicitaire (l'accroche, les trois premières "
        "secondes) se teste vite et coûte peu.",
        ["Écris trois accroches qui commencent par le problème du client, pas par le produit",
         "Mets le prix ou la condition dans l'annonce : tu perdras des clics et tu gagneras des commandes",
         "Teste les trois en parallèle, garde celle qui donne le meilleur coût par commande"],
        argent=poids,
        preuves={"ctr_seuil": CTR_FAIBLE, "lignes": len(faibles), "argent_concerné": poids}))
    return trouvailles


def _controle_colonnes(export, profil):
    """9. Ce que le fichier ne dit pas — et qu'il faut pour en dire plus."""
    if not export["absentes"] and not export["souhaitees_absentes"]:
        return []
    manquantes = list(export["absentes"]) + [c for c in export["souhaitees_absentes"]
                                             if c not in export["absentes"]]
    lisibles = {"objectif": "Objectif de la campagne", "type_resultat": "Type de résultat",
                "achats": "Achats", "valeur_achats": "Valeur d'achat",
                "frequence": "Fréquence", "clics": "Clics (tous)", "portee": "Portée",
                "resultats": "Résultats", "impressions": "Impressions", "depense": "Montant dépensé"}
    reclame = [lisibles.get(c, c) for c in manquantes]
    return [_trouvaille(
        "EXPORT_INCOMPLET", "pour information",
        f"Ton export ne contient pas {len(reclame)} colonne(s) utile(s)",
        "Manquant : " + ", ".join(reclame) + ".",
        "Ce ne sont pas des détails : sans la fréquence, je ne peux pas voir la fatigue d'audience ; "
        "sans les achats, je ne peux pas compter tes ventes. Plus l'export est complet, plus l'audit "
        "est précis — et l'export se refait en deux clics.",
        ["Dans Ads Manager : colonnes → Personnaliser les colonnes → coche « Performance » et "
         "« Conversions », puis Exporter en CSV"],
        argent=None,
        preuves={"colonnes_manquantes": manquantes})]


def _caution_volume(export, profil):
    """10. La prudence qui protège la crédibilité de tout le reste."""
    total = export["total"]
    if total["depense"] < SEUIL_DEPENSE_SERIEUSE:
        return [_trouvaille(
            "TROP_PEU_DE_DONNEES", "pour information",
            "Ton compte n'a pas encore assez tourné",
            f"{_argent(total['depense'])} F CFA dépensés au total.",
            "En dessous d'environ 10 000 F, un compte n'a pas produit assez de résultats pour qu'on "
            "puisse dire si quelque chose ne marche pas — ou si ça marche. Un jugement posé "
            "maintenant serait un avis, pas une mesure.",
            ["Laisse tourner une semaine de plus sans rien changer",
             "Reviens avec l'export : on saura alors de quoi on parle"],
            argent=None)]
    if 0 < total.get("resultats", 0) < SEUIL_RESULTATS_STAT and total["depense"] >= SEUIL_DEPENSE_SERIEUSE:
        return [_trouvaille(
            "PEU_DE_RESULTATS", "pour information",
            f"Seulement {int(total['resultats'])} résultat(s) pour juger",
            f"{_argent(total['depense'])} F CFA dépensés pour {int(total['resultats'])} résultat(s).",
            f"Sous {SEUIL_RESULTATS_STAT} résultats, un écart peut venir du hasard. Je peux te dire "
            f"où va l'argent — je ne peux pas encore te dire quel visuel est le meilleur. "
            f"Présenter un gagnant sur ce volume serait te faire couper un bon visuel.",
            ["Continue quelques jours, puis réexporte",
             "Pendant ce temps, applique ce qui ne dépend pas du volume : la mesure des ventes, "
             "le pilotage sur la commande, et le contrôle de la fréquence"],
            argent=None)]
    return []


# --------------------------------------------------------------------------- orchestration
def auditer(export, profil=None):
    """L'audit complet, dans l'ordre où le client doit le lire.

    Le tri est par ARGENT EN JEU, pas par gravité de manuel : le commerçant veut d'abord savoir où
    part son argent. Les constats sans montant passent après, et les informations en dernier.
    """
    profil = profil or {}
    trouvailles = []
    for controle in (_controle_mesure, _controle_objectif, _controle_marge, _controle_annonces_qui_brulent,
                     _controle_frequence, _controle_emiettement, _controle_visuel,
                     _controle_concentration, _caution_volume, _controle_colonnes):
        trouvailles += controle(export, profil)

    def _cle(t):
        return (0 if t["argent"] is not None else 1,
                -(t["argent"] or 0),
                GRAVITES.get(t["gravite"], 9))
    trouvailles.sort(key=_cle)

    return {
        "total": export["total"],
        "profil": profil,
        "trouvailles": trouvailles,
        "argent_en_jeu": round(sum(t["argent"] or 0 for t in trouvailles
                                   if t["gravite"] in ("critique", "élevé")), 2),
        "critiques": [t for t in trouvailles if t["gravite"] in ("critique", "élevé")],
        "note_parfaite": not [t for t in trouvailles if t["gravite"] in ("critique", "élevé")],
    }
