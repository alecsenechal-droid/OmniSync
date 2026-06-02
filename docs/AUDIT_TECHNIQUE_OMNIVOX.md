# Audit Technique pour OmniSync

**Auteur**: Manus AI

Ce document présente un audit technique détaillé des modules Omnivox pertinents pour le projet open source **OmniSync**. L'objectif est de cartographier la structure technique de chaque module, incluant les chemins d'accès, les URLs, les sélecteurs CSS/XPath, les formats de dates, les mécanismes de pagination/filtrage, les pièges potentiels et la priorité pour OmniSync.

---

## MODULE: Travaux – Énoncé et remise (Léa)

### Accès
- Menu: Accueil intranet → Léa → Mes classes → [Nom du cours] → Travaux
- URL finale stable: `https://climoilou-lea.omnivox.ca/cvir/dtrv/ListeTravauxEtu.aspx?C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}&NoCours={COURSE_ID}&NoGroupe={GROUP_ID}`
- SSO: oui, domaine `climoilou-lea`

### Liste des éléments
- Sélecteur CSS ou XPath de **chaque ligne**: `table.tblListeTravaux tr` (pour les lignes de travaux individuels)
- Champs par ligne: titre du travail (ex: `TP 1 - Laboratoire sur les 5S`), date limite de remise (ex: `28-fév-2026 à 12:00`), statut de remise.
- Exemple HTML **anonymisé** d'une ligne (extrait de `ListeTravauxEtu.aspx`):
```html
<tr class="ligneTravail">
    <td class="colonneTitre">
        <a href="#" title="Consulter l'énoncé du travail et remettre votre travail">TP 1 - Laboratoire sur les 5S</a>
    </td>
    <td class="colonneDate">
        28-fév-2026 à 12:00
    </td>
    <td class="colonneStatut">
        via Léa
    </td>
    <td class="colonneAction">
        -
    </td>
</tr>
```

### Dates
- Où la date apparaît sur la **liste**: Dans le `td.colonneDate`. Format: `JJ-MMM-AAAA à HH:MM` (ex: `28-fév-2026 à 12:00`).
- Si date absente sur la liste: Non applicable, la date est présente sur la page de détail des travaux.
- Format date affiché: `JJ-MMM-AAAA à HH:MM`.

### Pagination / filtres
- Session / trimestre à sélectionner: La session est sélectionnée au niveau supérieur de Léa.
- Postback ASP.NET (`__VIEWSTATE`): Oui, l'application utilise ASP.NET.

### Pièges
- Les URLs contiennent des paramètres variables (`Ref`, `SID`, `Info`, `NoCours`, `NoGroupe`).
- La page `SommaireTravaux.aspx` ne contient pas les dates de remise, il faut naviguer vers `ListeTravauxEtu.aspx` pour chaque cours.

### Priorité OmniSync
- P1 calendrier

---

## MODULE: Calendrier / Évènements (Léa `clre` ou menu intranet « Évènements »)

### Accès
- Menu: Accueil intranet → Léa → Calendrier (ou Accueil intranet → Évènements)
- URL finale stable: `https://climoilou-lea.omnivox.ca/cvir/clre/Default.aspx?cal=somm&C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}`
- SSO: oui, domaine `climoilou-lea`

### Liste des éléments
- Sélecteur CSS ou XPath de **chaque ligne**: `div.evenement` ou `td.jourAvecEvenement` (pour les jours avec événements dans la vue mois).
- Champs par ligne: date, titre de l'événement, cours, pondération, heure, local, type (Travail à remettre, Évaluation, Avoir lu le document, etc.).
- Exemple HTML **anonymisé** d'une ligne (extrait de `Default.aspx?cal=somm`):
```html
<div class="evenement">
    <div class="dateEvenement">
        ven 1er mai
    </div>
    <div class="detailsEvenement">
        <span class="typeEvenement">Travail à remettre</span>
        <span class="titreEvenement">Remise - Version presque finale</span>
        <span class="coursEvenement">Classe: 235-215-LI gr. 00001</span>
        <span class="heureEvenement">18:00</span>
        <span class="ponderationEvenement">Pondération 0%</span>
    </div>
</div>
```

### Dates
- Où la date apparaît sur la **liste**: Dans le `div.dateEvenement` (ex: `ven 1er mai`). Le format est `Jour JJ mois`.
- Si date absente sur la liste: Non applicable, la date est présente.
- Format date affiché: `Jour JJ mois` (ex: `ven 1er mai`).

