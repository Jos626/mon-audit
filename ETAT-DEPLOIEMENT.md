# ÉTAT DU DÉPLOIEMENT — Mon Audit (10/10/2026, 01h)

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
