# Le 1 clic — ce qui le bloque vraiment, et comment on y arrive

**Demande de José (09/10/2026)** : « Export WhatsApp et jeton Meta, c'est compliqué et long pour un
débutant et quelqu'un qui n'a pas le temps. Je veux que ça se passe en 1 clic vite fait et l'audit
démarre. »

Il a raison. Le parcours actuel — choisir une appli, cocher cinq permissions, générer un jeton qui
expire en une heure — est un parcours de **développeur**. Un commerçant qui gère sa boutique depuis son
téléphone n'ira pas au bout, même avec un mode d'emploi parfait. Ce n'est pas un problème de
pédagogie, c'est un problème de conception.

---

## 1. Pourquoi il n'existe pas de 1 clic aujourd'hui (et pourquoi ce n'est pas notre faute)

Les données publicitaires vivent **derrière l'authentification de Meta**. Trois portes possibles :

| La porte | Ce que le client fait | Ce qu'il faut de notre côté |
|---|---|---|
| Graph API Explorer (l'actuel) | choisit son appli, coche 5 permissions, génère un jeton | rien — mais ~10 gestes, et le jeton meurt en 1 h |
| **Facebook Login** (le vrai 1 clic) | **appuie sur « Continuer avec Facebook »** | une **adresse HTTPS publique** de retour + l'appli validée pour les comptes de tiers |
| Partenariat Business Manager | ajoute notre Business Manager à son compte pub | un Business Manager + une demande de partenariat |

**Vérifié le 09/10/2026 :**
- Il n'existe **aucun lien qui pré-remplit les permissions** dans l'Explorer (`path` et `method`
  seulement ; le jeton ne peut pas être injecté par l'URL). Ne pas en inventer un : un lien mort fait
  perdre la confiance en une seconde.
- **Une appli en mode développement fait tomber la barrière des validations** : « si votre appli est en
  développement, vous pouvez accorder n'importe quelle permission et vos requêtes la respectent ».
  Autrement dit, **les premiers clients peuvent avoir le 1 clic sans aucune validation de Meta** — à
  condition d'être ajoutés comme testeurs de l'appli, et à condition d'avoir une adresse de retour.

## 2. Ce qui manque, et c'est UNE seule chose : un serveur

Le 1 clic n'est pas bloqué par une validation, il est bloqué par une **adresse HTTPS publique** (Meta
exige une URL de retour déclarée, et il refuse tout ce qui n'est pas en HTTPS).

Le même serveur débloque **trois choses d'un coup** :
1. **Facebook Login** → le client appuie une fois, l'audit part. Aujourd'hui pour ses testeurs, demain
   pour tout le monde après validation.
2. **WhatsApp Embedded Signup** → le client branche son numéro en un geste, et les conversations
   arrivent en direct (vitesse de réponse, relance) — l'autre moitié de son problème.
3. **L'application web installable** sur l'écran d'accueil, Android et iPhone.

Coût : **environ 5 $ par mois**. C'est la seule dépense incompressible du projet.

## 3. Ce qu'il doit faire, lui — et ce que je prépare

**De son côté, une fois, 30 à 45 minutes :**
1. Créer l'application Meta (`developers.facebook.com` → Mes applis → Créer). Je lui donne les champs
   exacts, comme pour AdsGram.
2. Vérifier son entreprise (nom, adresse, téléphone, e-mail, site, documents).
3. Prendre un petit serveur (5 $/mois) et me donner l'accès.

**De mon côté, préparé d'avance :**
- la **page de retour** (le code de connexion) et la page de suppression des données — Meta les exige
  dans la soumission ;
- le **texte de la demande de validation**, permission par permission, avec l'usage exact ;
- le **script de la capture vidéo** que Meta réclame (démonstration du parcours de connexion et de
  l'écran de résultats) — c'est la pièce qui fait accepter ou refuser ;
- la **politique de confidentialité** (où vont les données, ce qui n'est jamais conservé).

## 4. Le parcours client, une fois le serveur en place

```
Le commerçant ouvre le lien
   ↓
Appuie sur « Continuer avec Facebook »        ← UN geste
   ↓
Choisit le compte publicitaire à auditer      ← UN geste
   ↓
L'audit démarre tout seul et arrive dans son Telegram
```

Et pour WhatsApp : « Connecter WhatsApp » → il choisit son numéro → les conversations arrivent en
direct. Deux gestes, une fois, et plus jamais rien à faire ensuite.

## 5. En attendant — ce qui reste vrai

- **Le chemin d'aujourd'hui reste utilisable**, mais il faut être honnête sur son public : il convient
  à quelqu'un qui a déjà touché à Ads Manager, pas à un débutant pressé.
- **Aucune donnée n'est inventée** et **aucun mot de passe n'est demandé**, quel que soit le chemin.
- Un **export de discussion WhatsApp** reste le meilleur moyen d'avoir l'historique passé, même après
  le branchement direct : la connexion ne voit que ce qui arrive après elle.
