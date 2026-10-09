# Ce que José fait — trois choses, une fois

Tout le reste (déployer, brancher, déclarer les adresses, tester) est de mon côté. Voici les trois
seules choses que je ne peux pas faire à sa place, parce qu'elles demandent son compte.

---

## 1. Créer l'application Meta — 6 clics, 10 minutes

1. Aller sur **`developers.facebook.com`** et se connecter **avec le compte Facebook de ses pages**.
   *(Le mot de passe se tape chez Facebook, jamais ailleurs.)*
2. En haut à droite : **Mes applis** → **Créer une appli**.
3. Choisir **« Autre »** puis **Business** — c'est le type qui donne accès à WhatsApp plus tard.
4. **Nom de l'appli** : `Mon Audit` · **E-mail de contact** : le sien.
5. Dans le tableau de bord → **Paramètres de l'appli** → **Général**. La page affiche deux choses :
   - **Identifiant de l'appli** (une longue suite de chiffres)
   - **Clé secrète** (cliquer sur *Afficher*)
6. **M'envoyer ces deux valeurs.** Je les range dans `~/.hermes/secrets` (droits 600). Elles ne vont
   jamais dans le code, ni dans un fichier visible.

> ⚠️ La clé secrète est un secret : elle s'envoie **ici, dans notre conversation**, et nulle part
> ailleurs. Si un jour elle fuite, on la régénère en un clic — c'est pour ça qu'il ne faut jamais la
> coller dans un site tiers.

---

## 2. Créer un compte d'hébergement gratuit — 10 minutes

**Sur `render.com`** (offre gratuite, adresse HTTPS fournie, pas de carte tant qu'on reste dans les
limites).

1. Créer un compte (connexion possible avec Google ou GitHub).
2. Aller dans **Account Settings** → **API Keys** → **Create API Key**.
3. **M'envoyer cette clé.**

Ensuite **je déploie moi-même** : je pousse le code, je règle les variables, je vérifie que l'adresse
répond. Il n'aura rien à faire dans leur tableau de bord.

---

## 3. Appuyer sur DÉMARRER sur le bot — 5 secondes

Ouvrir **@auditfacebot** dans Telegram et appuyer sur **DÉMARRER**.

C'est la seule chose qui bloque aujourd'hui : Telegram interdit à un bot d'écrire à quelqu'un qui ne
lui a pas parlé en premier. Tant qu'il n'a pas appuyé, je ne peux pas lui envoyer de rapport.

---

## 4. WhatsApp — deux choses de plus, maintenant (5 minutes)

**Pourquoi maintenant et pas plus tard** : ça ne dépend de rien, et ça nous permet de prouver la chaîne
complète (un message reçu → l'audit) avant d'avoir le moindre client.

1. Dans l'application qu'il vient de créer : **Cas d'utilisation** → **WhatsApp** → **Configurer**.
   *(C'est pour ça que l'application doit être de type **Business** : le parcours WhatsApp n'existe que
   pour ce type.)*
2. Meta affiche alors un **numéro d'essai gratuit**. Récupérer et m'envoyer **deux identifiants** :
   - **Phone number ID** (l'identifiant du numéro)
   - **WhatsApp Business Account ID** (l'identifiant du compte professionnel)

**Ce que j'en fais** : je branche la réception des messages (le webhook), et on envoie un message de test
depuis un autre téléphone. S'il arrive dans l'audit, la chaîne est prouvée.

**Ce qui vient plus tard, et pourquoi :**
- **Le domaine HTTPS à déclarer** dans « Allowed domains » → dès que le serveur est en ligne, je lui
  donne l'adresse exacte à coller. Rien à faire maintenant.
- **Tech Provider + vérification d'entreprise + revue de Meta** → seulement pour ouvrir au grand public.
  En **mode développement**, l'écran d'autorisation WhatsApp apparaît déjà pour les personnes ayant un
  rôle (administrateur, développeur, **testeur**) : ses premiers clients connectent donc leur WhatsApp
  tout de suite.
- **La carte bancaire du client chez Meta** → c'est LEUR condition pour terminer l'inscription. À lui
  dire avant, pas après. Rappel : répondre à un client dans les 24 h = 1 000 messages gratuits par mois
  et par numéro depuis le 1er octobre 2026.

---

## Ce qui vient APRÈS (pas maintenant)

- **Ouvrir au public** : ça demande la vérification de son entreprise puis la revue de Meta. Le dossier
  est déjà écrit (`DOSSIER-VALIDATION-META.md`), il n'y a qu'à coller. À faire quand il aura ses
  premiers clients, pas avant.
- **Ajouter un client comme testeur** : App Dashboard → **Rôles** → **Testeurs** → le nom de son compte
  Facebook. Ce client aura alors le 1 clic **immédiatement**, sans aucune validation.
- **WhatsApp** : il crée l'application en type Business (déjà fait à l'étape 1) et on lance l'onboarding
  Tech Provider ensemble, quand les publicités tourneront.

---

## Ce qu'il m'envoie, au total

| Quoi | Où il le trouve | Ce que j'en fais |
|---|---|---|
| **Identifiant de l'appli** | Paramètres de l'appli → Général | je le mets dans les réglages |
| **Clé secrète** | même page, bouton *Afficher* | `~/.hermes/secrets` (droits 600), jamais dans le code |
| **Clé API Render** | Account Settings → API Keys | je déploie et je vérifie |

Trois valeurs. Ensuite, il n'a plus qu'à appuyer sur DÉMARRER sur le bot.
