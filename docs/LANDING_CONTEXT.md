# OmniSync — Landing Page Context (pour Lovable)

## Résumé du projet en une phrase
OmniSync est un programme Windows gratuit (beta) qui lit Omnivox et Moodle chaque matin en arrière-plan et dépose automatiquement tous les travaux, examens et annulations dans Google Calendar — sans que l'étudiant ait besoin de rien faire.

---

## Le problème (douleur viscérale)

Les étudiants de cégep au Québec doivent chaque jour naviguer entre :
- Omnivox LÉA (travaux, calendrier)
- Omnivox MIO (messages)
- Moodle (remises, annonces)
- Leur agenda personnel

Cette dispersion génère : charge mentale élevée, stress de l'oubli, et des remises manquées. Le problème n'est pas l'étudiant — c'est l'outil imposé par l'institution.

---

## La solution

Un script local (Windows) qui :
1. S'exécute automatiquement à 05h chaque matin
2. Se connecte à Omnivox + Moodle avec les identifiants de l'étudiant
3. Extrait travaux, examens, annulations
4. Crée/met à jour les événements dans Google Calendar de l'étudiant
5. **Ne touche aucun serveur externe** — tout reste sur l'ordinateur de l'étudiant

---

## Cible

- **Qui** : Étudiants de cégep au Québec (18–22 ans), utilisateurs d'Omnivox
- **Niveau tech** : Non-technique — ils veulent que ça marche, pas comprendre comment
- **Cégeps prioritaires** : Cégep Limoilou (testé), autres cégeps Omnivox compatibles
- **Plateforme** : Windows uniquement pour l'instant

---

## Objectif de la landing page

**Waitlist beta — 20 premières places.**

- Créer de la rareté réelle (20 places, pas fictives)
- Collecter l'email + cégep de l'étudiant
- Crédibiliser le projet (confiance, sécurité, sérieux)
- Préparer le terrain pour une version payante future

---

## Proposition de valeur principale

> "Tu ouvres Google Calendar le matin — tout y est. Tu n'as plus besoin de te connecter à Omnivox."

---

## Arguments de confiance (très importants pour ce projet)

- Données 100 % locales sur l'ordinateur de l'étudiant
- Aucun serveur OmniSync ne reçoit quoi que ce soit
- Mot de passe stocké dans le coffre Windows sécurisé (pas en clair)
- Code source visible sur GitHub (open source)
- Projet indépendant — pas affilié à Omnivox, Skytech ou un cégep

---

## Sentiments cibles après la visite

1. **Confiance** — "Mon mot de passe est en sécurité"
2. **Excitation** — "Enfin quelqu'un a réglé ce problème"
3. **Simplicité** — "C'est simple, je peux faire ça"

---

## Modèle de prix (à définir — inclure dans la recherche Perplexity)

- Beta : gratuit pour les 20 premiers
- Version finale : probablement payante
- Format à explorer : one-time purchase (~9–15 $) ou abonnement annuel (~20–30 $/an)
- À éviter : freemium complexe (trop dur à gérer solo)

---

## Friction à minimiser sur la landing page

L'installation actuelle est complexe (Python, Google Cloud Console, OAuth). La landing page doit :
- Ne PAS montrer les étapes techniques dans le hero
- Promettre une installation guidée (assistant pas à pas)
- Rassurer : "Si tu peux installer Spotify, tu peux installer OmniSync"

---

## Stack technique du projet

- Python (Windows CLI)
- Playwright (scraping Omnivox/Moodle)
- Google Calendar API (OAuth)
- SQLite (stockage local)
- PyInstaller (futur .exe)
- Distribution : GitHub Releases

---

## Ce que la landing page doit faire concrètement

1. **Hero** : Problème → Solution en 2 phrases. CTA waitlist.
2. **Preuve du problème** : Montrer visuellement la dispersion Omnivox (screenshots ou animation)
3. **Demo visuelle** : Montrer le résultat dans Google Calendar
4. **Sécurité** : Section dédiée "Tes données restent chez toi"
5. **Rareté** : Compteur ou mention "20 places beta — X restantes"
6. **FAQ** : Répondre aux objections (sécurité, cégep compatible, Windows only)
7. **Formulaire** : Email + choix du cégep

---

## Ton et voix

- Québécois, direct, familier (tutoiement)
- Pas corporate, pas startup américaine
- Cri du cœur partagé : "Omnivox c'est le chaos"
- Humour sobre, pas de gimmicks

---

## Contraintes

- Pas de backend pour l'instant — le formulaire waitlist peut aller vers un Google Form ou Tally
- Mobile-first (les étudiants voient la page sur leur téléphone)
- Palette à définir — suggestion : bleu académique + accent vert (Google Calendar)