### Pagination / filtres
- Session / trimestre à sélectionner: La session est sélectionnée au niveau supérieur de Léa.
- Postback ASP.NET (`__VIEWSTATE`): Oui, l'application utilise ASP.NET.

### Pièges
- Les URLs contiennent des paramètres variables (`Ref`, `SID`, `Info`).
- Le calendrier peut afficher différents types d'événements (travaux, évaluations, événements scolaires).

### Priorité OmniSync
- P1 calendrier

---

## MODULE: Examens finaux (ESTD `hrex/Examen.ovx`)

### Accès
- Menu: Accueil intranet → Mes Services → Horaire d'examens
- URL finale stable: `https://climoilou-estd.omnivox.ca/estd/hrex/Examen.ovx?Ref={REF_ID}&C=LIM&L=FRA`
- SSO: oui, domaine `climoilou-estd`

### Liste des éléments
- Sélecteur CSS ou XPath de **chaque ligne**: Les examens sont regroupés par date. Chaque examen est un bloc de texte sous un en-tête de date. Un sélecteur pourrait être `div.detailsExamen` ou une combinaison de sélecteurs pour capturer le bloc complet.
- Champs par ligne: date (ex: `Mardi 26 mai 2026`), heure (ex: `08:00 à 11:00`), local (ex: `Local LIM - Q2195`), titre du cours (ex: `Méthodes et processus de travail`), code cours (ex: `235-215-LI`), groupe (ex: `gr. 00001`), enseignant (ex: `Bédard, Rémy`).
- Exemple HTML **anonymisé** d'une ligne (extrait de `Examen.ovx`):
```html
<div class="examen-item">
    <div class="date-examen">
        Mardi 26 mai 2026
    </div>
    <div class="details-examen">
        <span class="heure">08:00 à 11:00</span>
        <span class="local">Local LIM - Q2195</span>
        <span class="type-examen">Cet examen s'effectue en présentiel.</span>
        <span class="titre-cours">Méthodes et processus de travail</span>
        <span class="code-cours">Cours: 235-215-LI</span>
        <span class="groupe-cours">gr. 00001</span>
        <span class="enseignant">Enseignant: Bédard, Rémy</span>
    </div>
</div>
```

### Dates
- Où la date apparaît sur la **liste**: La date est un en-tête (ex: `Mardi 26 mai 2026`). Le format est `Jour JJ mois AAAA`.
- Si date absente sur la liste: Non applicable, la date est présente.
- Format date affiché: `Jour JJ mois AAAA` (ex: `Mardi 26 mai 2026`).

### Pagination / filtres
- Session / trimestre à sélectionner: Oui, via un `select` avec `id="ddlSession"`.
- Postback ASP.NET (`__VIEWSTATE`): Oui, l'application utilise ASP.NET.

### Pièges
- Les URLs contiennent des paramètres variables (`Ref`).
- La sélection de la session nécessite un postback.

### Priorité OmniSync
- P1 calendrier

---

## MODULE: Notes d'évaluation (dates d'examens dans le libellé?)

