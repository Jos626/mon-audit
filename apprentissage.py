"""apprentissage.py — MESURER une publicité, en TIRER des leçons, et préparer la suivante.

LA DEMANDE DE JOSÉ (10/10/2026, mot pour mot) : « L'outil doit pas se contenter que de créer des
publicités. Il doit analyser une publicité, tirer des leçons et reprendre et performer au fur et à
mesure. Donc une même pub doit pouvoir finir par être ultra précise. »

C'est donc une BOUCLE, pas une action :
    créer  ->  mesurer  ->  comprendre  ->  refaire mieux  ->  remesurer…

TROIS RÈGLES, TENUES PAR LE CODE (elles viennent de l'expérience accumulée avec José) :

  1. **Un chiffre sans comparaison ne vaut rien.** « CTR 11,6 % » ne dit pas si c'est bien. On compare
     toujours à l'INTÉRIEUR du même compte, sur la même période, à dépense comparable.
  2. **Sous ~30 résultats, on ne conclut RIEN.** Sur ce volume, un « mauvais » visuel peut être un
     gagnant qui n'a pas eu sa chance. Le module le DIT au lieu de désigner un coupable.
  3. **Une leçon sans geste est un devoir d'école.** Chaque constat finit par ce qu'il faut changer
     dans la publicité suivante — c'est ce qui rend la version d'après meilleure.

Usage :
    python3 apprentissage.py --lire            → les performances du compte, par campagne
    python3 apprentissage.py --lecons          → les constats chiffrés et les gestes
    python3 apprentissage.py --journal X       → l'historique des itérations de la pub X
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
SECRET_REGLAGES = os.path.expanduser("~/.hermes/secrets/meta-publicite.json")
JOURNAL_ITERATIONS = os.path.join(ICI, "iterations-publications.json")
NAVIGATEUR = "Mozilla/5.0 (Linux; Android 13; TECNO CAMON 19 Pro) AppleWebKit/537.36 Chrome/128.0"
VERSION_API = "v25.0"
GRAPHE = f"https://graph.facebook.com/{VERSION_API}"

# ⚠️ LES SEUILS DE PRUDENCE. Un outil qui crie au loup détruit la confiance : sous ces volumes, on
# signale « trop tôt », on ne désigne pas de coupable.
RESULTATS_MINI = 30            # en dessous : aucune conclusion défendable
DEPENSE_MINI_USD = 5           # en dessous : le compte n'a pas assez tourné pour juger
FREQUENCE_FATIGUE = 3.0        # la même personne a vu l'annonce trois fois
CTR_FAIBLE = 0.8               # % : le visuel ne retient pas
RATIO_BRULEUR = 2.5            # coût par résultat >= 2,5 × la médiane du compte

# Les types de résultats, du plus fort au plus faible : ce qui compte, c'est ce que la pub obtient.
TYPES_RESULTAT = (
    ("omni_purchase", "achat"),
    ("offsite_conversion.fb_pixel_purchase", "achat"),
    ("onsite_conversion.lead", "contact"),
    ("lead", "contact"),
    ("offsite_complete_registration_add_meta_leads", "inscription"),
    ("onsite_conversion.total_messaging_connection", "conversation"),
    ("onsite_conversion.messaging_conversation_started_7d", "conversation"),
    ("link_click", "clic"),
)


def lire_reglages():
    try:
        with open(SECRET_REGLAGES, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def appel(chemin, parametres, jeton):
    parametres = dict(parametres)
    parametres["access_token"] = jeton
    url = f"{GRAPHE}/{chemin}?" + urllib.parse.urlencode(parametres)
    requete = urllib.request.Request(url, headers={"User-Agent": NAVIGATEUR})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        return json.load(reponse)


def nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------- lire les performances réelles
def lire_performances(reglages, niveau="campaign", periode="last_30d", limite=100):
    """Les chiffres du compte, par campagne (ou par ensemble, ou par annonce).

    On demande aussi les ACTIONS : c'est là que se trouve ce que la publicité a vraiment obtenu
    (conversation, achat, inscription) — un clic ne nourrit personne.
    """
    champs = ("campaign_name,adset_name,ad_name,spend,impressions,clicks,ctr,cpc,cpm,reach,"
              "frequency,actions")
    charge = appel(f"{reglages['compte_publicitaire']}/insights",
                   {"level": niveau, "date_preset": periode, "limit": limite, "fields": champs},
                   reglages["jeton"])
    lignes = []
    for brute in charge.get("data", []):
        resultat, combien = extraire_resultat(brute)
        lignes.append({
            "nom": brute.get(f"{niveau}_name") or brute.get("campaign_name") or "(sans nom)",
            "depense": nombre(brute.get("spend")),
            "impressions": int(nombre(brute.get("impressions"))),
            "clics": int(nombre(brute.get("clicks"))),
            "ctr": nombre(brute.get("ctr")),
            "cpc": nombre(brute.get("cpc")),
            "cpm": nombre(brute.get("cpm")),
            "portee": int(nombre(brute.get("reach"))),
            "frequence": nombre(brute.get("frequency")),
            "resultat": resultat,
            "resultats": combien,
            "cout_par_resultat": (nombre(brute.get("spend")) / combien) if combien else None,
            "quand": brute.get("date_stop"),
        })
    return lignes


def extraire_resultat(ligne):
    """Le résultat qui compte : un achat vaut mieux qu'un contact, qui vaut mieux qu'un clic."""
    actions = {a.get("action_type"): nombre(a.get("value")) for a in (ligne.get("actions") or [])}
    for cle, libelle in TYPES_RESULTAT:
        if actions.get(cle):
            return libelle, int(actions[cle])
    return None, 0


# ------------------------------------------------------------------------------- tirer les leçons
def lecons(lignes, periode="les 30 derniers jours"):
    """Ce que les chiffres disent VRAIMENT — et ce qu'ils ne disent pas encore.

    Chaque constat porte son chiffre, et chaque constat finit par un geste.
    """
    vendu = [l for l in lignes if l["depense"] > 0]
    if not vendu:
        return {"assez_de_donnees": False,
                "constats": [{"gravite": "conseil", "constat":
                              "Aucune campagne n'a dépensé sur cette période : il n'y a rien à "
                              "analyser pour l'instant.",
                              "geste": "Lance une première publicité ; on mesurera après quelques "
                                       "jours."}],
                "trop_tot": True}
    total_depense = sum(l["depense"] for l in vendu)
    with_resultat = [l for l in vendu if l["resultats"]]
    resultats = sum(l["resultats"] for l in with_resultat)
    constats = []
    trop_tot = total_depense < DEPENSE_MINI_USD or resultats < RESULTATS_MINI

    if trop_tot:
        constats.append({
            "gravite": "info",
            "constat": f"Trop tôt pour juger : {total_depense:.2f} $ dépensés et {resultats} "
                       f"résultat(s) sur {periode}. En dessous de {RESULTATS_MINI} résultats, "
                       "désigner un « mauvais » visuel est un pari, pas un diagnostic.",
            "geste": "Laisser tourner encore quelques jours avant de couper quoi que ce soit."})

    # 1. Qui obtient des résultats, et à quel prix
    if len(with_resultat) >= 2:
        moins_chere = min(with_resultat, key=lambda l: l["cout_par_resultat"])
        plus_chere = max(with_resultat, key=lambda l: l["cout_par_resultat"])
        median = sorted(l["cout_par_resultat"] for l in with_resultat)[len(with_resultat) // 2]
        constats.append({
            "gravite": "important",
            "constat": f"« {moins_chere['nom'][:45]} » obtient ses résultats à "
                       f"{moins_chere['cout_par_resultat']:.2f} $ pièce "
                       f"({moins_chere['resultats']} {moins_chere['resultat']}s), contre "
                       f"{plus_chere['cout_par_resultat']:.2f} $ pour "
                       f"« {plus_chere['nom'][:45]} ». La médiane du compte est à {median:.2f} $.",
            "geste": f"Copier la structure et le texte de « {moins_chere['nom'][:40]} » ; "
                     "c'est le modèle à imiter."})
        bruleuses = [l for l in with_resultat
                     if l["cout_par_resultat"] >= RATIO_BRULEUR * median and median > 0]
        if bruleuses:
            noms = ", ".join(f"« {l['nom'][:35]} »" for l in bruleuses[:3])
            constats.append({
                "gravite": "important",
                "constat": f"{len(bruleuses)} campagne(s) coûtent au moins {RATIO_BRULEUR} fois la "
                           f"médiane du compte : {noms}.",
                "geste": "Couper celles-là (ou les refaire) : c'est là que l'argent est récupérable."})

    # 2. Le visuel retient-il ?
    faibles = [l for l in vendu if l["ctr"] and l["ctr"] < CTR_FAIBLE
               and l["impressions"] >= 1000]
    bonnes = [l for l in vendu if l["ctr"] and l["ctr"] >= CTR_FAIBLE * 2]
    if faibles:
        constats.append({
            "gravite": "important",
            "constat": f"{len(faibles)} campagne(s) sous {CTR_FAIBLE} % de clics alors qu'elles ont "
                       f"été vues plus de 1 000 fois — par exemple "
                       f"« {faibles[0]['nom'][:40]} » ({faibles[0]['ctr']:.2f} %).",
            "geste": "Changer d'abord l'IMAGE (et la première ligne), pas le budget."})
    if bonnes:
        meilleure = max(bonnes, key=lambda l: l["ctr"])
        constats.append({
            "gravite": "info",
            "constat": f"Ce qui retient le mieux : « {meilleure['nom'][:45]} » avec "
                       f"{meilleure['ctr']:.2f} % de clics pour {meilleure['cpc']:.3f} $ le clic.",
            "geste": "Reprendre son visuel et son accroche comme point de départ de la prochaine."})

    # 3. La même personne voit-elle l'annonce trop souvent ?
    fatiguees = [l for l in vendu if l["frequence"] >= FREQUENCE_FATIGUE]
    if fatiguees:
        constats.append({
            "gravite": "conseil",
            "constat": f"{len(fatiguees)} campagne(s) à une fréquence de {FREQUENCE_FATIGUE} ou "
                       f"plus (la même personne a vu l'annonce plusieurs fois) — la plus élevée : "
                       f"« {fatiguees[0]['nom'][:35]} » à {fatiguees[0]['frequence']:.1f}.",
            "geste": "Élargir la cible ou changer le visuel : répéter lasse et fait monter le coût."})

    # 4. Ce que la publicité obtient VRAIMENT
    if with_resultat:
        par_type = {}
        for ligne in with_resultat:
            par_type.setdefault(ligne["resultat"], 0)
            par_type[ligne["resultat"]] += ligne["resultats"]
        detail = ", ".join(f"{v} {k}s" for k, v in sorted(par_type.items(), key=lambda x: -x[1]))
        constats.append({
            "gravite": "info",
            "constat": f"Ce que le compte a obtenu sur la période : {detail}.",
            "geste": "Vérifier que c'est bien ce qu'on veut : si les conversations dominent alors "
                     "qu'on vend sur un site, l'objectif de campagne n'est pas le bon."})

    return {"assez_de_donnees": not trop_tot, "constats": constats, "trop_tot": trop_tot,
            "depense_totale": round(total_depense, 2), "resultats": resultats}


def ingredients_pour_rediger(analyse):
    """Le résumé des leçons, en clair, à donner au rédacteur de la prochaine version.

    C'est LE lien entre mesurer et refaire : sans ça, la version suivante repartirait de zéro et
    « une même pub qui finit ultra précise » resterait un vœu.
    """
    morceaux = []
    for constat in analyse.get("constats", []):
        if constat["gravite"] in ("important", "info"):
            morceaux.append(f"{constat['constat']} → {constat['geste']}")
    if not morceaux:
        return ""
    return ("CE QUI A DÉJÀ ÉTÉ MESURÉ SUR CE COMPTE (à respecter dans le texte) :\n- "
            + "\n- ".join(morceaux[:5]))


# --------------------------------------------------------------------- journal des itérations
def lire_journal():
    try:
        with open(JOURNAL_ITERATIONS, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def journaliser(cle, entree):
    """Range une itération : quelle version, quels chiffres, quelles leçons.

    C'est ce journal qui permet de dire, à la dixième fois, ce qui a réellement amélioré la
    publicité — et de le prouver chiffre par chiffre.
    """
    journal = lire_journal()
    entrees = journal.setdefault(cle, {"iterations": []})
    entree["quand"] = time.strftime("%d/%m/%Y %H:%M")
    entree["numero"] = len(entrees["iterations"]) + 1
    entrees["iterations"].append(entree)
    try:
        with open(JOURNAL_ITERATIONS, "w", encoding="utf-8") as f:
            json.dump(journal, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return entree


def progression(cle):
    """La courbe d'apprentissage de cette publicité : ce qu'on a gagné, itération après itération."""
    journal = lire_journal().get(cle, {}).get("iterations", [])
    if not journal:
        return None
    premier = journal[0]
    dernier = journal[-1]
    lignes = []
    for it in journal:
        cout = it.get("cout_par_resultat")
        lignes.append(f"  v{it['numero']} ({it['quand']}) : "
                      + (f"{cout:.2f} $ par résultat" if cout else "pas encore de résultat")
                      + (f" · {it['lecon'][:70]}" if it.get("lecon") else ""))
    gain = ""
    if premier.get("cout_par_resultat") and dernier.get("cout_par_resultat"):
        baisse = 100 * (premier["cout_par_resultat"] - dernier["cout_par_resultat"]) \
            / premier["cout_par_resultat"]
        gain = (f"\nRésultat : le coût par résultat a "
                f"{'baissé' if baisse > 0 else 'monté'} de {abs(baisse):.0f} % entre la v1 et la "
                f"v{dernier['numero']}.")
    return "\n".join(lignes) + gain


def boucle_amelioration(reglages, idee, visuel, budget, duree, cible, destination,
                        periode="last_30d"):
    """LA BOUCLE COMPLÈTE : mesurer ce qui a tourné, comprendre, puis FABRIQUER la version suivante.

    C'est exactement ce que José a demandé : « analyser une publicité, tirer des leçons et reprendre
    et performer au fur et à mesure ». Le résultat n'est pas un rapport — c'est une publicité
    PRÊTE, qui tient compte de ce qui a déjà marché sur son compte et de ce qui a échoué.

    Rend (publicite, analyse, entree_journal).
    """
    import pub   # import local : évite un cycle à l'import du module

    lignes = lire_performances(reglages, "campaign", periode)
    analyse = lecons(lignes, periode)
    ingredients = ingredients_pour_rediger(analyse)

    publicite = pub.fabriquer(idee, visuel, budget, duree, cible, destination,
                              lecons=ingredients)
    publicite["lecons_utilisees"] = ingredients

    premiere = analyse["constats"][0] if analyse.get("constats") else {}
    cle = pub._sujet_propre(idee, 40)
    entree = journaliser(cle, {
        "version_redigee": publicite["textes"],
        "budget_fcfa": publicite["budget"]["total"],
        "duree_jours": publicite["duree"]["jours"],
        "cible": publicite["cible"],
        "lecon": premiere.get("constat", "")[:200],
        "geste": premiere.get("geste", "")[:200],
        "depense_du_compte": analyse.get("depense_totale"),
        "resultats_du_compte": analyse.get("resultats"),
    })
    return publicite, analyse, entree


# ----------------------------------------------------------------------------------------- le CLI
def main():
    analyseur = argparse.ArgumentParser(description="Mesurer, comprendre, améliorer.")
    analyseur.add_argument("--lire", action="store_true", help="les performances du compte")
    analyseur.add_argument("--lecons", action="store_true", help="les constats et les gestes")
    analyseur.add_argument("--niveau", default="campaign",
                           choices=["campaign", "adset", "ad"])
    analyseur.add_argument("--periode", default="last_30d")
    analyseur.add_argument("--journal", help="montrer la progression d'une publicité")
    options = analyseur.parse_args()

    if options.journal:
        progression_texte = progression(options.journal)
        print(progression_texte or "Aucune itération enregistrée pour cette publicité.")
        return 0

    reglages = lire_reglages()
    if not reglages.get("jeton"):
        print("⛔ Aucun jeton : ouvre la page « Créer mes publicités » pour en obtenir un.")
        return 2
    lignes = lire_performances(reglages, options.niveau, options.periode)
    if options.lire or not options.lecons:
        print(f"{len(lignes)} ligne(s) de performance ({options.niveau}, {options.periode})\n")
        for ligne in lignes[:20]:
            if not ligne["depense"]:
                continue
            resultat = (f"{ligne['resultats']} {ligne['resultat']}s à "
                        f"{ligne['cout_par_resultat']:.2f} $" if ligne["resultats"] else "aucun résultat")
            print(f"  {ligne['nom'][:48]:50} {ligne['depense']:7.2f} $ · CTR {ligne['ctr']:5.2f} % · "
                  f"fréq {ligne['frequence']:.1f} · {resultat}")
        print()
    if options.lecons:
        analyse = lecons(lignes, options.periode)
        for constat in analyse["constats"]:
            marque = {"important": "🔴", "conseil": "🟠", "info": "🔵"}.get(constat["gravite"], "▪️")
            print(f"{marque} {constat['constat']}")
            print(f"    → {constat['geste']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
