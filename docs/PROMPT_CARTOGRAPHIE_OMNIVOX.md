# Prompt Claude in Chrome — cartographie Omnivox pour OmniSync

Copie-colle ce bloc dans Claude (extension Chrome) **pendant que tu es connecté** sur https://climoilou.omnivox.ca/intr/

---

## Prompt

Tu es un auditeur technique pour le projet open source **OmniSync** (sync Omnivox → Google Calendar, local, Playwright).

**Ne clique sur rien de destructif.** Explore seulement. Pour chaque module ci-dessous, fournis une fiche structurée.

### Modules à cartographier (priorité calendrier / dates)

1. **Travaux – Énoncé et remise** (Léa)
2. **Calendrier / Évènements** (Léa `clre` ou menu intranet « Évènements »)
3. **Examens finaux** (ESTD `hrex/Examen.ovx`)
4. **Notes d'évaluation** (dates d'examens dans le libellé?)
5. **Actualités** (reports, annulations)
6. **Documents distribués / Énoncés distribués** (date dans titre ou page?)

### Format de sortie OBLIGATOIRE (Markdown, une section par module)

```markdown
## MODULE: <nom exact menu Omnivox>

### Accès
- Menu: chemin clic (ex: Accueil intranet → lien texte « LÉA » → …)
- URL finale stable (sans SID/Ref si possible, sinon indiquer paramètres variables)
- SSO: oui/non, domaine (`climoilou-lea`, `climoilou-estd`, etc.)

### Liste des éléments
- Sélecteur CSS ou XPath de **chaque ligne** (tr, div, li)
- Champs par ligne: titre, code cours, date, heure, local, pondération, type (travail/examen)
- Exemple HTML **anonymisé** d'une ligne (retire noms perso)

### Dates
- Où la date apparaît sur la **liste** (attribut, colonne, texte)
- Si date absente sur la liste: URL de la **fiche détail** + sélecteur date sur la fiche
- Format date affiché (ex: « 26 mai 2026 », « 2026-05-26 »)

### Pagination / filtres
- Session / trimestre à sélectionner?
- Postback ASP.NET (`__VIEWSTATE`)?

### Pièges
- Redirections, iframes, nouvel onglet
- Contenu chargé en AJAX (attendre quel élément?)

### Priorité OmniSync
- P1 calendrier / P2 info / P3 ignorer
```

### Livrable final

Tableau récap:

| Module | URL pattern | Date sur liste? | Fiche détail? | Sélecteur ligne |
|--------|-------------|-----------------|---------------|-----------------|

Puis liste des **3 corrections** les plus utiles pour récupérer les 14 travaux sans date sur SommaireTravauxEtu.

---
