# Google Calendar

OmniSync utilisera l'API officielle Google Calendar.

## MVP

Pendant le MVP, la connexion Google sera documentee pour developpeurs avec un fichier `credentials.json` local. Ce fichier ne doit jamais etre commite.

## UX cible

A terme, l'utilisateur devrait cliquer sur "Connecter Google Calendar", choisir son compte Google, puis revenir dans OmniSync sans manipuler Google Cloud Console.

## Evenements crees

Les evenements OmniSync doivent porter une propriete privee telle que:

```text
source=omnisync
omnisync_uid=<uid stable>
```

Cela permet de mettre a jour ou supprimer seulement les evenements crees par OmniSync.

## Regles de sync MVP

- Les evenements sans date sont stockes dans SQLite mais ignores dans Google Calendar.
- Les evenements passes sont ignores par defaut.
- Pour tester les evenements passes en developpement: `OMNISYNC_SYNC_PAST_EVENTS=true`.
- `run.bat run --calendar-dry-run` affiche les actions sans rien ecrire dans Google.
