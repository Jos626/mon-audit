# État du déploiement — 10/10/2026

## En ligne

| Quoi | Valeur |
|---|---|
| Adresse du serveur | **https://mon-audit.onrender.com** |
| Service Render | `srv-db4o4ul9fdbs73a9la9g` · plan **free** · région Francfort |
| Dépôt de code | `github.com/Jos626/mon-audit` — **public** (choix de José : déployer tout de suite) |
| Déploiement | **live** · vérifié HTTP 200 sur les deux pages |
| Identifiant de l'appli Meta | `1114320824585270` |

## Variables posées chez Render

`META_APP_ID` · `AUDIT_SECRET_LIENS` (signe les liens clients) · `ADRESSE_PUBLIQUE` · `PYTHON_VERSION`

## Le piège rencontré, noté pour ne pas y revenir

Le premier déploiement a échoué avec « Il manque meta-app-id » — **les variables ont été posées
APRÈS le début du déploiement, et Render ne les applique qu'au déploiement suivant**. Il faut donc
TOUJOURS : poser les variables d'abord, puis déclencher un déploiement. (Diagnostic fait en lisant
leurs journaux via `/v1/logs?ownerId=…&resource=…`, pas en devinant.)

## Ce qui reste

| Quoi | Qui |
|---|---|
| Déclarer `https://mon-audit.onrender.com/callback` dans Facebook Login → Paramètres → **URI de redirection OAuth valides** | José (un champ) |
| Appuyer sur **DÉMARRER** sur @auditfacebot | José (5 secondes) |
| La **clé secrète** de l'appli (nécessaire pour que la connexion aboutisse) | à récupérer — le bouton « Afficher » ne répond pas sur son navigateur de téléphone ; à refaire en version ordinateur |
| Ajouter le cas d'utilisation WhatsApp | ensemble |
