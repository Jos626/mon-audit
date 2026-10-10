# Pubmeta — créer mes publicités : ce que José fait, et ce que fait la machine

**L'outil s'appelle Pubmeta** (renommé le 10/10/2026 — c'était « Pubmeta »).
Signé : *Pubmeta — par José Ledanite*.

---

## 1. Le geste : UN bouton, et il n'y a rien à chercher

Ouvre **https://mon-audit.onrender.com** et appuie sur le bouton vert
**« Créer mes publicités »**.

On te demande :
1. d'**autoriser** (les pages de Facebook : ton mot de passe ne passe jamais par nous) ;
2. de **choisir ton compte publicitaire** dans une liste — la liste est remplie automatiquement,
   tu ne cherches aucun identifiant ;
3. de **choisir ta page** dans une autre liste.

C'est tout. **Tu ne vois jamais un jeton, tu ne copies rien.**

> ⚠️ Si tu n'as jamais appuyé sur DÉMARRER dans ton bot Telegram, ton téléphone ne pourra pas être
> prévenu. Ouvre la conversation du bot et appuie sur DÉMARRER une fois.

## 2. Ce qui se passe pendant ce temps (et qui explique le bouton)

| Étape | Ce qui se passe | Pourquoi |
|---|---|---|
| Tu autorises | Facebook rend un code au serveur | ton mot de passe reste chez Facebook |
| Le serveur échange | le code devient un **jeton de longue durée** (≈ 60 jours) | sinon il faudrait recommencer chaque heure |
| Le serveur lit | tes **comptes publicitaires** et tes **pages** | pour te les présenter en liste |
| Tu choisis | le compte et la page | aucun identifiant à recopier |
| Le tout part | par **Telegram**, sur ton téléphone | c'est le canal privé déjà en place |
| Ton téléphone installe | une tâche vérifie toutes les **10 minutes** | tu n'as rien à faire, et c'est silencieux si rien n'est en attente |

Les droits demandés sont : **gérer tes annonces**, voir la liste de tes pages, **publier au nom de ta
page**. Tu peux retirer cet accès quand tu veux, dans tes réglages Facebook.

## 3. Créer une publicité

Tu donnes cinq choses : **l'image ou la vidéo**, **ton idée de texte**, le **budget**, la **durée**,
la **cible** — par exemple :

    photo.jpg · « un VPN pour jouer à eFootball sans décalage » ·
    15 000 F · 10 jours · hommes 18-35 ans Abidjan, intéressés par eFootball

L'outil écrit alors les textes (gratuitement), calcule le budget par jour, traduit la cible, et met
la publicité en ligne.

## 4. Les garde-fous, et c'est volontaire

- **Plafond de 100 000 F** par publicité : au-delà, l'outil refuse. Une virgule mal placée
  (« 500 000 » au lieu de « 5 000 ») ne peut donc pas partir toute seule. Demande-le moi si tu veux
  le relever.
- **Le budget est relu après création**, chez Meta. Si le montant relu n'est pas le montant voulu,
  **tout est mis en pause immédiatement** — parce que tu as choisi la mise en ligne automatique, et
  qu'une publicité qui part au centuple doit se couper en dix secondes, pas dans la soirée.
- **La monnaie compte** : en euro, Meta compte en centimes (le budget est multiplié par 100) ; en
  franc CFA, il n'y a pas de centime. C'est la devise de TON compte qui décide, et elle est relue.

## 5. L'audit reste disponible

Le bouton bleu « Continuer avec Facebook » de la page d'accueil fait toujours l'audit
(« pourquoi ta pub ne vend pas »). Rien n'a été supprimé.
