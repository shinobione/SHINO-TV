# SHINO // TV × SHINO // LINK — Plan de réunification

**Document de coordination actif au 19 octobre 2026 sur [PR #85](https://github.com/shinobione/SHINO-TV/pull/85).**
**Ce document est un plan et un inventaire de preuves, pas un merge ni une livraison.**
Le SmallTV réel a passé la vérification postboot B5.4 [#81](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6275185762) après une OTA unique. Le firmware privé, les codes de fabrication publics, les branches Codex locales, le Windows installé et les laboratoires M3-R sont **cinq objets distincts** jusqu'à rapprochement explicite.

## 1. Architecture produit cible — une chaîne, pas deux applications concurrentes

| Couche | Responsabilité / comportement cible | Statut actuellement prouvé |
| --- | --- | --- |
| SmallTV ESP8266 4 MiB, LCD 240×240 | Firmware B5.4 exécuté ; cartes **CPU, GPU, RAM, GPU temp** ; horloge ; météo autonome ; scène musique exclusive ; état d'affichage | Identité B5.4 postboot rapportée et affichage cartes+heure observé. Météo en fonctionnement et musique **NON VÉRIFIÉES** |
| SHINO // LINK Windows (un seul EXE/tray) | Unique télémétrie CPU/GPU/RAM/GPU temp, reconnexion, menu **Auto / Horloge & météo / Monitoring / Musique**, et bouton d'inspection de version | LINK actuel observé avec télémétrie ; nouveau menu #54/#83 **HOST seulement**, EXE inchangé |
| Canal de contrôle M3 | Une route mode authentifiée **HMAC-SHA256** pré-corps, révision/tx anti-rejeu, origine LAN STA, une prise de socket contrôlée, pas d'autre serveur | Labs M3-A→R sur #85 ; **pas** de handler actif B5.4/commande écran |
| Canal de lecture diagnostic | GET Digest manuel borné, partage du verrou, contrôle du vrai BIN+manifeste+reçu, identité inconnue honnête | #83 importé dans #85, tests HOST ; **pas installé**, pas de nouveau GET physique |
| VM Freebox météo | Open-Meteo HTTPS → VM existante → SAMPLE signé LAN ; indépendant du PC | VM existante testée selon propriétaire ; publication vers TV rapportée OFF ; **ne pas réinstaller / activer** |
| Maintenance OTA/recovery | One-shot conservateur, staging 4m2m, LittleFS/SDK préservés, STOP_UNKNOWN_NO_RETRY et réservations immuables | Première OTA B5.4 et preuve postboot #81 rapportées. Un second transfert est **NON AUTORISÉ** |

Les modes sont une **politique d'affichage**, pas quatre firmwares. En mode **Auto** : affichage des cartes+horloge/météo sans lecture musicale ; en lecture, scène musique/pochette qui masque les cartes à l'écran mais ne coupe pas leur ingestion. En sélection manuelle **Horloge & météo**, conserver les métriques reçues en fond. Le fonctionnement précis des scènes **Monitoring** et **Musique** doit être figé et testé entre le menu M2 et le renderer B5.4 avant raccordement. L'écran doit rester **240×240**, avec libellés lisibles exactement CPU, GPU, RAM, GPU temp, barres/métriques préservées.

## 2. Graphe des sources / PR et ordre de réconciliation

| Chantier | Source / statut | Action dans #85 |
| --- | --- | --- |
| Firmware P0+Updater512+B5.4 installé | Issue [#81 — postboot réel](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6275185762) ; original privé #74 ; identités privées non publiées | **Référence physique uniquement.** Ne jamais le reconstruire/écraser d'après une PR publique |
| Graphe B5.4 public assaini | [PR #72](https://github.com/shinobione/SHINO-TV/pull/72), Draft | Qualifier le vrai source graph/provenance, ancien HTTP/Digest, OTA, 4m2m. **Non importé** |
| Rendu météo → LCD 240×240 HOST | [PR #73](https://github.com/shinobione/SHINO-TV/pull/73), Draft sur #72 | Réutiliser tests/contrat après inspection du HEAD et du différentiel. **Non importé** |
| Modes Auto / Horloge & météo | [PR #76](https://github.com/shinobione/SHINO-TV/pull/76), Draft sur #73 | Réconcilier politique renderer et commande M3 sans activer. **Non importé** |
| Modes Windows M1/M2 | [PR #53](https://github.com/shinobione/SHINO-TV/pull/53) → [#54](https://github.com/shinobione/SHINO-TV/pull/54) | Ancêtres de #85, conserver état de l'EXE en place |
| Vérifier firmware Windows | [Issue #83](https://github.com/shinobione/SHINO-TV/issues/83), [PR #84](https://github.com/shinobione/SHINO-TV/pull/84) | **12 fichiers exacts déjà importés** dans #85 ; conserver le verrou Digest et le HOLD marqueurs OTA |
| M3-A…Q, travaux TCP/auth/ressources | Chaîne de PR [#56](https://github.com/shinobione/SHINO-TV/pull/56) → [#82](https://github.com/shinobione/SHINO-TV/pull/82) | Ancêtres de #85 ; historique de LAB seulement, pas de déploiement |
| **M3-R — seul point de convergence actif** | [PR #85](https://github.com/shinobione/SHINO-TV/pull/85), branche `feature/link-m3r-unified-integration-20261019` | **Continuer ici**, sans modifier les branches Codex ou merger les PR sources |

**Ne pas confondre « présence par ascendance » avec « intégré au binaire B5.4 ».** Les anciens laboratoires M3 héritent d'un graphe B5.3 et de Core 3.1.2 ; même si leur CI passe, l'intégration dans le **B5.4 installé** reste à concevoir, à prouver hors ligne et à qualifier sur les octets/provenances privés pertinents.

## 3. Contrat d'intégration unique : critères vérifiables

| Porte | Exigence de passage | État |
| --- | --- | --- |
| G0 Provenance | HEAD GitHub/local propre, correspondance publique↔source privée évaluée par Codex, pas de secrets ni identités privées dans GitHub | **HOLD —** source privée non consultée par cette branche |
| G1 Auth / ingress | Core véritable, un seul listener, transfert M3-O après ligne M3-P bornée, **un seul parseur M3-C**, HMAC avant corps, absence de double buffer | **LAB HOST/Xtensa inerte**, intégration réelle non faite |
| G2 Compatibilité HTTP | Non-régression Digest, GET d'identité, POST télémétrie, horloge, météo signée, OTA, erreurs/timeout, AP STA et anciennes routes | **HOLD** sur graphe B5.4 complet |
| G3 UI / LINK | Quatre cartes et barres exactes, AUTO, override Horloge, scènes musique exclusives, TTL/continuité des métriques, reconnexion, tray Windows et autostart | **PARTIEL HOST / observation ancienne**, pas de qualification combinée |
| G4 Diagnostics / OTA | Un seul GET manuel après clic, serrure Digest partagée, vrai répertoire/réservation `.attempt`, pas de contrôle pendant OTA active/incertaine, aucun retry | **HOLD** : le client #81 privé et ses marqueurs ne sont pas encore rapprochés du bouton #83 |
| G5 Ressources physiques | Mesurer sur **candidat complet** : flash 4m2m/staging, statique/IRAM, heap/bloc/CONT au pire cas, WDT, LittleFS, rollback absent et voie récupération | **HOLD** ; le snapshot postboot ne mesure pas le coût M3-R |
| G6 Activation matérielle | GO neuf pour candidat/identité et opération exacts, récupération étudiée, preuves et seuils intacts | **NON AUTORISÉ**, aucun transfert/reboot à lancer |

La fermeture de G0 à G5 ne vaut **pas** approbation automatique de G6. L'exécuteur OTA #81 one-shot a consommé son unique GO. Toute sortie incertaine = STOP / aucun retry, conservation absolue des sauvegardes, reçus et marqueurs.

## 4. État physique et journal de décision

- [#81 staging + timeout / STOP](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6274872177) : un POST autorisé, ACK `STAGED_PENDING_BOOT`, première vérification postboot expirée. État alors **UNKNOWN**.
- [#81 observation LCD propriétaire](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6275027781) : écran affichant cartes, date et heure après reboot. Cela ne suffit pas à identifier la version.
- [#81 identité postboot authentifiée](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6275185762) : B5.4 original **confirmé** à 431 920 o après vérification des fichiers privés ; boot différent ; `fs_ok=true`, `metrics_fresh=true`, `last_update=NONE`, `ota_enabled=true`. Au même instant heap **28 168**, bloc **26 080**, CONT **2 180** o, fragmentation **8 %**.
- Météo B5.4 physique **NON QUALIFIÉE** ; publisher VM **OFF** selon rapport. Aucun GET, POST, OTA, changement de VM, reboot, UART ou Wi-Fi ne résulte de cette documentation.

## 5. Méthode de développement / branche unique

1. **Travailler uniquement sur #85** pour la convergence, après relecture HEAD/working tree/CI/PR concurrentes. Ne pas forcer les branches de Codex ; les PR sources restent Draft, consultables et inchangées.
2. Comparer les **vraies routes et bibliothèques de #72** au laboratoire M3-R, puis les scènes de #76 et tests de #73. Garder la provenance d'origine et l'historique, sans transposer directement des tests simulés comme du code déployable.
3. Adapter **un seul graphe produit B5.4** ; un seul worker Windows de télémétrie, un seul serveur ESP8266, un seul parser HMAC spécifique au contrôle, sans contourner les bornes et gardes existantes.
4. Tester comportement nominal, mauvais identifiants, altération, replay, fragmentation, timeout, EOF, reconnexion, concurrence et chemins Legacy; mesurer l'image **complète** sans toucher au SmallTV.
5. Avant diffusion de l'EXE Windows #83, obtenir la preuve de coordination de l'état OTA privé #81 avec le répertoire/les réservations et le verrou Digest. Un vieux `STOP_UNKNOWN_NO_RETRY` peut coexister avec l'identité B5.4 postboot confirmée : **ne pas effacer** ce marqueur pour lever un HOLD.
6. Mettre à jour [PROJECT_STATE.md](PROJECT_STATE.md), [ROADMAP.md](ROADMAP.md), [AGENT_HANDOFF.md](AGENT_HANDOFF.md) au SHA final avec PASS/NOT_RUN/HOLD. Préserver tous les anciens audits comme contexte daté.

**Prochaine action technique unique :** inspecter et comparer le vrai graphe B5.4 public de #72 au laboratoire M3-R de #85, identifier le point unique d'insertion du contrôle HMAC sans perte de Digest/OTA/SHINO-WX/1 ; documenter cette parité et ses mesures avant tout portage privé. Aucune installation physique autorisée.
