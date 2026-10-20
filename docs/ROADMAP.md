# SHINO // TV — Roadmap active (synthèse publique)

**Mise à jour : 21 octobre 2026.** Cette page est un index de décisions et d'étapes, pas une preuve de correspondance entre `main`, les branches de développement, un BIN privé, le PC Windows et le SmallTV réellement installé.

## Situation de référence

- **OBSERVÉ PROPRIÉTAIRE (dernier checkpoint daté) :** firmware privé P0+Updater512 installé par UART, démarrage à froid et quatre cartes CPU/GPU/RAM/GPU temp + horloge affichées, SHINO LINK transmet les quatre mesures. Voir [PROJECT_STATE.md](PROJECT_STATE.md).
- **OBSERVÉ PROPRIÉTAIRE / non relu en direct :** VM Freebox météo déjà installée/testée ; publication météo signée décrite OFF. Aucune nouvelle activation implicite.
- **HOLD :** aucune OTA post-P0+Updater512 confirmée sur l'appareil ; ne pas confondre code en Draft PR et firmware installé.
- **PROUVÉ FICHIER (21/10) :** trois références graphiques natives 240 × 240 et leurs zooms, désormais disponibles dans [le dossier UI](UI_240X240_REFERENCES.md). Il s'agit de maquettes, pas de sorties du matériel.

## Jalons produit

| Ordre | Travail | Statut / dépendance | Critère pour avancer |
| --- | --- | --- | --- |
| 1 | **Conserver le socle P0+Updater512** : HMAC/Digest, `4m2m`, LittleFS, OTA, Wi-Fi, LINK, horloge et récupération | **Prioritaire ; état physique daté, revalidation ciblée nécessaire** | Aucune régression de sûreté ; identité BIN/layout/ressources prouvées avant écriture |
| 2 | **B5.4 météo LAN signée** sur la VM Freebox existante | **Intégration logicielle autorisée antérieurement ; physique/activation HOLD** | Validation offline de la chaîne signée, données valides/périmées, budgets et protections ; aucune seconde VM |
| 3 | **Références visuelles V1 240 × 240** : monitoring, horloge/météo, musique | **Images intégrées ; réception graphique à confirmer** | Contrat UI et lisibilité native discutés avec le propriétaire |
| 4 | **Portage graphique monitoring + horloge/météo** dans le renderer natif | **PLANIFIÉ / non réalisé par ce pack** | Captures HOST natives de 240 × 240, texte sans clipping, barres et mémoire ; pas de régression des quatre mesures |
| 5 | **Contrôle de modes Windows via SHINO LINK** : Automatique / Horloge-Météo / Monitoring / Musique | **PR Draft / maquettes HOST existantes, pas un contrôle physique livré** | Règles de priorité et sources fiables, contrat authentifié borné, tests HOME-LAN, aucune collision avec Codex en cours |
| 6 | **Mode musique natif** : pochette carrée, artiste, titre, progression, Play/Pause | **PLANIFIÉ / système de données et rendu réels à valider** | Source PC réelle, scène exclusive, limite mémoire du décodeur, durée/état/texte longs et fallback prouvés |
| 7 | **Qualification physique des nouveaux écrans** | **HOLD — GO matériel candidat spécifique obligatoire** | Comparaison photos 240 × 240, lisibilité à distance, comportement réel, acceptation propriétaire |

Les jalons 4–6 peuvent être étudiés en parallèle **en HOST**, mais ne doivent pas modifier les mêmes branches sans coordination. Une proposition visuelle ne débloque jamais un flash ni une OTA.

## Contrats d'affichage retenus

- **Monitoring** : CPU %, GPU %, RAM en `Go` (ex. `11.3 Go` sans capacité ni pourcentage textuel), GPU temp °C ; quatre libellés sur une ligne et quatre barres conservées ; heure/météo lisibles.
- **Horloge/météo** : heure dominante, jour seul, condition météo en français, température et icône ; pas de ville obligatoire.
- **Musique** : pochette 1:1 sans maximum 64 px, titre/artiste lisibles, durée écoulée/totale et statut Play/Pause.
- **Modes** : Auto / Horloge-Météo / Monitoring / Musique, par SHINO LINK à terme ; l'override manuel explicite prime lorsqu'il sera implémenté. Ne pas créer un second service PC ou réinstaller la VM.
- **Source of truth** : polices, surfaces, animations et marges **à valider dans le vrai rendu firmware et sur l'écran**, jamais par un PNG agrandi seul.

## Documents et travaux liés

- [Références UI / critères de validation](UI_240X240_REFERENCES.md).
- [Checkpoint matériel/logiciel et interdictions](PROJECT_STATE.md).
- [Règles de reprise](../AGENTS.md).
- [PR #73 — tests HOST renderer B5.4](https://github.com/shinobione/SHINO-TV/pull/73).
- [PR #76 — politique de modes d'affichage](https://github.com/shinobione/SHINO-TV/pull/76).
- [PR #52 — plan Windows SHINO LINK](https://github.com/shinobione/SHINO-TV/pull/52).

Les roadmaps détaillées situées sur des branches de travail historiques restent des sources **datées et dépendantes de leur branche** ; cette synthèse n'affirme pas les avoir fusionnées dans `main`.

## Prochaine action

**Faire valider les trois références à leur taille réelle par le propriétaire**, puis préparer un portage **HOST/SIMULÉ** ciblé du monitoring et de l'horloge, sans contact SmallTV, sans modifier un firmware installé ni pousser sur une branche Codex concurrente.
