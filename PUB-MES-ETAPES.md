# Mettre une pub en ligne tout seul — la seule chose que je ne peux pas faire à ta place

L'outil est prêt : il écrit la publicité, calcule le budget par jour, traduit ta cible, et sait la
créer dans ton compte. **Il ne lui manque qu'une chose : le droit de dépenser à ta place.** Ce droit
s'appelle un **jeton** — une clé que TU donnes, que tu peux retirer quand tu veux. Ton mot de passe
Facebook n'est jamais demandé, ni ici ni ailleurs.

Deux chemins. Le premier pour essayer **tout de suite**, le second pour que ça tourne **tous les jours**.

---

## Chemin A — Essayer aujourd'hui (jeton d'une heure)

1. Va sur **`developers.facebook.com/tools/explorer`** (connecté avec le compte de tes pages).
2. En haut à droite, dans **« Application Meta »**, choisis **`Mon audit`**.
3. Dans **« Autorisations »**, ajoute ces trois-là :
   - `ads_management` (gérer les annonces)
   - `pages_show_list` (voir mes pages)
   - `pages_manage_ads` (gérer les pubs de la page)
4. Clique sur **« Générer un jeton d'accès »**.
5. **Copie le jeton** (il commence par `EAA…`) et **envoie-le moi ici**, comme tu m'envoies un message.

⚠️ Ce jeton **meurt au bout d'une heure** : parfait pour vérifier que la chaîne fonctionne, pas pour
l'usage quotidien.

---

## Chemin B — Pour de vrai, tous les jours (jeton durable)

C'est le même genre de jeton, mais rattaché à une **identité automatique** de ton entreprise : il ne
périme pas au bout d'une heure, et il n'est lié à aucun mot de passe.

1. Va sur **`business.facebook.com`** → **Paramètres de l'entreprise**.
2. Dans le menu, choisis **« Utilisateurs » → « Utilisateurs système »**.
3. **Ajouter** → nom : `Publication auto` → rôle : **Admin** (ou Employé).
4. Sélectionne `Publication auto` → **« Générer un jeton »** :
   - **Application** : `Mon audit`
   - **Coche** : `ads_management`, `pages_show_list`, `pages_manage_ads`, `business_management`
   - **Générer**. ⚠️ Le jeton ne s'affiche **qu'une seule fois** : copie-le et envoie-le moi.
5. **Assigne les actifs** à `Publication auto` (bouton « Ajouter des actifs ») :
   - ton **compte publicitaire** → avec « Gérer les campagnes »
   - ta **page Facebook** → avec « Créer du contenu »

Sans l'étape 5, le jeton existe mais n'a le droit sur rien : c'est l'erreur la plus fréquente.

---

## Ce que je fais dès que j'ai le jeton

Je lance `meta-choisir.py` : il te liste **tes comptes publicitaires** et **tes pages**, numérotés.
Tu me réponds « 1 et 2 » — et c'est fini, les réglages sont rangés dans un fichier protégé
(droits 600, comme les autres secrets).

Ensuite, à chaque publicité, l'outil :

1. **écrit les textes** (modèle gratuit, la clé est déjà sur ton téléphone) ;
2. **vérifie** : visuel reconnu, budget, durée, destination, cible (et refuse au-delà du plafond) ;
3. **envoie** chez Meta : campagne → ensemble → annonce ;
4. **relit** ce qui a été créé et **compare le budget au montant voulu** — et **si le montant relu
   n'est pas le bon, il met TOUT en pause tout seul**, immédiatement, plutôt que de laisser brûler
   un budget faux. C'est la protection la plus importante, parce que tu as choisi la mise en ligne
   automatique.

## Le plafond de sécurité, et comment le changer

Par défaut, une publicité **au-dessus de 100 000 F CFA est refusée** par le moteur. C'est ce qui
empêche une virgule mal placée (« 500 000 » au lieu de « 5 000 ») de partir telle quelle.

Pour le relever exprès, c'est une ligne dans `pub.py` (`PLAFOND_BUDGET`) — demande-le moi, je le
change et je te le dis.
