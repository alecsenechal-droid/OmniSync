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

### 🔲 À faire — Beta

- [ ] **Beta testeur Ste-Foy ou Garneau** — PRIORITÉ SUIVANTE
  - Valide onboarding < 2 min + logs `[csfoy]` ou `[cegepgarneau]` en conditions réelles
  - Observer les frictions, documenter les sélecteurs qui diffèrent

- [ ] **PyInstaller .exe** — 0 Python requis pour l'utilisateur

- [ ] **Token Moodle : surveiller expiration**
  - Procédure : Edge F12 → Network → launch.php → `run.bat token-moodle`

---

### 🔲 À faire — UX / Cleanup

- [ ] **Reformulation log SSO Limoilou** : `SSO OK (format lk=, C= absent)` au lieu de `WARN mismatch`
  - Petit fix cosmétique dans `_navigate_to_lea_via_sso` + `_ensure_estd`

- [ ] Supprimer fichiers debug :
  `test_rebrowser.py`, `fix_config.py`, `save_token.py`,
  `test_cookie_moodle.py`, `test_extract_cookies.py`, `test_sqlitelock.py`

---

### ⏸ En attente (pas avant automne 2026)

- [ ] MIO messages profs — iframes complexes, hors scope actuel
- [ ] `remind-classes` pour calendriers existants — si demandé par beta testeurs

---

### ❌ Hors scope (jamais)

IA, résumés, frontend, notifications push, multi-users, cloud, mémoire long terme.
