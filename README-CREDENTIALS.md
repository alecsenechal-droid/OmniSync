# Credentials Google pour beta testeurs

Ce fichier `credentials.json` permet de se connecter à Google Calendar via OmniSync.

## Installation

1. Télécharge `credentials.json` depuis la page [Releases GitHub](../../releases)
2. Place-le dans :
   ```
   C:\Users\%USERNAME%\AppData\Local\OmniSync\credentials.json
   ```
3. Lance `setup.bat`

## Sécurité

- Ce `credentials.json` est lié au projet Google Cloud "OmniSync" géré par Alec Sénéchal
- Il permet uniquement d'accéder à **TON** Google Calendar (pas celui des autres)
- Limite : 100 utilisateurs max en mode test
- Ne partage pas ce fichier publiquement — il est distribué via Releases, pas dans le repo
