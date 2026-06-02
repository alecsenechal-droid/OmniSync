# Troubleshooting

## Omnivox refuse la connexion

- Verifier DA / mot de passe.
- Ouvrir Omnivox manuellement pour voir si une validation MFA est demandee.
- Relancer `run.bat init` si les identifiants ont change.

## Le PC etait ferme a 05:00

Le scheduler catch-up sera ajoute au MVP technique. Pour l'instant, lancez:

```powershell
run.bat run
```

## Google Calendar ne se met pas a jour

- Verifier le token Google.
- Verifier le calendar ID.
- Lancer `run.bat doctor`.
- Tester `run.bat run --dry-run`.

## Doublons dans le calendrier

OmniSync doit utiliser des UID stables. Si des doublons apparaissent, ne supprimez pas manuellement tous vos evenements personnels: supprimez seulement ceux crees par OmniSync ou utilisez la future commande de nettoyage.
