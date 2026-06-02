# Session Handoff — OmniSync
## 2026-06-02 (Publication GitHub + Corrections Landing)

---

## État pipeline

**Omnivox** : stable — DA=2534700, mot de passe keyring OS, headless=true.
**Google Calendar** : stable — calendrier "OmniSync" en production.
**Moodle** : TOKEN VALIDE — 19 travaux au dernier run.
**Notifications** : actives — `omnisyncqc@gmail.com` → `alec.senechal@gmail.com`.
**Doctor** : 15/15 PASS ✅
**run --scrape-only** : PASS — 82 events Omnivox + 19 Moodle, `[OK] Aucune anomalie` ✅
**Git repo** : commit `a44f243` local, remote configuré, push en attente (repo GitHub à créer)

---

## Ce qui a été livré

### 1. Audit documentaire complet OmniSync
- Scraping : 9 pages visitées, 10 modules, données récupérées vs ignorées documentées
- Sync Calendar : CRUD, RRULE, rappels, couleurs, déduplication documentés
- Multi-cégep : 3 cégeps dans KNOWN_CEGEPS, 1 seul testé (Limoilou)
- Installation : flux réel documenté, blocage #1 identifié (credentials.json Google, 20-40 min)

### 2. Analyse Google OAuth — 3 options (agents parallèles)
- **Option 2A** (app centralisée) : viable pour 20 users, limite 100 sans vérification, `credentials.json` JAMAIS dans le repo (violation ToS)
- **Option 2B** (script PowerShell `setup_google.ps1`) : guide étape par étape, ouvre deep-links console.cloud.google.com, vérifie présence fichier
- **Option 2C** (auto-provision) : **IMPOSSIBLE** — API IAP de création OAuth Client ID dépréciée depuis janvier 2024
- **Décision** : approche 2A+2B hybrid — credentials.json Alec via GitHub Releases + script pour power users

### 3. Repo GitHub préparé (commit a44f243)
- `.gitignore` corrigé : `step*.png`, `v2_*.png`, `after_signin.png` ajoutés (DA visible dans screenshots)
- Nouveau repo git dans `C:\Users\alecs\Desktop\Omnisync` (l'ancien root était le home dir `C:\Users\alecs` — paths incorrects)
- Commit : 61 fichiers, 10 073 insertions, remote `https://github.com/alecsenechal/omnisync.git`
- **BLOQUANT** : repo GitHub pas encore créé → push échoue avec "Repository not found"

### 4. Landing page — 5 corrections bloquantes appliquées
Fichiers modifiés dans `C:\Users\alecs\Desktop\study-agent\landing-v3` :

| Fichier | Correction |
|---------|-----------|
| `app/page.tsx` | HOW IT WORKS : 3 étapes → 4 (étape Google ajoutée en position 1) |
| `app/page.tsx` | "dans ton Google Calendar existant" → "dans un calendrier dédié « OmniSync »" |
| `app/page.tsx` | "Cours annulés barrés automatiquement" supprimé (fonctionnalité inexistante) |
| `app/page.tsx` | FAQ cégeps : "V2" → "Ste-Foy et Garneau déjà dans le code, jamais testés" |
| `components/TerminalDemo.tsx` | Ajout Chromium ~170 MB + prompts wizard interactif (DA, cégep, credentials.json) |
| `components/CalendarDemo.tsx` | `[REMISE]` → `Remise:`, `[EXAM]` → `Exam:` |

---

## Décisions prises

| Type | Décision | Raison |
|------|----------|--------|
| Infrastructure | Nouveau repo git initialisé dans `Omnisync/` | Home dir (`C:\Users\alecs`) était le vrai root git — paths auraient été `Desktop/Omnisync/src/` sur GitHub |
| Sécurité | `credentials.json` via GitHub Releases uniquement | ToS Google — jamais dans le repo public ; GitHub Secret Scanning révoque automatiquement |
| Produit | Google OAuth : 2A+2B hybrid | 2C impossible (API dépréciée) ; 2B seul = friction identique ; 2A seul = fragilité (1 suspension = tous bloqués) |
| Landing | 4 étapes HOW IT WORKS (Google obligatoire en étape 1) | Blocage invisible — testeur plantait à mi-setup.bat sans explication |

---

## Ce qui a été livré (session 2026-06-02 #2)

### 5. Fix log SSO Limoilou
- `omnivox_auth.py` : WARN SSO mismatch → `SSO OK (format lk=, C= absent)` pour les cégeps qui utilisent `lk=` au lieu de `C=CLI`
- Appliqué dans `_navigate_to_lea_via_sso` + `_ensure_estd`

### 6. Fix test_adapter.py
- `scrape_omnivox(dry_run=True)` retourne `(list, None, None)` — test déstructurait mal le tuple
- 3/3 tests PASS

---

## Ce qui N'est PAS fait

- [ ] **Créer repo GitHub** — aller sur github.com → New repository `alecsenechal/omnisync` (public, vide), puis `git push -u origin main` — **PRIORITÉ IMMÉDIATE**
- [ ] **Distribuer credentials.json** — créer une GitHub Release avec le fichier (pas dans le repo)
- [ ] **Déployer landing corrigée** — `cd C:\Users\alecs\Desktop\study-agent\landing-v3 && vercel deploy --prod`
- [ ] **WorkflowDemo.tsx** — `[REMISE]`/`[EXAM]` non corrigés dans les CAL_EVENTS (hors scope demandé)
- [ ] **DEVLOG.md landing** — corriger les erreurs : Moodle marqué ❌ (faux), préfixes avec crochets (faux)
- [ ] **setup_google.ps1** — script conçu par Agent 2B, pas encore intégré dans le repo
- [ ] **Cours récurrents en production** — valider en août
- [ ] **Beta testeur Ste-Foy ou Garneau** — priorité dès repo public
- [ ] **Token Moodle : surveiller expiration**

---

## Risques actifs

1. **Repo GitHub inexistant** — bloquant pour tout testeur. Résolution : 2 min.
2. **credentials.json non distribué** — bloquant même avec le repo. Résolution : GitHub Releases.
3. **Token Moodle** : expiration silencieuse → `run.bat token-moodle`.
4. **Sélecteurs csfoy/cegepgarneau** : non testés en production.

---

## Prochaine étape (1 seule)

**Créer le repo GitHub puis pousser.**

1. Aller sur github.com → New repository
   - Nom : `omnisync`, Compte : `alecsenechal`
   - Visibilité : **Public** — sans README ni .gitignore (déjà locaux)
2. Lancer :
```powershell
cd C:\Users\alecs\Desktop\Omnisync
git push -u origin main
```
