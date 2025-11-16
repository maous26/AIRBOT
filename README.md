# Gearted Discord Bot

Bot Discord pour le serveur Gearted avec système de tirage et points Builders.

## Fonctionnalités

- **Système de tirage hebdomadaire** : Les membres s'inscrivent avec `!tirage`, le staff lance le tirage avec `!tirage go`
- **Système de points Builders** : Points attribués par le staff pour récompenser les contributions
- **Attribution automatique de rôles** : Rôle "Gagnant de la semaine" et "Builders Gearted"

## Déploiement sur Railway

### 1. Prérequis

- Un compte Railway (https://railway.app)
- Votre token de bot Discord
- L'ID de votre serveur Discord

### 2. Configuration Discord Bot

1. Allez sur https://discord.com/developers/applications
2. Créez une application ou sélectionnez votre bot existant
3. Dans **Bot**, copiez le token
4. Dans **OAuth2 > URL Generator**, sélectionnez :
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Manage Roles`, `Send Messages`, `Read Message History`, `Mention Everyone`

### 3. Déploiement Railway

#### Étape 1 : Créer un nouveau projet
1. Connectez-vous à Railway
2. Cliquez sur **New Project**
3. Sélectionnez **Deploy from GitHub repo** (ou **Empty Project** si vous uploadez manuellement)

#### Étape 2 : Configurer les variables d'environnement
Dans Railway, allez dans **Variables** et ajoutez :

```
DISCORD_BOT_TOKEN=votre_token_de_bot_ici
```

⚠️ **Important** : Ne partagez JAMAIS votre token publiquement !

#### Étape 3 : Fichiers à uploader
Si vous uploadez manuellement, assurez-vous d'avoir ces fichiers :

- ✅ `gearted_bot.py` (code principal)
- ✅ `requirements.txt` (dépendances Python)
- ✅ `Procfile` (commande de démarrage)
- ✅ `runtime.txt` (version Python - optionnel)

#### Étape 4 : Déploiement automatique
Railway détectera automatiquement :
- Le `Procfile` pour savoir comment lancer le bot
- Le `requirements.txt` pour installer les dépendances
- Le `runtime.txt` pour la version Python

Le bot démarre automatiquement après le déploiement ! 🚀

### 4. Vérification

Une fois déployé :
1. Vérifiez les logs dans Railway (onglet **Deployments** > **View Logs**)
2. Vous devriez voir : `✅ Connecté comme [Nom du bot]`
3. Testez avec `!ping` dans votre serveur Discord

## Configuration du Bot

Dans `gearted_bot.py`, vérifiez ces paramètres :

```python
GUILD_ID = 1434470610565726325  # ID de votre serveur
GIVEAWAY_CHANNEL_NAME = "🎁-giveaways"
HOF_CHANNEL_NAME = "🏆-hall-of-fame"
WINNER_ROLE_NAME = "Gagnant de la semaine"
BUILDERS_ROLE_NAME = "Unité Alpha – Builders Gearted"
BUILDERS_ANNOUNCE_CHANNEL_NAME = "🎯-programme-builders"
BUILDER_THRESHOLD = 200  # Points nécessaires pour le rôle Builders
```

## Commandes Disponibles

### Pour tous les membres
- `!ping` : Vérifier si le bot est en ligne
- `!tirage` : S'inscrire au tirage de la semaine (dans #🎁-giveaways)
- `!builderstats` : Voir ses propres points Builders

### Pour le staff (permission "Gérer le serveur")
- `!tirage liste` : Voir la liste des participants
- `!tirage go` : Lancer le tirage et sélectionner un gagnant
- `!tirage reset` : Réinitialiser la liste des participants
- `!builderadd @user 10` : Ajouter des points Builders
- `!builderremove @user 5` : Retirer des points Builders
- `!builderstats @user` : Voir les points d'un membre
- `!builderboard [limite]` : Afficher le classement Builders

## Persistence des Données

Le bot crée automatiquement 2 fichiers JSON pour sauvegarder les données :
- `tirage_participants.json` : Liste des participants au tirage
- `builders_points.json` : Points Builders de chaque membre

⚠️ **Important pour Railway** : Railway a un système de fichiers éphémère. Si vous redémarrez le service, ces fichiers peuvent être perdus. Pour une solution permanente, utilisez Railway Volumes ou une base de données externe.

### Solution recommandée pour la persistence :
Dans Railway, ajoutez un **Volume** :
1. Allez dans votre service > **Settings**
2. Cliquez sur **+ New Volume**
3. Mount Path : `/app/data`
4. Modifiez le code pour sauvegarder dans `/app/data/` au lieu de `./`

## Support

Pour toute question ou problème :
1. Vérifiez les logs Railway
2. Vérifiez que le bot a les bonnes permissions Discord
3. Vérifiez que les noms de salons/rôles correspondent exactement

## Sécurité

- ⚠️ Ne commitez JAMAIS votre token dans le code
- ✅ Utilisez toujours des variables d'environnement
- ✅ Ajoutez `.env` à votre `.gitignore`

