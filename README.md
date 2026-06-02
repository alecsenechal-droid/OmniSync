# OmniSync

OmniSync synchronise automatiquement les remises, examens et evenements Omnivox vers Google Calendar, localement sur l'ordinateur de l'etudiant.

> Projet independant, non affilie a Omnivox, Skytech, Google ou un cegep.

## Ce que fait OmniSync

- Se connecte a Omnivox avec les identifiants de l'etudiant.
- Recupere les remises, examens et evenements publies dans Omnivox LÉA.
- Synchronise aussi les remises Moodle (optionnel, cegeps Decclic supportes).
- Stocke un historique local dans SQLite pour eviter les doublons.
- Cree ou met a jour les evenements dans Google Calendar.
- Peut etre planifie chaque matin a 05:00 sur Windows.

## Perimetre

- Windows en priorite.
- Cegep Limoilou teste en premier — autres cegeps Omnivox devraient fonctionner.
- Remises, examens et evenements scolaires (Omnivox + Moodle).
- Google Calendar.
- Donnees locales, aucun serveur central.

Fonctionnalites hors perimetre actuel: Obsidian, IA, chatbot, app mobile.

## Installation Windows

**Assistant complet (recommande pour tester comme un utilisateur):**

```powershell
setup.bat
```

**Installation manuelle:**

```powershell
git clone https://github.com/votre-utilisateur/omnisync.git
cd omnisync
install.bat
run.bat init
```

Verifier l'environnement:

```powershell
run.bat doctor
```

Lancer une synchronisation manuelle:

```powershell
run.bat run --calendar-dry-run
```

Planifier tous les jours a 05:00:

```powershell
run.bat scheduler install --time 05:00
```

## Donnees locales

OmniSync stocke ses donnees runtime dans:

```text
%LOCALAPPDATA%\OmniSync\
```

Ce dossier peut contenir la configuration locale, la base SQLite, les logs, le profil navigateur et le token Google. Il ne doit jamais etre publie.

## Securite

Ne publiez jamais:

- votre DA / matricule;
- votre mot de passe Omnivox;
- `token.json` Google;
- `credentials.json` personnel;
- le profil navigateur;
- la base SQLite;
- les logs ou captures de debug.

Voir [SECURITY.md](SECURITY.md).

Guide etudiant pas a pas : [docs/UTILISATEUR.md](docs/UTILISATEUR.md).

## Limites connues

OmniSync repose sur Omnivox, qui n'a pas d'API publique officielle pour ce cas d'usage. Le scraping peut casser si l'interface change. Verifiez toujours vos dates importantes dans Omnivox.

## Etat actuel du MVP

Le repo contient maintenant:

- une CLI fonctionnelle;
- un mode demo `run.bat run --dry-run`;
- un mode de test reel `run.bat run --calendar-dry-run`;
- le moteur Omnivox integre (Playwright, LEA travaux/calendrier, examens finaux);
- le moteur Moodle integre (REST API, SSO Azure AD, token persistant);
- une sync Google Calendar implementee, avec dry-run securitaire;
- `run.bat auth-google` pour connecter Google Calendar;
- `run.bat init-moodle` pour connecter Moodle (une seule fois, MFA inclus).

Par defaut, les evenements passes et les evenements sans date ne sont pas envoyes dans Google Calendar.

## Roadmap courte

1. Stabiliser le CLI public.
2. Porter le scraper Omnivox actuel dans `src/omnisync/scraper/`.
3. Ajouter la synchronisation Google Calendar complete.
4. Tester l'installation sur une machine Windows propre.
5. Publier une release `.zip` ou `.exe`.
