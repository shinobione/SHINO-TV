# SHINO // LINK Windows V1.0.1 — correction du menu d’état

21 octobre 2026. Retour propriétaire [#85 / UI HOLD](https://github.com/shinobione/SHINO-TV/pull/85#issuecomment-6309141360).
Source initiale `630bf32cef6e5ccc07a894a1321dc2c4d9f8560d`, branche existante
`feature/link-m3r-unified-integration-20261019`, Draft et non fusionnée.

## EXE réellement construit et testé

`C:\Users\jerry\SHINO-TV-V06-AUDIT\research-local\SHINO-LINK-Windows-V1-UI-FIX-20261021\SHINO-LINK.exe`

**17 592 329 octets**, SHA-256 :

`bdf039fd8313a14ca9130b003d5342f3c5632ff4d0174427bdebbc70314c8613`

Windows x64, GUI sans console, interpréteur et dépendances embarqués,
version Windows affichée **1.0.1** dans le sous-menu d’état. Build non installé.
L’EXE V1 précédent et ses preuves sont conservés, sans remplacement :
17 588 605 o / `9d2fdde369362061cefbf9fe4ecbd9016e6c7bea65012fed001b68a75e926df6`.

## Reproduction et correction

Le premier essai manuel propriétaire de V1 est **PARTIAL / UI HOLD** : la
boîte d’état reste ouverte. Les anciennes preuves de build/CI conservent leur
périmètre et ne deviennent pas une validation humaine de fermeture.

Reproduction locale sur le code exact de l’ancien bundle, réseau interdit :
vrai `TrackPopupMenuEx`, sélection de « Consulter l’état » par `WM_CHAR` dans
la fenêtre du menu natif du seul processus de test. Le callback et
`MessageBoxW` s’exécutent sur le même thread Win32. Un `BM_CLICK` posté au
bouton OK laisse la boîte visible après 500 ms ; `WM_CLOSE` la ferme.
Cela reproduit le chemin problématique sans attribuer une cause interne
unique à Windows, à pystray ou aux clics physiques du propriétaire.

La nouvelle action est un **sous-menu natif avec lignes désactivées** : état,
version Windows, compteurs acceptés/tentatives, échecs, âge du dernier ACK PC,
mesures prises en charge, option horloge, rappel des modes PC. Aucune boîte,
requête, collecte de capteur, lecture privée ou nouveau worker. Données lues
uniquement dans la RAM du moteur ; pas de valeur de mesure inventée.

Le menu est reconstruit sur le thread Win32 immédiatement avant chaque
ouverture. Le worker ne détruit plus le menu pendant son affichage ; il
continue d’actualiser l’icône/infobulle. Les choix radio restent des aperçus PC,
avec « SmallTV : aucun changement envoyé ». #83 reste désactivé / OTA HOLD.
Les dialogues d’erreur au démarrage et l’autostart opt-in sont conservés.

## Preuves Win32 sur le nouvel EXE

EXE seul copié dans un chemin avec espaces, PATH réduit à System32,
variables Python/venv retirées : **PASS**, sans interpréteur externe.

- **7 cycles** réels d’ouverture d’état, fermeture du sous-menu par Échap,
  fermeture du menu racine et réouverture : PASS.
- **8 sélections radio natives** : les quatre modes, dans le scénario de
  transport fictif et dans l’aperçu hors ligne : PASS.
- **2 sélections natives de Quitter** : retour de la boucle Win32, arrêt du
  worker et libération des verrous : PASS.
- HMENU et textes réellement lus via API Win32, lignes d’état désactivées,
  compteurs et état CONNECTED actualisés après reconnexion fictive : PASS.
- Aucun `MenuItem` appelé directement pour les sélections de ces tests,
  aucun retour de popup simulé ; messages ciblés vers les HWND du seul PID
  de test. Aucun clavier/souris global injecté.
- Aucune fenêtre de dialogue d’état ; tout appel à `message()` depuis ce
  smoke tray ferait échouer le test. Aperçu : **zéro worker / zéro envoi**.
- Même vrai moteur et code de POST LINK sur faux HTTP : RETRYING → CONNECTED
  → RETRYING → CONNECTED, quatre mesures fixture explicitement synthétiques.
  Zéro tentative socket/DNS, exclusion d’un second EXE, un seul worker.
- Boîtes natives de démarrage config absente, identifiants absents et
  arguments invalides toujours vérifiées ; codes de sortie 1/1/2 : PASS.

**72 tests ciblés PASS** : état 4, entrée Windows 12, moteur LINK 28,
menu modes 15, politique des modes 13. Contrôles des pins Windows et du
refus des mutations exécutés séparément. Les pins historiques restent stricts.
Les deux tables de nouveaux fichiers PC sont mises à jour avec les blobs
exacts des deux sources Windows modifiées, sans exemption globale.

Preuves dans le nouveau dossier livré : `BASELINE-WIN32.json`,
`tests/FROZEN-SMOKE.json` (cycles, lignes natives et assertions),
`tests/EXE-TESTS.json`, `BUILD-MANIFEST.json`, `BUILD.log`.
**AUTOMATED_WIN32=PASS ; OWNER_RETEST=NOT_RUN** pour ce nouvel EXE.
Aucun lancement LIVE, test SmallTV/VM, modification de registre/autostart,
installation, remplacement de LINK ni nouveau travail M3-R.

## Lancement manuel sûr

Win+R, puis :

```text
"C:\Users\jerry\SHINO-TV-V06-AUDIT\research-local\SHINO-LINK-Windows-V1-UI-FIX-20261021\SHINO-LINK.exe" --offline-preview
```

Clic droit → Consulter l’état : sous-menu ; Échap pour fermer, puis
Quitter SHINO // LINK. Les quatre modes sont des aperçus PC. Ne pas lancer
sans `--offline-preview` pendant cette qualification : le lancement par
défaut reste le sender LIVE existant, qui exige une décision séparée.

Le patch HMAC et ses preuves demeurent hors commit, avec contrôle intégral
de leurs **8 589 fichiers** ; les 18 lignes HMAC locales de ROADMAP restent
hors index. La CI du commit final est vérifiée séparément avant le rapport
de livraison ; une CI antérieure n’est pas présentée comme celle du nouveau SHA.
Arrêt après cette livraison.
