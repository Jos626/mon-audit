"""tests-pages.py — le choix « publicité neuve » ou « publication déjà en ligne ».

Demande de José (10/10/2026) : « l'option publication existante peut être sélectionnée par
l'utilisateur, en plus de l'option de base qui est d'automatiser la création de publication ? »
Ces tests verrouillent les deux chemins et le fait qu'ils ne se mélangent jamais.
"""
import sys

import pages as pages_meta

reussites, echecs = [], []


def verifier(nom, condition, detail=""):
    (reussites if condition else echecs).append(nom)
    print(f"  {'✓' if condition else '✗'} {nom}" + (f" — {detail}" if detail and not condition else ""))


faux = {
    "me/accounts": {"data": [
        {"id": "111", "name": "Parier c'est trop facile", "category": "Sports",
         "fan_count": 2, "access_token": "JETON-DE-PAGE-AAA"},
        {"id": "222", "name": "Roro Boutique Ivoire", "category": "Boutique",
         "fan_count": 6047, "access_token": "JETON-DE-PAGE-BBB"},
    ]},
    "111/posts": {"data": [
        {"id": "111_900", "message": "LES PARIS SPORTIFS, TROP FACILE !",
         "created_time": "2026-10-01T10:00:00+0000", "full_picture": "https://x/img1.jpg",
         "permalink_url": "https://fb/111_900"},
    ]},
    "222/posts": {"data": [
        {"id": "222_901", "message": "", "created_time": "2026-10-02T10:00:00+0000",
         "full_picture": "https://x/img2.jpg"},
    ]},
}
vus = []


def faux_appel(chemin, parametres, jeton):
    vus.append((chemin, jeton))
    if chemin not in faux:
        raise pages_meta.ErreurMeta(f"chemin inattendu : {chemin}")
    return faux[chemin]


pages_meta._appel = faux_appel

print("\n=== 1. Les Pages du client, chacune avec son jeton ===")
mes_pages = pages_meta.lister_pages("JETON-UTILISATEUR")
verifier("les deux Pages sont trouvées", len(mes_pages) == 2, str(len(mes_pages)))
verifier("chaque Page porte son jeton propre",
         mes_pages[0]["jeton_page"] == "JETON-DE-PAGE-AAA" and
         mes_pages[1]["jeton_page"] == "JETON-DE-PAGE-BBB")

print("\n=== 2. Les publications d'une Page se lisent AVEC le jeton de la Page ===")
print("    (avec le jeton de l'utilisateur, Meta refuse : code 190, sous-code 2069032)")
vus.clear()
publications = pages_meta.lister_publications(mes_pages[0])
verifier("la lecture utilise le jeton de la Page, pas celui de l'utilisateur",
         all(jeton == "JETON-DE-PAGE-AAA" for _, jeton in vus), str(vus))
verifier("deux publications trouvées", len(publications) == 1)
verifier("le texte est conservé", publications[0]["texte"].startswith("LES PARIS SPORTIFS"))
verifier("l'image est conservée", publications[0]["image"] == "https://x/img1.jpg")

print("\n=== 3. Une publication sans texte n'est pas un trou dans la liste ===")
sans_texte = pages_meta.lister_publications(mes_pages[1])
verifier("le texte vide ne fait pas planter", len(sans_texte) == 1)
verifier("un aperçu lisible est tout de même fourni",
         isinstance(sans_texte[0]["apercu"], str) and sans_texte[0]["apercu"] == "")

print("\n=== 4. Le choix du client décide de la source du contenu ===")
base = {"jeton": "j", "compte_publicitaire": "act_1", "page_id": "111"}
avec = pages_meta.contenu_a_promouvoir(base, "111_900")
verifier("choisir une publication la met dans les réglages",
         avec.get("object_story_id") == "111_900")
sans = pages_meta.contenu_a_promouvoir(dict(base, object_story_id="VIEUX"), None)
verifier("choisir une publicité neuve EFFACE l'ancien choix",
         "object_story_id" not in sans, str(sans))
verifier("les réglages d'origine ne sont pas modifiés par effet de bord",
         "object_story_id" not in base)

print("\n=== 5. L'écran montre bien les DEUX options, et les publications ===")
import serveur   # noqa: E402 — importé ici : le module lit ses secrets à l'import

fiche = {"jeton": "JETON-UTILISATEUR", "comptes": [{"account_id": "1", "name": "Merveilles",
                                                   "currency": "USD"}],
         "pages": [{"id": "111", "name": "Parier c'est trop facile"}], "chat": "x"}
serveur.pages_meta = pages_meta
html = serveur.page_du_contenu("id-essai", 1, 1, fiche)
verifier("l'option « publicité neuve » est proposée", "publicité neuve" in html)
verifier("l'option « publication déjà en ligne » est proposée", "déjà en ligne" in html)
verifier("la publication est cliquable et porte son identifiant",
         'name="contenu" value="111_900"' in html)
verifier("on montre la photo, pas seulement du texte", "<img src=" in html)
verifier("l'option « publicité neuve » est celle mise en avant par défaut",
         'class="offre actif"><b>①' in html)
# ⛔ Ce test a trouvé un vrai défaut : un champ caché aurait pu envoyer « rien » à la place du choix.
verifier("aucun champ caché ne peut contredire le choix du client",
         'name="contenu" value=""' not in html)
verifier("ne rien cocher veut dire « publicité neuve » (le serveur le déduit)",
         'name="contenu" value="111_900"' in html and html.count('name="contenu"') == 1)
verifier("aucun repère technique n'est resté dans la page", "__" not in html)

print(f"\n=== RÉSULTAT : {len(reussites)} réussite(s), {len(echecs)} échec(s) ===")
for nom in echecs:
    print("  ✗", nom)
sys.exit(1 if echecs else 0)
