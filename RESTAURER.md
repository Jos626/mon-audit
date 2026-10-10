# RESTAURER L'OUTIL D'AUDIT — si le téléphone disparaît

Bonne nouvelle : **celui-ci ne dépend presque pas du téléphone.**

## Le site

Le code est sur `github.com/Jos626/mon-audit`. Render le surveille et le redéploie tout seul à
chaque envoi. Si le téléphone disparaît : **le site continue de fonctionner**, sans rien faire.
Il suffit de cloner le dépôt pour pouvoir le modifier de nouveau.

⚠️ Le dépôt doit rester **public** : le service gratuit de Render n'a pas accès aux dépôts privés
(c'est la raison pour laquelle il a été rendu public le 10/10/2026).

## La clé secrète et les variables

Elles vivent chez Render, pas sur le téléphone :

| Variable (Render → service « mon-audit ») | Où la retrouver |
|---|---|
| `META_APP_ID` | 1114320824585270 |
| `META_APP_SECRET` | developers.facebook.com → Paramètres → Général → Clé secrète |
| `AUDIT_SECRET_LIENS` | **à régénérer** (clé de signature des liens) |
| `ADRESSE_PUBLIQUE` | https://mon-audit.onrender.com |

⚠️ **Piège appris à la dure :** les variables d'environnement ne s'appliquent qu'au déploiement
**suivant**. Les poser ne suffit pas — il faut relancer un déploiement, sinon le service redémarre
avec l'ancien jeu et plante. Et l'API Render attend un **tableau brut** pour `PUT /env-vars`
(`[{"key": ..., "value": ...}]`), pas un objet.

## Ce qui est perdu si le téléphone disparaît

Uniquement le **bot Telegram d'audit** (@auditfacebot), qui ne sert plus à rien depuis que le
rapport s'affiche dans la page (décision de José le 10/10/2026). Autrement dit : rien d'important.
