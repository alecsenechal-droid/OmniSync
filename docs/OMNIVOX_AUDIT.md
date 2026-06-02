# Audit Technique Omnivox (OmniSync)

Généré par Manus AI — session Hiver 2026, instance Cégep Limoilou.
Complété et précisé par audit Phase 2.1.

---

## Module : Examens Finaux (`Examen.ovx`)

- **URL** : `https://climoilou-estd.omnivox.ca/estd/hrex/Examen.ovx`
- **SSO** : via Skytech ESTD depuis l'intranet
- **Select session** : `id="ctl00_cntFormulaire_ddlSession"` (ou `[id*='ddlSession']`)
  - Valeurs : `20261` = Hiver 2026, `20253` = Automne 2025 (format `AAAA + index`)
  - Texte visible : "Hiver 2026"
- **Structure DOM** : tables imbriquées sans ID ni classe stable (`table > tbody > tr > td`)
  - Date (header) : dans un `<b>` — ex. `<b>Mardi 26 mai 2026</b>`
  - Chaque examen : un `<tr>` avec 2 `<td>`
    - td[0] : `08:00 à 11:00<br>Local LIM - Q2195`
    - td[1] : `Méthodes et processus de travail<br>Cours: 235-215-LI  gr. 00001<br>Enseignant: Bédard, Rémy`
- **Stratégie** : parse textuel ligne par ligne (inner_text) — fonctionne malgré l'HTML ancien

---

## Module : Travaux (`ListeTravauxEtu.aspx`)

- **URL directe** : `https://climoilou-lea.omnivox.ca/cvir/dtrv/ListeTravauxEtu.aspx?NoCours=[CODE]&NoGroupe=[GR]`
- **Table** : `table#tabListeTravEtu`
- **Lignes** : `tr.LigneListTrav1`, `tr.LigneListTrav2`, `tr.LigneListTrav1Last`, `tr.LigneListTrav2Last`
- **Colonnes** :
  - td index 1 : titre du travail
  - td index 2 : date (`28-fév-2026 à 12:00via Léa` — "via Léa" est collé, strip par regex)
- **Date absente** : cellule vide, `&nbsp;`, ou "Non définie"
- **Accueil LEA** : les liens vers `ListeTravauxEtu` ne sont PAS des `<a>` mais des `<div onclick>` dans les cartes de cours. L'onclick contient `Service.aspx?...NoCours=...&NoGroupe=...` — extraire NoCours+NoGroupe par regex depuis l'attribut onclick.

---

## Module : Calendrier LÉA (`clre/Default.aspx?cal=somm`)

- **Sélecteur événement** : `div.evenement`
  - `.dateEvenement` : `ven 1er mai` (format `Jour JJer mois`)
  - `.titreEvenement` : titre
  - `.typeEvenement` : "Travail à remettre", "Évaluation", etc.
  - `.coursEvenement` : `Classe: 235-215-LI gr. 00001`
  - `.heureEvenement` : `18:00`
  - `.ponderationEvenement` : `Pondération 0%`

---

## Module : Actualités

- **Sélecteur** : `a.carte-portail.carte-actualite`
- **Date** : dans `.carte-portail-desc`, après `i.material-icons.date-card-icon` — format `JJ mois AAAA`

---

## Module : Documents distribués (`ListeDocuments.aspx`)

- **Sélecteur ligne** : `tr.ligneDocument`
- **Date distribution** : `span.dateDistribution` — format `JJ mois AAAA`
- **Deadline lecture** : dans `div.descriptionDocument` — texte libre ex. "Avoir lu ce document d'ici au jeudi le 29 janvier"

---

## Top 5 risques scraping automatisé

1. **Déconnexion navigation directe** : accéder à une URL ESTD depuis session LÉA sans SSO → `isLogout=1`. Toujours passer par `_ensure_lea()` / `_ensure_estd()`.
2. **Paramètres `Ref` et `SID` expirables** : URLs stockées = inutilisables après quelques minutes. Toujours extraire dynamiquement.
3. **Format date localisé** : `fév`, `août` — le parser `_parse_colonne_date_lea()` gère déjà ça via `MOIS_ABBR_MAP`.
4. **Texte collé** : `12:00via Léa` — strip par `re.sub(r'via\s+\S+', '', ...)` avant parsing.
5. **Structure ESTD ancienne** : HTML Layout 2000, pas de classes stables — le parse textuel est plus fiable que les sélecteurs CSS.

---

## Hors scope OmniSync

- MIO : iframes imbriquées, hors scope calendrier
- Forum de classe : AJAX lourd, aucune valeur calendrier
- Documents de cours : volume excessif, scraper uniquement les énoncés via module Travaux
- Centre de paiement : risque sécurité, hors scope
