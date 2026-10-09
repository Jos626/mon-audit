# Mettre le serveur en ligne — la marche à suivre

## D'abord : ce n'est pas OVH

**Aucun fournisseur n'est imposé.** Ce dont le 1 clic a besoin, c'est exactement deux choses :

1. une **adresse HTTPS publique** (Facebook refuse tout ce qui n'est pas en HTTPS) ;
2. un endroit qui fait tourner **Python**.

Tout ce qui remplit ces deux conditions fait l'affaire.

## Étape 1 — le chemin gratuit, pour commencer tout de suite (0 franc)

**Render** (render.com) — offre gratuite de service web Python, adresse HTTPS fournie
(`ton-service.onrender.com`), pas de carte demandée tant qu'on reste dans les limites.

Ce que Render dit lui-même de son offre gratuite (à savoir avant) :
- le service **s'endort après 15 minutes sans visite** et met **environ une minute** à se réveiller ;
- 750 heures d'instance par mois offertes (un service endormi ne consomme pas) ;
- leurs mots : *« ne pas utiliser pour de la production ; parfait pour tester »*.

**Conclusion honnête :** l'offre gratuite suffit pour le 1 clic de la connexion (le réveil d'une minute
ne gêne personne qui vient de cliquer). Elle **ne suffit pas** pour le WhatsApp en direct, qui doit être
joignable à toute heure.

**Ce que José fait (10 minutes, une fois) :**
1. Créer un compte sur render.com.
2. Créer un *Web Service* → *Deploy from a Git repository* (je lui prépare le dépôt : le code est prêt,
   et il n'a **aucune dépendance** à installer — tout est en bibliothèque standard).
3. Renseigner trois variables d'environnement (Render → Environment) :
   - `META_APP_ID` — l'identifiant de son application Meta
   - `META_APP_SECRET` — son secret (jamais dans le code)
   - `AUDIT_SECRET_LIENS` — une longue chaîne au hasard, qui signe les liens envoyés aux clients
   - `ADRESSE_PUBLIQUE` — l'adresse HTTPS fournie par Render
4. Me donner l'adresse : je déclare l'URL de retour dans l'application Meta et je vérifie en direct.

## Étape 2 — quand il voudra payer (toujours joignable)

**OVHcloud VPS-1** — **3,81 € HT/mois, soit 4,57 € TTC/mois** (prix relevé sur leur propre page le
09/10/2026 : 2 vCores, 4 Go de RAM, 40 Go SSD). C'est le serveur qui fait tourner le bot, le webhook
WhatsApp et l'application web, jour et nuit.

Alternative équivalente : **Render plan payant à 7 $/mois** (même code, aucune migration à faire).

⚠️ **Sur le paiement depuis la Côte d'Ivoire** : je ne sais pas si sa carte passe sur ces services —
c'est justement pour ça que l'étape 1 est gratuite. S'il veut payer plus tard et que la carte est
refusée, on cherchera ensemble (il a déjà des solutions de ce côté).

## Étape 3 bis — WhatsApp : le 1 geste, et il fonctionne SANS attendre Meta

Le geste existe : **Embedded Signup**. Le commerçant appuie sur « Connecter WhatsApp », Meta ouvre son
propre écran, il choisit sa page professionnelle et son numéro, et c'est fini. **Aucun code QR, aucun
mot de passe** — la même mécanique que « Continuer avec Facebook ».

**Ce que les documents de Meta disent, mot pour mot (relevé le 09/10/2026) :**

> « Tant que votre application est en **mode développement**, ces permissions apparaissent dans l'écran
> d'autorisation d'Embedded Signup **pour toute personne ayant un rôle d'administrateur, de développeur
> ou de testeur** sur votre application. En revanche, une fois l'application passée en mode public,
> seules les permissions validées par la revue apparaissent dans le parcours. »

Traduction : **les premiers clients connectent leur WhatsApp tout de suite**, sans attendre la revue de
Meta — il suffit de les ajouter comme testeurs. La revue ne sert qu'à ouvrir au grand public.

### Ce que ça coûte au commerçant

- **Répondre à un client dans les 24 h** = « message de service ». Ces messages ont été **gratuits** à
  partir du 1er novembre 2024, et **depuis le 1er octobre 2026 Meta en offre 1 000 par mois et par
  numéro**, puis facture au-delà. Pour un commerçant qui répond à ses clients, la facture est donc
  nulle ou presque.
- **Envoyer une campagne** (un modèle « marketing ») est facturé, au tarif du pays.
- ⚠️ **Le client doit tout de même enregistrer un moyen de paiement** chez Meta pour terminer son
  inscription. C'est une condition de Meta, pas la nôtre — à lui dire AVANT, pas après.

### Ce qu'il faut régler dans l'application Meta (en plus des publicités)

- créer l'application en type **Business** (l'assistant Embedded Signup n'existe que pour ce type) ;
- lancer l'**onboarding Tech Provider** (App Dashboard → Cas d'utilisation → WhatsApp) ;
- déclarer le **domaine HTTPS** dans « Allowed domains » et « Valid OAuth redirect URIs » : sans ça, le
  parcours ne rend ni l'identifiant du compte, ni le numéro, ni le code à échanger ;
- au retour du parcours, trois appels à enchaîner : échanger le code contre un **jeton d'entreprise**,
  abonner l'application au compte (`/<WABA_ID>/subscribed_apps`), puis **enregistrer le numéro**
  (`/<PHONE_NUMBER_ID>/register` avec un PIN à 6 chiffres).

### Pour tester AVANT d'avoir un client

L'App Dashboard offre un **compte bac à sable** (WhatsApp → Démarrage → *Claim sandbox account*) qui
simule un vrai client qui termine le parcours et rend un identifiant de compte, un numéro et un code à
échanger. Il est valable 30 jours. C'est avec lui qu'on prouvera la chaîne complète avant de brancher
quelqu'un.

## Étape 4 — la revue de Meta (pour ouvrir au public)

Tant que l'application Meta est **en mode développement**, elle fonctionne **sans validation** pour les
comptes ajoutés comme **testeurs** (App Dashboard → Rôles → Testeurs). Les premiers clients ont donc le
1 clic immédiatement.

Pour ouvrir à tout le monde, il faudra la **revue d'application** — le dossier est déjà prêt, à coller :
`DOSSIER-VALIDATION-META.md` (description, justification de chaque permission, script de la capture
vidéo exigée, politique de confidentialité).

## Ce que j'ai besoin de lui, dans l'ordre

| Quand | Ce qu'il me donne | Ce que je fais |
|---|---|---|
| maintenant | l'identifiant et le secret de son application Meta | je les range dans `~/.hermes/secrets` (droits 600) |
| maintenant | l'adresse HTTPS (Render gratuit) | je déclare l'URL de retour et je teste le parcours |
| plus tard | l'accès au serveur payé | je pose le bot, le webhook WhatsApp et l'application web |

## Rappel de ce qui ne change jamais

- **Aucun mot de passe n'est demandé** au commerçant, sur aucun chemin.
- **Le jeton n'est pas conservé** après l'audit.
- **Une adresse forgée est refusée** : le lien envoyé au client est signé (vérifié : un `state` inventé
  reçoit un 403).
