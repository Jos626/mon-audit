# Dossier de validation Meta — prêt à coller

Ce dossier sert à la **revue d'application** de Meta. Il est écrit pour être recopié tel quel dans les
formulaires, le jour où José aura créé son application et pris son serveur.

⚠️ **À SAVOIR AVANT DE COMMENCER** : une application **en mode développement** accorde **toutes** les
permissions à ses testeurs, sans aucune validation. Les premiers clients peuvent donc avoir le 1 clic
**tout de suite**, en les ajoutant comme testeurs (App Dashboard → Rôles → Testeurs). La revue ne sert
qu'à ouvrir au public : elle n'est pas un préalable au premier test.

---

## 1. Ce que l'application fait (description à coller)

> **Pubmeta** aide les commerçants à comprendre pourquoi leur publicité Facebook ne leur rapporte pas
> de commandes. Le commerçant se connecte avec Facebook, choisit le compte publicitaire qu'il veut
> analyser, et reçoit un rapport : où part son budget, quelles annonces ne rapportent rien, quelles
> annonces fonctionnent (et qu'il ne faut pas modifier), et pourquoi son compte n'arrive pas à mesurer
> ses ventes. Il peut aussi connecter son numéro WhatsApp Business pour que les questions de ses
> clients soient analysées : ce qu'ils demandent, ce qui les bloque, les villes d'où ils écrivent et
> les heures où ils écrivent.
>
> L'application ne publie rien, ne modifie aucune campagne, ne dépense pas d'argent et n'envoie aucun
> message en dehors de la fenêtre de service de 24 heures prévue par WhatsApp. Toutes les données sont
> lues, jamais écrites.

## 2. Justification, permission par permission

**`ads_read`** — Nécessaire pour lire les statistiques publicitaires du compte que le commerçant a
choisi : montant dépensé, impressions, clics, résultats et coût par résultat, par annonce. C'est la
matière première du rapport : sans cette lecture, l'outil n'a rien à analyser. L'application n'écrit
jamais dans le compte publicitaire.

**`business_management`** — Nécessaire quand le compte publicitaire est rattaché à un Business Manager :
c'est ce qui permet de retrouver le compte et la page du commerçant. Sans cette permission, les
comptes rattachés à un Business Manager ne sont pas visibles et le rapport serait vide.

**`pages_show_list`** — Nécessaire pour afficher au commerçant la liste de ses pages et lui laisser
choisir celle dont il veut analyser les commentaires.

**`pages_read_engagement`** — Nécessaire pour lire les commentaires publics des publications de cette
page. Ces commentaires sont la matière la plus utile du rapport : c'est là que les clients disent
franchement ce qui les bloque (« c'est trop cher », « vous livrez chez moi ? »). L'application ne
publie jamais, ne répond à aucun commentaire et ne supprime rien.

**`read_insights`** — Nécessaire pour lire les statistiques d'audience de la page (répartition par âge,
par sexe et par ville). C'est la seule source honnête des données démographiques : l'outil refuse
explicitement de deviner un âge ou un revenu.

**`whatsapp_business_messaging` / `whatsapp_business_management`** — Nécessaires pour recevoir les
messages que les clients envoient au numéro professionnel, afin d'en tirer les questions récurrentes et
les objections. L'application ne démarre aucune conversation en dehors de la fenêtre de 24 h.

## 3. Script de la capture vidéo (Meta l'exige, permission par permission)

La vidéo doit montrer, sans coupe, les cinq étapes ci-dessous. Commentaire à dire en même temps :

1. **L'écran d'entrée de l'application.** « Voici Pubmeta. Le commerçant appuie sur *Continuer avec
   Facebook*. »
2. **Le dialogue Facebook Login.** « C'est Facebook qui demande les permissions, sur ses propres pages.
   L'application ne voit jamais le mot de passe. » → cliquer sur *Continuer*.
3. **Le choix du compte publicitaire.** « Le commerçant choisit lequel de ses comptes il veut analyser. »
4. **Le rapport affiché.** « Voici les données lues : montant dépensé, impressions, résultats, coût par
   résultat, et le détail par annonce. » → **montrer l'écran avec les chiffres visibles** (Meta exige
   de voir que les données sont réellement affichées).
5. **Le retour dans Telegram.** « Le commerçant reçoit son rapport dans Telegram, l'application où il
   travaille déjà. »

Puis, une seconde séquence pour WhatsApp : connecter le numéro, envoyer un message de test depuis un
autre téléphone, et montrer le message reçu dans l'application.

## 4. Politique de confidentialité (version courte, à publier)

> **Pubmeta** lit les données publicitaires et les conversations que le commerçant accepte
> explicitement de partager, dans le seul but de produire un rapport pour lui.
>
> · **Aucun mot de passe n'est jamais demandé.** L'accès passe par une autorisation révocable, que le
>   commerçant peut retirer à tout moment depuis Facebook (Réglages → Applications et sites web).
> · **Le jeton d'accès n'est pas conservé** : il vit le temps de l'audit.
> · **Les conversations analysées** restent dans l'espace du commerçant et sont supprimées à sa demande
>   (commande `/efface`).
> · **Aucune donnée n'est vendue, ni partagée** avec un autre client, ni utilisée pour entraîner un
>   modèle.
> · **Rien n'est publié, modifié ou envoyé** en dehors des messages de service autorisés par WhatsApp.

## 5. Pages à fournir (Meta les exige dans la soumission)

- **URL de la politique de confidentialité** — le texte du point 4, publié.
- **URL de suppression des données** — une page qui explique `/efface` et donne un contact.
- **URL de redirection OAuth valide** — en HTTPS, sur le domaine du serveur.

---

## Ce qui reste à faire, dans l'ordre

1. José crée l'application Meta (30 minutes au total, comme pour AdsGram).
2. José prend le serveur (≈ 5 $/mois) et me donne l'accès.
3. Je pose l'écran de connexion + ces pages, et je branche le serveur.
4. Les **premiers clients passent en testeurs** → ils ont le 1 clic **immédiatement**.
5. Je dépose la revue avec ce dossier → l'ouverture au public.
