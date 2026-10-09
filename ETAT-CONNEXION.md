# État de la connexion Meta — à jour le 09/10/2026

| Quoi | Valeur | Où |
|---|---|---|
| Application | `Mon audit` | tableau de bord Meta |
| **App ID** | **1114320824585270** | `~/.hermes/secrets/meta-app-id.txt` (600) |
| Portefeuille business | `105365702195413` | chez Meta |
| Type | Business (Facebook Login for Business installé) | — |
| Mode | **Non publiée** = développement → les testeurs fonctionnent sans validation | — |
| Clé secrète | *(en attente — PAS bloquant)* | à ranger dans `~/.hermes/secrets/meta-app-secret.txt` (600) |
| Clé API Render | *(en attente)* | pour le déploiement |
| WhatsApp (Phone number ID / WABA ID) | *(en attente)* | étape « Cas d'utilisation → WhatsApp » |

## Adresses à déclarer chez Meta, une fois le serveur en ligne

- **URI de redirection OAuth** (Facebook Login → Paramètres) : `https://<adresse>/callback`
- **Allowed domains / Valid OAuth redirect URIs** (pour WhatsApp) : le même domaine en HTTPS

## Ce qui est déjà vérifié de mon côté

- Le serveur de connexion fonctionne : page d'accueil, page de confidentialité (exigée par Meta), lien
  signé, et un lien forgé reçoit un **403**.
- Le bot `@auditfacebot` tourne, et un gardien le relance toutes les 10 minutes s'il tombe.
- Les quatre batteries du projet d'audit passent (audit 27, portrait 19, connexion 12, WhatsApp 19).
