# Security Policy

OmniSync manipule des donnees sensibles: identifiants Omnivox, tokens Google, horaires, notes, messages et documents scolaires. Le projet est concu pour fonctionner localement, sans serveur central.

## Versions supportees

Pendant le MVP, seule la derniere version publiee recoit des correctifs de securite.

## Signaler une faille

N'ouvrez pas d'issue publique contenant:

- mot de passe;
- token Google;
- captures d'ecran Omnivox;
- base SQLite;
- messages MIO;
- documents ou notes scolaires.

Utilisez un canal prive du mainteneur du projet.

## Donnees sensibles

Sont considerees sensibles:

- DA / matricule;
- mot de passe Omnivox;
- cookies et sessions navigateur;
- `token.json` Google;
- `credentials.json` OAuth;
- base SQLite OmniSync;
- logs et captures de debug;
- documents, messages, notes et horaires.

## Stockage recommande

- Mot de passe Omnivox: Windows Credential Manager via `keyring`.
- Token Google: dossier local utilisateur, idealement protege par l'OS.
- Base SQLite: `%LOCALAPPDATA%\OmniSync\omnivox.db`.
- Profil navigateur: `%LOCALAPPDATA%\OmniSync\browser_profile\`.

## Politique de logs

Les logs ne doivent pas contenir:

- mots de passe;
- tokens;
- cookies;
- HTML complet Omnivox;
- corps complet de messages MIO;
- donnees scolaires detaillees inutiles.

Ils doivent contenir seulement les statuts, compteurs, dates, modules et erreurs resumees.

## Google Calendar

OmniSync utilise l'API Google Calendar avec OAuth. L'utilisateur peut revoquer l'acces depuis son compte Google a tout moment. Les evenements crees par OmniSync doivent porter des proprietes privees permettant de les identifier sans toucher aux evenements personnels de l'utilisateur.

## Scraping Omnivox

OmniSync est un projet non officiel. L'utilisateur est responsable de respecter les politiques de son etablissement et les conditions d'utilisation des services utilises. La synchronisation doit rester raisonnable: une fois par jour par defaut.

## Incident: secret publie accidentellement

1. Revoquer le token Google.
2. Changer le mot de passe Omnivox.
3. Supprimer le secret du depot.
4. Reecrire l'historique Git si le secret a ete commite.
5. Regenerer les credentials concernes.