### Accès
- Menu: Accueil intranet → Léa → Mes classes → [Nom du cours] → Notes d'évaluation
- URL finale stable: `https://climoilou-lea.omnivox.ca/cvir/note/ListeEvalCVIR.ovx?ModeAff=SOMMAIREEVAL&C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}` (pour le sommaire)
- URL de détail: `https://climoilou-lea.omnivox.ca/cvir/note/ListeEvalCVIR.ovx?_________________________________________________________________________________________________________________________________=comp&NDX={INDEX}&FromRech=&From=&cp=_____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________&C=LIM&E=P&L=FRA&Ref={REF_ID}&Info={INFO_PARAM}&NoCours={COURSE_ID}&NoGroupe={GROUP_ID}` (pour le détail d'un cours)
- SSO: oui, domaine `climoilou-lea`

### Liste des éléments
- Sélecteur CSS ou XPath de **chaque ligne**: `table.tblNotes tr` (pour les évaluations individuelles sur la page de détail d'un cours).
- Champs par ligne: titre de l'évaluation (ex: `TP1 - Les 5S`), date (ex: `27 février`), note obtenue, moyenne du groupe, poids de l'évaluation.
- Exemple HTML **anonymisé** d'une ligne (extrait de la page de détail des notes d'un cours):
```html
<tr class="ligneEval">
    <td class="colonneTitre">
        TP1 - Les 5S
    </td>
    <td class="colonneDate">
        27 février
    </td>
    <td class="colonneNote">
        0/4
    </td>
    <td class="colonneMoyenne">
        0%
    </td>
    <td class="colonnePoids">
        4%
    </td>
</tr>
```

### Dates
- Où la date apparaît sur la **liste**: Sur la page de détail des notes d'un cours, la date apparaît dans le `td.colonneDate` (ex: `27 février`). Le format est `JJ mois`.
- Si date absente sur la liste: La date est présente sur la page de détail de chaque cours.
- Format date affiché: `JJ mois` (ex: `27 février`). L'année n'est pas affichée directement, mais est implicite par la session.

### Pagination / filtres
- Session / trimestre à sélectionner: La session est sélectionnée au niveau supérieur de Léa.
- Postback ASP.NET (`__VIEWSTATE`): Oui, l'application utilise ASP.NET.

### Pièges
- Les URLs contiennent de nombreux paramètres variables (`Ref`, `SID`, `Info`, `NoCours`, `NoGroupe`).
- La date est au format `JJ mois` sans l'année, nécessitant de déduire l'année de la session courante.

### Priorité OmniSync
- P2 info (les dates sont des dates d'évaluation, pas des dates de remise ou d'événements de calendrier au sens strict)

---

## MODULE: Actualités (reports, annulations)

### Accès
- Menu: Accueil intranet → Actualités (ou directement sur la page d'accueil)
- URL finale stable: `https://climoilou.omnivox.ca/intr/UI/WebParts/SiteIntra_Actualites/WebPart_2_Liste.aspx?C=LIM&E=P&L=FRA&Ref={REF_ID}&FSA=true`
- SSO: oui, domaine `climoilou`

### Liste des éléments
- Sélecteur CSS ou XPath de **chaque ligne**: `a.carte-portail.carte-actualite`
- Champs par ligne: titre (ex: `Un premier emploi pour toi`), date (ex: `26 mai 2026`).
- Exemple HTML **anonymisé** d'une ligne:
```html
<a class="carte-portail carte-actualite" data-manus_click_id="57" data-manus_clickable="true" data-oid="94ea3910-d00d-4c4a-8b9d-6bdd9a00b899" data-prov="1" data-ref="C1286" href="/intr/webpart.gestion?IdWebPart=00000000-0000-0000-0003-000000000007&amp;mode=one&amp;idNews=1286&amp;idProv=1&amp;FSA=true&amp;RTP=1" title="Un premier emploi pour toi">
 <div class="carte-portail-header">
  <img alt="Un premier emploi pour toi" class="card-actualite-image-container" src="/intr/UI/WebParts/SiteIntra_Actualites/ObtenirImageActualite.ashx?i=T3g5SklYSTExVGl4OERMTEFGM0VzSEo0NHVtcVdOMmNudGUyV0dDclJzNW50NExob2NhaTMwYUhuZ1BYS0gzcHpSTHJkYWVUSlZIdUVvQ0pGUE04bnEvdXBKNHFyaWJRNXdFVVZQR1U4Ui90dU95ZmgzaktZbTlFbDRvZWVvTkxFZlc1alQzM1JtdHA2RGV5SWZ6MmdJRWZ4WmN0V3ZvZythSWRYbWVYWHZxblZ4ZU5YWTl5eW5FNHgzVkg3MCtqZlFXVjA5d0M0ZkFTV243elI0cUE5QT09"/>
 </div>
 <div class="carte-portail-border" style="background-color: hsl(30,62%,84%);">
 </div>
 <div class="carte-portail-contenu">
  <div class="carte-portail-type">
   <div class="svg-icon" tabindex="-1">
    <svg aria-hidden="true" focusable="false" height="100%" viewbox="0 0 30 30" width="100%" xmlns="http://www.w3.org/2000/svg">
     <path d="m27.494 0h-24.988a2.515 2.515 0 0 0 -2.506 2.5v24.99a2.516 2.516 0 0 0 2.506 2.51h24.988a2.516 2.516 0 0 0 2.506-2.51v-24.99a2.515 2.515 0 0 0 -2.506-2.5zm-23.488 7h9v9h-9zm21.988 15.99h-21.988v-3h21.988zm0-6.988h-9.988v-3.002h9.988z">
     </path>
    </svg>
   </div>
   actualité
  </div>
  <h3 class="carte-portail-titre multi-line-ellipsis" style="max-height: 56.7px; overflow: hidden; text-overflow: ellipsis; -webkit-box-orient: vertical; display: -webkit-box; -webkit-line-clamp: 3;">
   Un premier emploi pour toi
  </h3>
 </div>
 <div class="carte-portail-footer">
  <div class="carte-portail-desc">
   <i class="material-icons date-card-icon">
    refresh
   </i>
   26 mai 2026
   <div class="indicateur">
   </div>
  </div>
 </div>
</a>
```

### Dates
- Où la date apparaît sur la **liste**: Dans le `div.carte-portail-desc` sous la balise `i.material-icons.date-card-icon`. Format: `JJ mois AAAA` (ex: `26 mai 2026`).
- Si date absente sur la liste: Non applicable, la date est présente.
- Format date affiché: `JJ mois AAAA` (ex: `26 mai 2026`).

### Pagination / filtres
- Session / trimestre à sélectionner: Non applicable, les actualités sont générales.
- Postback ASP.NET (`__VIEWSTATE`): Oui, l'application utilise ASP.NET.

### Pièges
- Les URLs contiennent des paramètres variables `Ref`.
- Le contenu est chargé dynamiquement, mais les éléments sont présents dans le HTML initial.

### Priorité OmniSync
- P2 info (peut contenir des reports ou annulations, mais pas des événements de calendrier direct)

---

## MODULE: Documents distribués / Énoncés distribués

### Accès
- Menu: Accueil intranet → Léa → Mes classes → [Nom du cours] → Documents de cours
- URL finale stable: `https://climoilou-lea.omnivox.ca/cvir/ddle/ListeDocuments.aspx?C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}&NoCours={COURSE_ID}&NoGroupe={GROUP_ID}`
- SSO: oui, domaine `climoilou-lea`

### Liste des éléments
- Sélecteur CSS ou XPath de **chaque ligne**: `tr.ligneDocument` (pour les lignes de documents individuels).
- Champs par ligne: titre du document (ex: `Plan de cours 235-215-LI gr. 00001`), date de distribution (ex: `depuis le 26 jan 2026`), date de lecture requise (ex: `Avoir lu ce document d'ici au jeudi le 29 janvier`), taille du fichier.
- Exemple HTML **anonymisé** d'une ligne (extrait de `ListeDocuments.aspx`):
```html
<tr class="ligneDocument">
    <td class="colonneTitre">
        <a href="#" title="Voir ou télécharger">Plan de cours 235-215-LI gr. 00001</a>
        <div class="descriptionDocument">
            Avoir lu ce document d'ici au jeudi le 29 janvier
        </div>
    </td>
    <td class="colonneDate">
        depuis le
        <span class="dateDistribution">26 jan 2026</span>
    </td>
    <td class="colonneTaille">
        H26-235-215-LI_Me...
        1.4 Mo
    </td>
</tr>
```

### Dates
- Où la date apparaît sur la **liste**: La date de distribution est dans un `span.dateDistribution` (ex: `26 jan 2026`). Une date de lecture requise peut être présente dans le `div.descriptionDocument` (ex: `Avoir lu ce document d'ici au jeudi le 29 janvier`).
- Si date absente sur la liste: Non applicable, les dates sont présentes.
- Format date affiché: `JJ mois AAAA` (ex: `26 jan 2026`) ou `Jour JJ mois` (ex: `jeudi le 29 janvier`).

### Pagination / filtres
- Session / trimestre à sélectionner: La session est sélectionnée au niveau supérieur de Léa.
- Postback ASP.NET (`__VIEWSTATE`): Oui, l'application utilise ASP.NET.

### Pièges
- Les URLs contiennent de nombreux paramètres variables (`Ref`, `SID`, `Info`, `NoCours`, `NoGroupe`).
- Il y a deux types de dates: date de distribution et date de lecture requise, toutes deux importantes pour OmniSync.

### Priorité OmniSync
- P1 calendrier (les dates de lecture requises sont des événements importants)

---

## Tableau récapitulatif

| Module | URL pattern | Date sur liste? | Fiche détail? | Sélecteur ligne |
|---|---|---|---|---|
| Travaux – Énoncé et remise | `https://climoilou-lea.omnivox.ca/cvir/dtrv/ListeTravauxEtu.aspx?C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}&NoCours={COURSE_ID}&NoGroupe={GROUP_ID}` | Oui | Non (détail sur la même page) | `tr.ligneTravail` |
| Calendrier / Évènements | `https://climoilou-lea.omnivox.ca/cvir/clre/Default.aspx?cal=somm&C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}` | Oui | Non (détail sur la même page) | `div.evenement` ou `td.jourAvecEvenement` |
| Examens finaux | `https://climoilou-estd.omnivox.ca/estd/hrex/Examen.ovx?Ref={REF_ID}&C=LIM&L=FRA` | Oui | Non (détail sur la même page) | `div.examen-item` |
| Notes d'évaluation | `https://climoilou-lea.omnivox.ca/cvir/note/ListeEvalCVIR.ovx?ModeAff=SOMMAIREEVAL&C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}` | Non (sur page détail) | Oui | `tr.ligneEval` (sur page détail d'un cours) |
| Actualités | `https://climoilou.omnivox.ca/intr/UI/WebParts/SiteIntra_Actualites/WebPart_2_Liste.aspx?C=LIM&E=P&L=FRA&Ref={REF_ID}&FSA=true` | Oui | Non (détail sur une autre page) | `a.carte-portail.carte-actualite` |
| Documents distribués / Énoncés distribués | `https://climoilou-lea.omnivox.ca/cvir/ddle/ListeDocuments.aspx?C=LIM&E=P&L=FRA&Ref={REF_ID}&SID={SESSION_ID}&Info={INFO_PARAM}&NoCours={COURSE_ID}&NoGroupe={GROUP_ID}` | Oui | Non (détail sur la même page) | `tr.ligneDocument` |

---

## 3 corrections les plus utiles pour récupérer les 14 travaux sans date sur SommaireTravauxEtu

Pour récupérer les 14 travaux sans date sur la page `SommaireTravauxEtu` (qui est la page de sommaire des travaux par cours, et non la liste détaillée des travaux), il faut comprendre que cette page ne liste que les cours et le nombre d'énoncés distribués, mais pas les travaux individuels avec leurs dates. Les dates sont disponibles sur la page de détail des travaux pour chaque cours (`ListeTravauxEtu.aspx`).

Voici les 3 corrections les plus utiles pour récupérer les dates des travaux:

1.  **Naviguer vers la page de détail des travaux pour chaque cours**: La page `SommaireTravauxEtu` fournit une liste des cours avec le nombre d'énoncés distribués. Pour obtenir les dates de remise de chaque travail, il est impératif de cliquer sur chaque cours listé (par exemple, le lien avec le titre du cours comme `MÉTHODES ET PROCESSUS DE TRAVAIL`) pour accéder à la page `ListeTravauxEtu.aspx`. C'est sur cette page que les travaux individuels et leurs dates de remise sont affichés.

2.  **Extraire les dates de la colonne "Date limite de remise" sur `ListeTravauxEtu.aspx`**: Une fois sur la page `ListeTravauxEtu.aspx`, chaque travail est listé avec une colonne "Date limite de remise". Le sélecteur CSS pour cette date est `td.colonneDate`. Le format est `JJ-MMM-AAAA à HH:MM`, ce qui est facilement parsable.

3.  **Gérer les paramètres d'URL variables**: Les URLs pour accéder aux pages de détail des travaux (`ListeTravauxEtu.aspx`) contiennent des paramètres variables tels que `Ref`, `SID`, `Info`, `NoCours`, et `NoGroupe`. Il est crucial de capturer ces paramètres dynamiquement lors de la navigation depuis la page `SommaireTravauxEtu` pour pouvoir construire les URLs correctes vers les pages de détail de chaque cours. Le `NoCours` et `NoGroupe` sont particulièrement importants pour identifier le cours spécifique.

En résumé, la stratégie consiste à:
*   Parcourir la page `SommaireTravauxEtu` pour identifier tous les cours.
*   Pour chaque cours, extraire les informations nécessaires pour construire l'URL de la page `ListeTravauxEtu.aspx`.
*   Naviguer vers chaque page `ListeTravauxEtu.aspx`.
*   Sur chaque page `ListeTravauxEtu.aspx`, extraire le titre du travail, la date et l'heure de remise de la colonne correspondante.
