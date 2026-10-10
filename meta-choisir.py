"""meta-choisir.py — le seul geste que José doit faire : donner un jeton.
Tout le reste (quel compte publicitaire, quelle page), c'est CE script qui va le lire chez Meta.

POURQUOI AINSI : demander à José de retrouver un identifiant « act_123456789 » dans les entrailles
d'un tableau de bord, c'est le perdre. Il colle un jeton, et je lui montre la liste de ses comptes et
de ses pages, numérotée. Il répond « 1 » et « 2 ». C'est fini.

Usage :
    python3 meta-choisir.py --jeton EAAxxxxx            # montre les comptes et les pages
    python3 meta-choisir.py --jeton EAAxxx --compte 1 --page 2 --but trafic
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

SECRET = os.path.expanduser("~/.hermes/secrets/meta-publicite.json")
VERSION_API = "v25.0"
GRAPHE = f"https://graph.facebook.com/{VERSION_API}"


def appel(chemin, parametres):
    parametres = dict(parametres)
    donnees = urllib.parse.urlencode(parametres).encode()
    url = f"{GRAPHE}/{chemin}"
    requete = urllib.request.Request(url, data=donnees, headers={"User-Agent": "MonAudit/1.0"})
    try:
        with urllib.request.urlopen(requete, timeout=60) as reponse:
            return json.load(reponse)
    except urllib.error.HTTPError as erreur:
        try:
            corps = json.loads(erreur.read().decode("utf-8", "replace"))
            infos = corps.get("error", {})
            message, code = infos.get("message", ""), infos.get("code")
        except Exception:  # noqa: BLE001
            message, code = "réponse illisible", None
        if code == 190:
            print("⛔ Ce jeton n'est pas valide, ou il a expiré (un jeton ne dure pas toujours).")
        elif code in (200, 10):
            print("⛔ Ce jeton n'a pas les droits nécessaires. Il lui manque « gérer les annonces » "
                  "(ads_management) et l'accès à la page.")
        else:
            print(f"⛔ Meta a refusé ({code}) : {message}")
        sys.exit(2)
    except urllib.error.URLError as erreur:
        print("⛔ Impossible de joindre Meta (réseau). Réessaie dans un instant.", erreur)
        sys.exit(2)


def main():
    analyseur = argparse.ArgumentParser(description="Choisir le compte publicitaire et la page.")
    analyseur.add_argument("--jeton", required=True, help="le jeton Meta (EAA…)")
    analyseur.add_argument("--compte", help="numéro du compte publicitaire dans la liste")
    analyseur.add_argument("--page", help="numéro de la page dans la liste")
    analyseur.add_argument("--but", default="trafic",
                           choices=["trafic", "messages", "ventes"])
    options = analyseur.parse_args()

    moi = appel("me", {"access_token": options.jeton, "fields": "name,id"})
    print(f"\nBonjour {moi.get('name', '?')} — le jeton fonctionne.\n")

    comptes = appel("me/adaccounts", {"access_token": options.jeton,
                                      "fields": "name,account_id,currency,account_status",
                                      "limit": 50}).get("data", [])
    if not comptes:
        print("⛔ Ce jeton ne voit AUCUN compte publicitaire. Vérifie qu'il a bien la permission "
              "« gérer les annonces » et qu'il est assigné au compte publicitaire.")
        sys.exit(2)
    print(f"TES COMPTES PUBLICITAIRES ({len(comptes)}) :")
    for i, compte in enumerate(comptes, 1):
        etat = {1: "actif", 2: "désactivé", 3: "non réglé", 7: "en revue", 9: "en grâce",
                101: "fermé"}.get(compte.get("account_status"), compte.get("account_status"))
        print(f"  {i}. {compte.get('name')} · act_{compte.get('account_id')} · "
              f"devise {compte.get('currency')} · {etat}")

    pages = appel("me/accounts", {"access_token": options.jeton, "fields": "name,id",
                                  "limit": 50}).get("data", [])
    print(f"\nTES PAGES ({len(pages)}) :")
    for i, page in enumerate(pages, 1):
        print(f"  {i}. {page.get('name')} · {page.get('id')}")
    if not pages:
        print("  (aucune page visible — la publicité a besoin d'une page : vérifie les droits)")

    if not options.compte or not options.page:
        print("\nRéponds-moi avec les DEUX numéros (le compte, puis la page), et je range les réglages.")
        return 0

    try:
        compte = comptes[int(options.compte) - 1]
        page = pages[int(options.page) - 1]
    except (ValueError, IndexError):
        print("⛔ Numéro hors de la liste.")
        return 2

    reglages = {"jeton": options.jeton, "compte_publicitaire": f"act_{compte['account_id']}",
                "page_id": page["id"], "but": options.but, "devise": compte.get("currency", "XOF"),
                "compte_nom": compte.get("name"), "page_nom": page.get("name")}
    os.makedirs(os.path.dirname(SECRET), exist_ok=True)
    with open(SECRET, "w", encoding="utf-8") as f:
        json.dump(reglages, f, ensure_ascii=False, indent=2)
    os.chmod(SECRET, 0o600)
    print(f"\n✅ Réglages rangés (droits 600, comme un secret) :\n   {SECRET}")
    print(f"   Compte : {compte.get('name')} ({reglages['compte_publicitaire']}) — "
          f"devise {reglages['devise']}")
    print(f"   Page   : {page.get('name')} ({reglages['page_id']})")
    print(f"   But    : {options.but}")
    print("\nVérification possible tout de suite : python3 publication.py <publicite.json> --a-blanc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
