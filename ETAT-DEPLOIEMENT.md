# ÉTAT DU DÉPLOIEMENT — Pubmeta (10/10/2026, 01h)

## En ligne, vérifié depuis Internet

| Élément | Valeur | Vérifié |
|---|---|---|
| Adresse | https://mon-audit.onrender.com | HTTP 200 |
| Page d'accueil | bouton « Continuer avec Facebook » | présente |
| Page /confidentialite | exigée par Meta | HTTP 200 |
| Lien forgé (/callback sans signature) | refusé | **HTTP 403** |
| Déploiement Render | live, plan gratuit, Francfort | oui |
| Service ID | srv-db4o4ul9fdbs73a9la9g | — |
| Dépôt | github.com/Jos626/mon-audit (public) | à jour |

## Variables d'environnement (Render, service mon-audit)

- `META_APP_ID` = 1114320824585270
- `META_APP_SECRET` = la clé secrète de l'appli (rangée aussi dans ~/.hermes/secrets/meta-app-secret.txt, 600)
- `AUDIT_SECRET_LIENS` = clé de signature des liens Telegram
- `ADRESSE_PUBLIQUE` = https://mon-audit.onrender.com

## TEST DE LA CHAÎNE COMPLÈTE (fait, concluant)

Lien signé comme celui d'un vrai client + faux code :
`GET /callback?code=code-de-test-invalide&state=<signé HMAC>`
→ HTTP 200, réponse : « Facebook a refusé la demande : Invalid verification code format. »

**Ce que ça prouve** : le serveur a bien appelé le point d'échange de jetons de Meta, et Meta a
répondu. Donc l'identifiant d'appli, l'adresse de retour déclarée et la clé secrète sont acceptés
par Meta. Le seul refus portait sur le faux code — c'est exactement ce qu'on voulait tester.

## ⚠️ DEUX PIÈGES DE L'API RENDER (perdus une heure chacun si on les oublie)

1. **Les variables d'environnement ne s'appliquent qu'au déploiement SUIVANT.** Poser une variable
   ne suffit pas : il faut relancer un déploiement, sinon le service démarre avec l'ancien jeu et
   plante (« Il manque meta-app-id »). Poser les variables AVANT de créer/déployer.
2. **`PUT /v1/services/{id}/env-vars` attend un TABLEAU BRUT** :
   `[{"key": "X", "value": "Y"}]` → 200. La forme `{"envVars": [...]}` → 400 « invalid JSON ».
   Et un PUT **remplace tout le jeu** : envoyer toutes les variables, sinon elles sont supprimées.

## Reste à faire

- José : appuyer sur DÉMARRER sur @auditfacebot (le bot tourne, mais Telegram ne le laisse pas
  écrire à quelqu'un qui ne l'a pas démarré).
- Un vrai essai client : « Continuer avec Facebook » → l'audit doit se dérouler jusqu'au rapport.
- Le service gratuit **s'endort** après 15 min : la première visite prend ~1 minute.

## APPLICATION INSTALLABLE (PWA) — faite et vérifiée le 10/10/2026

Le client n'installe rien de compliqué : il ouvre l'adresse dans Chrome, menu ⋮ →
« Ajouter à l'écran d'accueil ». L'icône « Pubmeta » apparaît, et s'ouvre en plein écran.

Ce qu'il faut pour que Chrome l'autorise (les trois, sinon pas d'installation) :
1. HTTPS — Render s'en charge.
2. Un **manifeste** (`/manifeste.json`) : nom, start_url, display standalone, icônes 192 et 512
   (+ une « masquable », qu'Android redécoupe lui-même).
3. Un **service worker** (`/sw.js`). ⚠️ Le nôtre ne met RIEN en cache, exprès : l'audit parle du
   compte publicitaire du client, et une page resservie par un cache peut mentir.

Icônes : de vrais PNG, dessinés par `fabriquer-icones.py` (PIL) et versionnés dans le projet —
pas d'images récupérées ailleurs. Garde-fou : `tests-pwa.py` (15 contrôles).

Aussi : le mode navigation privée de Chrome **refuse** l'installation. Il faut une fenêtre normale.

## UN VRAI FICHIER .APK (pour plus tard, si José le veut)

Possible sans Android Studio : **PWABuilder** (gratuit, Microsoft) transforme cette PWA en APK/AAB.
Deux voies, deux coûts :
- **APK téléchargé directement** → l'utilisateur doit autoriser « sources inconnues » (avertissement
  Android + méfiance légitime).
- **APK sur Google Play** → compte développeur 25 $ une fois, revue de Google, et une déclaration
  « sécurité des données » (notre page /confidentialite la sert déjà).
Conclusion honnête : la page installable donne 95 % du bénéfice pour 0 € et 0 friction. L'APK ne
vaut le coup que si des clients refusent Telegram ET Chrome.
