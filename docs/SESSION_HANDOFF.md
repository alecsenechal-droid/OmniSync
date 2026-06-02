# Session Handoff — OmniSync
## 2026-06-02 (Repo GitHub public + Google Cloud OmniSync + Beta prep)

---

## État pipeline

**Omnivox** : stable — DA=2534700, mot de passe keyring OS, headless=true.
**Google Calendar** : stable — calendrier "OmniSync" en production.
**Moodle** : TOKEN VALIDE — 19 travaux au dernier run.
**Notifications** : actives — `omnisyncqc@gmail.com` → `alec.senechal@gmail.com`.
**Doctor** : 15/15 PASS ✅
**run --scrape-only** : PASS — 82 events Omnivox + 19 Moodle, `[OK] Aucune anomalie` ✅
**Git repo** : pushé sur `https://github.com/alecsenechal-droid/OmniSync` (public) — commit `c7e533f`

---

## Ce qui a été livré

### 1. Repo GitHub public en ligne (commit c7e533f)
- `.gitignore` mis à jour : CLAUDE.md exclu (données personnelles)
- `README-CREDENTIALS.md` : instructions distribution `credentials.json` via Releases
- `omnivox_auth.py` : fix SSO log Limoilou (WARN mismatch → `SSO OK (format lk=, C= absent)`)
- `tests/` : test_adapter, test_config, test_models intégrés
- `omnisync.spec` : spec PyInstaller pour build .exe futur
- Checklist sécurité GitHub validée 6/6 : secrets exclus, .gitignore, README, LICENSE MIT, auth, commits clairs

### 2. Projet Google Cloud OmniSync (manuel)
- Projet créé : `OmniSync` (compte `alec.senechal@gmail.com`)
- API Google Calendar activée
- Écran de consentement OAuth : type Externe, application publiée (évite écran "non vérifiée")
- ID client OAuth créé : Application de bureau "OmniSync Desktop"
- **BLOQUANT** : `credentials.json` pas encore téléchargé depuis la console

### 3. Fix URL install.bat
- `install.bat` ligne 37 : `alec-senechal/omnisync` → `alecsenechal-droid/OmniSync` (URL GitHub Releases)
- Corrige le téléchargement automatique de `credentials.json` lors de l'install

---

## Décisions prises

| Type | Décision | Raison |
|------|----------|--------|
| Infrastructure | Repo sous `alecsenechal-droid` (pas `alecsenechal`) | Compte GitHub actif |
| Sécurité | `CLAUDE.md` dans `.gitignore` | Contient email + instructions privées Claude Code |
| Distribution | `credentials.json` via GitHub Releases uniquement | ToS Google — jamais dans le repo |
| Beta | OAuth consent publié (pas en test) | Évite l'écran "Application non vérifiée" chez les testeurs |

---

## Ce qui a été livré (session 2026-06-02 #3)

### 4. Landing déployée en production
- `vercel --prod` PASS — `https://landing-v3-blush.vercel.app`

### 5. Analyse 9 agents — plan onboarding beta unifié
- **Friction #1** : Python absent (~60% machines) → winget auto-install dans setup.bat à coder
- **Friction #2** : Git absent (~40%) → ZIP téléchargeable comme alternative
- **Scope OAuth** : garder `calendar` complet confirmé — `calendars.insert` requiert scope complet
- **Wizard redesign** : design 5 étapes numérotées, helpers `step_header/ask/validate_da` identifiés
- **Beta strategy** : 2 testeurs directs live Discord (pas onboarding autonome) — valider sélecteurs avant UX

---

## Décisions prises (session #3)

| Type | Décision | Raison |
|------|----------|--------|
| Technique | Scope OAuth `calendar` complet confirmé | `calendars.insert` requiert scope complet — `calendar.events` insuffisant |
| Technique | winget Python auto-install dans setup.bat | Friction #1 identifiée par agent UX — ~60% sans Python |
| Marché | Beta live Discord (pas onboarding autonome) | Agent sense-check : valider sélecteurs > polir UX |
| Marché | Profil beta : Sciences humaines / Techniques admin (pas TI) | Représentatif de la vraie cible utilisateur |

---

## Message WhatsApp beta testeur (prêt à envoyer)

> Hey, je teste un outil qui sync ton Omnivox (cours, travaux, examens) dans Google Calendar automatiquement. J'ai besoin d'une personne de [Ste-Foy / Garneau] pour valider que ça marche là-bas. Ça prend 15 min avec moi en live sur Discord. T'as juste besoin d'un ordi Windows. Intéressé(e) ?

---

## Ce qui N'est PAS fait

- [ ] **Télécharger credentials.json** depuis console Google Cloud → OmniSync Desktop → ⬇ — **PRIORITÉ IMMÉDIATE**
- [ ] **Créer GitHub Release v1.0-beta** avec credentials.json attaché
- [ ] **setup.bat winget Python auto-install** — si Python absent → `winget install Python.Python.3.12`
- [ ] **Wizard redesign** — design exact prêt (5 étapes numérotées, helpers), code pas encore écrit
- [ ] **Recruter 2 beta testeurs** — 1 Ste-Foy, 1 Garneau (message ci-dessus)
- [ ] **Valider cours récurrents en prod** — début août
- [ ] **Valider écriture Calendar automne 2026** — dès session automne
- [ ] **ESTD examens finaux** — retester en août
- [ ] **Token Moodle : surveiller expiration** — `run.bat token-moodle`
- [ ] **WorkflowDemo.tsx landing** — `[REMISE]`/`[EXAM]` non alignés avec `Remise:`/`Exam:`
- [ ] **DEVLOG.md landing** — Moodle marqué ❌ (faux), préfixes avec crochets (faux)

---

## Risques actifs

1. **credentials.json non distribué** — bloquant pour tout beta testeur. Résolution : 5 min sur console Google Cloud.
2. **Token Moodle** : expiration silencieuse → `run.bat token-moodle`.
3. **Sélecteurs csfoy/cegepgarneau** : non testés en production — comportement inconnu.

---

## Prochaine étape (1 seule)

**Télécharger le credentials.json du projet OmniSync et créer la GitHub Release.**

```powershell
# Après téléchargement dans Downloads :
# 1. Aller sur https://github.com/alecsenechal-droid/OmniSync/releases/new
# 2. Tag : v1.0-beta
# 3. Titre : "OmniSync v1.0 Beta"
# 4. Attacher credentials.json
# 5. Publier
```
