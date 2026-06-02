# TODO — OmniSync
## Priorité : BETA PUBLIQUE (dans l'ordre)

### ✅ Complété

- [x] **Pipeline core** — Omnivox + Moodle + Google Calendar fonctionnel (2026-06-01)
- [x] **Notifications email** — Gmail SMTP, App Password keyring, 3 triggers (2026-06-01)
- [x] **Multi-cégep architecture** — load_config() dynamique, KNOWN_CEGEPS (2026-06-01)
- [x] **Cégeps supportés** — Limoilou (CLI), Sainte-Foy (SFO), Garneau (FXG)
- [x] **Calendar write validé** — 97 events créés via --include-past (2026-06-01)
- [x] **UX Calendar V2** (2026-06-01) — calendrier dédié, titres propres, RRULE cours, couleurs, reminders
- [x] **Bugfixes post V2** (2026-06-01) — calendar_id auto, filtre actualités, pipeline cours récurrents câblé
- [x] **Onboarding V2** (2026-06-01)
- [x] **UX Terminal Dashboard** (2026-06-01)
- [x] **QA session** (2026-06-01) — 3 bugs corrigés, 5 commandes testées PASS
- [x] **Fixes onboarding + stabilité** (2026-06-01) — isatty(), wizard loop, session_expired WARN
- [x] **Refactoring God File** (2026-06-01) — omnivox_engine.py 4388→86L, 11 modules extraits
- [x] **Robustesse multi-cégep** (2026-06-01) :
  - SSO validation `[{slug}]` dans `_navigate_to_lea_via_sso` + `_ensure_estd`
  - Doctor 15/15 : check slug KNOWN_CEGEPS, institution_code, moodle_url
  - Logs scraper préfixés par `[{slug}]` — 179 appels, 31 lignes `[climoilou]` en --verbose
- [x] **Audit documentaire OmniSync** (2026-06-02) — scraping, sync, multi-cégep, install documentés
- [x] **Analyse Google OAuth** (2026-06-02) — 3 options : 2A viable, 2B script PS, 2C impossible
- [x] **Repo GitHub public** (2026-06-02) — commit `c7e533f` pushé sur `alecsenechal-droid/OmniSync`
- [x] **Reformulation log SSO Limoilou** (2026-06-02) — `SSO OK (format lk=, C= absent)` au lieu de WARN
- [x] **README-CREDENTIALS.md** (2026-06-02) — instructions distribution beta
- [x] **Fichiers debug** — absents du repo (exclus par .gitignore)
- [x] **Projet Google Cloud OmniSync** (2026-06-02) — créé, API Calendar activée, OAuth consent publié, client Desktop créé
- [x] **install.bat auto-download credentials.json** (2026-06-02) — Invoke-WebRequest depuis GitHub Releases
- [x] **Landing déployée** (2026-06-02) — `https://landing-v3-blush.vercel.app`
- [x] **Analyse onboarding 9 agents** (2026-06-02) — plan beta unifié : winget Python, wizard redesign, beta strategy

---

### 🔲 À faire — IMMÉDIAT (débloque le testeur)

- [ ] **Télécharger credentials.json** — console.cloud.google.com/apis/credentials → OmniSync Desktop → ⬇ — **BLOQUANT**
- [ ] **Créer GitHub Release v1.0-beta** — attacher credentials.json, tag v1.0-beta, publier
- [ ] **setup.bat winget Python auto-install** — si Python absent → `winget install Python.Python.3.12`
- [ ] **Wizard redesign 5 étapes** — design exact prêt (numérotées, `step_header/ask/validate_da`), code pas encore écrit
- [ ] **Recruter 2 beta testeurs** — 1 Ste-Foy, 1 Garneau — message WhatsApp prêt dans SESSION_HANDOFF.md

---

### 🔲 À faire — Beta

- [ ] **Beta testeur Ste-Foy ou Garneau** — PRIORITÉ SUIVANTE (dès credentials distribués)
  - Valide onboarding < 2 min + logs `[csfoy]` ou `[cegepgarneau]` en conditions réelles
  - Observer les frictions, documenter les sélecteurs qui diffèrent

- [ ] **PyInstaller .exe** — 0 Python requis pour l'utilisateur (spec omnisync.spec déjà prêt)

- [ ] **Token Moodle : surveiller expiration**
  - Procédure : Edge F12 → Network → launch.php → `run.bat token-moodle`

---

### 🔲 À faire — Automne 2026 (priorité critique)

- [ ] **Valider cours récurrents en prod** — PRIORITÉ 1
  - Début août, `run.bat run --calendar-dry-run` → vérifier [HORAIRE] retourne des cours
  - Puis `run.bat run` → vérifier dans Google Calendar :
    - Cours apparaissent comme récurrents (RRULE) — couleur Blueberry
    - Créneaux horaires corrects (lundi 8h30, mercredi 8h30, etc.)

- [ ] **Valider écriture Calendar automne 2026**
  - Dès que la session commence, relancer `run.bat run`

- [ ] **ESTD examens finaux** — redirect normale fin session, retester en août

---

### 🔲 À faire — Landing / UX

- [ ] **WorkflowDemo.tsx** — aligner `[REMISE]`/`[EXAM]` sur `Remise:`/`Exam:` dans les CAL_EVENTS
- [ ] **DEVLOG.md landing** — corriger "Moodle ❌" (faux) et préfixes avec crochets (faux)
- [ ] **Déployer landing corrigée** — `cd C:\Users\alecs\Desktop\study-agent\landing-v3 && vercel deploy --prod`

---

### ⏸ En attente (pas avant automne 2026)

- [ ] MIO messages profs — iframes complexes, hors scope actuel
- [ ] `remind-classes` pour calendriers existants — si demandé par beta testeurs

---

### ❌ Hors scope (jamais)

IA, résumés, frontend, notifications push, multi-users, cloud, mémoire long terme.
