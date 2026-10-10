"""pages.py — LES PAGES DU CLIENT, ET LEURS PUBLICATIONS DÉJÀ EN LIGNE.

POURQUOI CE MODULE EXISTE (question de José, 10/10/2026) : « l'option publication existante peut être
sélectionnée par l'utilisateur, en plus de l'option de base qui est d'automatiser la création de
publication ? »

Réponse : oui — et ce module est ce qui le rend possible. Deux façons de donner un contenu à une
publicité, et le client choisit :

  - **AUTOMATIQUE** : le client fournit une image (ou une vidéo) et une idée, l'outil écrit le texte
    et fabrique la publication. C'est la voie de base, et elle exige que l'application Meta soit en
    « En ligne » (voir publication.py).
  - **PUBLICATION EXISTANTE** : la boutique a déjà publié la photo et le texte sur sa Page. Le client
    la CHOISIT dans la liste, et la publicité s'appuie dessus — sans rien fabriquer. C'est la voie qui
    fonctionne TOUT DE SUITE, même avec une application en développement.

⚠️ CE QUI REND LA LISTE POSSIBLE : `me/accounts` ne rend pas seulement les Pages, il rend aussi un
**jeton propre à chaque Page**. Avec le jeton de l'utilisateur, la lecture des publications d'une Page
est refusée (code 190, sous-code 2069032) ; avec le jeton de la Page, elle passe. On passe donc par
lui — et il ne sort JAMAIS du serveur : il ne doit pas être envoyé au navigateur du client.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

VERSION_API = "v25.0"
GRAPHE = f"https://graph.facebook.com/{VERSION_API}"
NAVIGATEUR = ("Mozilla/5.0 (Linux; Android 13; TECNO CAMON 19 Pro) AppleWebKit/537.36 "
              "Chrome/128.0 Mobile Safari/537.36")


class ErreurMeta(RuntimeError):
    """Une erreur de Meta, avec son message exact — jamais un code seul."""


def _appel(chemin, parametres, jeton):
    parametres = dict(parametres)
    parametres["access_token"] = jeton
    url = f"{GRAPHE}/{chemin}?" + urllib.parse.urlencode(parametres)
    requete = urllib.request.Request(url, headers={"User-Agent": NAVIGATEUR})
    try:
        with urllib.request.urlopen(requete, timeout=60) as reponse:
            return json.load(reponse)
    except urllib.error.HTTPError as erreur:
        try:
            detail = json.loads(erreur.read().decode("utf-8", "replace")).get("error", {}) or {}
        except ValueError:
            detail = {}
        message = " ".join(str(x) for x in (detail.get("message"), detail.get("error_user_msg"),
                                            detail.get("error_data")) if x)
        raise ErreurMeta(f"Meta a refusé ({detail.get('code')}) : {message or 'sans message'}") \
            from erreur
    except urllib.error.URLError as erreur:
        raise ErreurMeta(f"Impossible de joindre Meta : {erreur}") from erreur


def lister_pages(jeton):
    """Les Pages que ce client peut administrer, avec le jeton PROPRE à chacune.

    Le jeton de Page n'est jamais renvoyé au navigateur : il sert au serveur à lire les publications
    et à publier. On ne garde donc ici que ce qui peut être montré.
    """
    charge = _appel("me/accounts", {"fields": "id,name,category,fan_count,access_token",
                                    "limit": 100}, jeton)
    pages = []
    for brut in charge.get("data", []):
        pages.append({
            "id": brut.get("id"),
            "nom": brut.get("name"),
            "categorie": brut.get("category"),
            "abonnes": brut.get("fan_count"),
            "jeton_page": brut.get("access_token"),   # ⚠️ usage interne uniquement
        })
    return pages


def lister_publications(page, limite=12):
    """Les publications déjà en ligne sur cette Page : ce que le client pourra choisir.

    On garde le texte et l'image, parce que c'est ainsi qu'un client reconnaît ce dont il parle —
    une liste d'identifiants ne lui dit rien.
    """
    if not page.get("jeton_page"):
        raise ErreurMeta(f"Pas de jeton pour la Page « {page.get('nom')} » : impossible de lire ses "
                         "publications. Le droit pages_show_list est peut-être absent.")
    charge = _appel(f"{page['id']}/posts",
                    {"fields": "id,message,created_time,full_picture,permalink_url,status_type",
                     "limit": limite}, page["jeton_page"])
    publications = []
    for brut in charge.get("data", []):
        texte = (brut.get("message") or "").strip()
        publications.append({
            "id": brut.get("id"),
            "texte": texte,
            "apercu": (texte[:110] + "…") if len(texte) > 110 else texte,
            "image": brut.get("full_picture"),
            "lien": brut.get("permalink_url"),
            "quand": brut.get("created_time"),
        })
    return publications


def contenu_a_promouvoir(reglages, choix):
    """Traduit le choix du client en ce que publication.py attend.

    `choix` vaut soit None (« fabrique le contenu »), soit l'identifiant d'une publication
    (« appuie-toi sur celle-ci »). C'est le seul endroit où cette décision se prend : le reste du
    code n'a pas à savoir d'où vient le contenu.
    """
    reglages = dict(reglages)
    if choix:
        reglages["object_story_id"] = choix
    else:
        reglages.pop("object_story_id", None)
    return reglages


if __name__ == "__main__":   # petite vérification à la main, sans réseau simulé
    import os
    with open(os.path.expanduser("~/.hermes/secrets/meta-publicite.json"), encoding="utf-8") as f:
        reglages = json.load(f)
    mes_pages = lister_pages(reglages["jeton"])
    print(f"{len(mes_pages)} page(s) :")
    for page in mes_pages:
        print(f"  - {page['nom']} ({page['abonnes']} abonnés)")
    if mes_pages:
        publications = lister_publications(mes_pages[0])
        print(f"\n{len(publications)} publication(s) sur « {mes_pages[0]['nom']} » :")
        for publication in publications[:6]:
            print(f"  - {publication['apercu'][:80] or '(sans texte)'}")
            print(f"    image : {'oui' if publication['image'] else 'non'} · {publication['id']}")
