# Prompt Phase 2 — Cartographie Omnivox (compléments pour OmniSync)

**Quand l’utiliser :** après le premier audit (`Audit Technique pour OmniSync.md`), une fois connecté sur https://climoilou.omnivox.ca/intr/

**Objectif :** combler les trous restants pour que le développeur OmniSync n’ait plus à deviner URLs, iframes, formats de date ni chemins vers les PDF.

---

## Prompt à copier-coller dans Claude in Chrome / Manus

```
Tu es auditeur technique pour OmniSync (sync locale Omnivox → Google Calendar, Playwright, Cégep Limoilou climoilou).

Le premier audit a déjà couvert : ListeTravauxEtu, calendrier clre, examens hrex, notes, actualités, documents ddle.

Cette session Phase 2 doit clarifier ce qui MANQUE encore. Ne clique sur rien destructif. Explore et documente.

### A. Vérifications sur le premier audit (confirmer ou corriger)

1. **ListeTravauxEtu** : depuis SommaireTravauxEtu (dtrv ET trav si les deux existent), liste TOUS les liens vers ListeTravauxEtu.aspx. Pour UN cours, copie le HTML réel de 2 lignes `tr.ligneTravail` (anonymisé). Confirme le sélecteur exact si différent de `table.tblListeTravaux tr.ligneTravail`.

2. **Calendrier Léa** : ouvre `clre/Default.aspx?cal=somm`. Le calendrier utilise-t-il `div.evenement`, un tableau `td`, ou les deux? Donne le HTML réel d’1 événement avec date/heure/cours. Comment changer de mois (boutons, postback)?

3. **Examens finaux** : sur `hrex/Examen.ovx`, sélecteur réel des blocs (classes CSS exactes). Comment changer la session (`ddlSession`)? HTML d’1 examen complet.

### B. Modules pas encore exploités par OmniSync (P1 restants)

4. **Menu intranet « Évènements »** (pas seulement Léa clre) : chemin menu, URL, structure liste, format date, lien avec annulations.

5. **Horaire / grille horaire** (ESTD ou intranet) : où voir cours récurrents (lun-ven), sélecteurs, format heure/local/prof. Est-ce la même source que le calendrier Léa?

6. **MIO** : structure liste messages (Reçus), y a-t-il des dates d’échéance ou seulement informatif? Sélecteurs pour titre, date, expéditeur, catégorie. Utile pour OmniSync calendrier? (oui/non + pourquoi)

7. **Communiqués / Activité dans mes classes** : contient-il des dates de remise ou changements? URL + 1 exemple.

### C. Documents et dates cachées (critique)

8. **ListeDocuments.aspx** : pour 1 cours, HTML de `tr.ligneDocument` avec `descriptionDocument` contenant « Avoir lu … d’ici au … ». Sélecteurs pour date distribution vs date lecture obligatoire.

9. **Énoncé d’un travail (PDF)** : depuis ListeTravauxEtu, ouvre UN travail (PDF ou page énoncé). La date est-elle:
   - uniquement sur la liste?
   - dans le PDF (texte extractible)?
   - sur une page intermédiaire avant le PDF?
   Décris le flux de clics et l’URL de chaque étape.

10. **PowerPoint / Word** : même question si un prof met un .pptx au lieu d’un PDF.

### D. Cas limites Omnivox

11. **Travaux sans date** : sur ListeTravauxEtu, existe-t-il des lignes avec colonne date vide ou « - »? Que dit la fiche détail?

12. **Évaluations / examens intra** : sont-ils seulement dans travaux, calendrier, ou aussi dans Notes d’évaluation?

13. **Annulations / reports** : où apparaissent-ils (Actualités, MIO, bandeau intranet, courriel)? Exemple de libellé.

14. **MFA** : après login, combien de temps la session reste active sans re-MFA? (observation qualitative)

### E. Paramètres URL à capturer dynamiquement

Pour chaque type de lien (ListeTravaux, ListeDocuments, ListeEval), liste les query params OBLIGATOIRES:
- Ref, SID, Info, NoCours, NoGroupe, C, E, L
Lesquels changent à chaque session? Lesquels sont stables par cours?

### F. Livrables OBLIGATOIRES (format strict)

#### 1. Tableau des écarts vs audit Phase 1
| Module | Audit Phase 1 correct? | Correction si non |
|--------|------------------------|-------------------|

#### 2. Fichier JSON machine-readable (dans un bloc ```json)
```json
{
  "cegep": "climoilou",
  "modules": [
    {
      "id": "liste_travaux",
      "entry_urls": ["..."],
      "list_selector": "...",
      "fields": {
        "title": "...",
        "due_date": "...",
        "due_time": "...",
        "course_code": "..."
      },
      "date_formats": ["28-fév-2026 à 12:00"],
      "pagination": null,
      "notes": ""
    }
  ]
}
```

#### 3. Checklist « prêt pour automatisation 5h du matin »
- [ ] Toutes les dates remises ont une source HTML sans ouvrir PDF
- [ ] Calendrier mois courant + mois suivant accessibles
- [ ] Examens session courante sélectionnée par défaut
- [ ] Pas d’iframe bloquante sans sélecteur
- [ ] Liste des sélecteurs testés dans DevTools (F12)

#### 4. Top 5 risques si OmniSync scrape sans humain
(numéroté, concret)

#### 5. Ce qu’il ne faut PAS scraper (hors scope calendrier étudiant)

Sois exhaustif sur les sélecteurs CSS réels observés, pas des suppositions.
```

---

## Pourquoi ce prompt complète le premier

| Sujet | Audit 1 | Phase 2 |
|-------|---------|---------|
| Liste travaux par cours | Oui (théorique) | HTML réel + params URL |
| Calendrier div vs table | Partiel | Confirmation + navigation mois |
| PDF / dates dans fichiers | Mentionné | Flux clic par clic |
| Évènements intranet | Non | Oui |
| Horaire récurrent | Non | Oui |
| MIO utile ou non | Non | Décision claire |
| Annulations | Partiel (actualités) | Toutes les sources |
| JSON pour le dev | Non | Oui |

---

## Après la réponse Manus

Enregistre le fichier exporté dans :

`docs/AUDIT_TECHNIQUE_OMNIVOX_PHASE2.md`

ou colle le JSON dans le chat du développeur OmniSync.
