# SHINO // TV — État opérationnel et décisions actives

## 20 octobre — incrément 4 natif B5.4/M3-R strictement inerte

Deux compositions Xtensa Core 3.1.2, StageA B5.4 avec/sans handoff ; entrée
vide, BIN rendu non amorçable, refus 503 intact, aucun writer/ACK de commande.
RAM statique +2116 o, BIN +6112 o ; heap/CONT/WDT physiques NON VÉRIFIÉS.
[Mesures, preuves et limites](B54_M3R_NATIVE_INERT_2026-10-20.md) ; verdict
conditionné à la CI du SHA exact consignée dans #85. HOLD matériel conservé.
Météo automatique déjà validée et firmware installé hors périmètre.


## 20 octobre — incrément 3 HOST B5.4/M3-R

Le handoff pré-body est importé comme overlay HOST source-épinglé dans
`experiments/link_m3r_b54_handoff`, sans remplacer `firmware/` ni importer
le firmware privé. Une seule Gate sous `httpBusy`, refus 503 même après
vérification, aucun writer d'écran. Les mesures HOST ne qualifient pas
ESP8266/heap/CONT. CI exacte requise pour le verdict final ; voir le
[rapport daté](B54_M3R_SOCKET_HANDOFF_IMPORT_2026-10-20.md) et le bilan #85.
La météo automatique déjà validée reste inchangée, hors périmètre.
Les checkpoints physiques et preuves historiques ci-dessous restent datés.


**Checkpoint actif — 19 octobre 2026, projet SHINO // TV / SHINO // LINK.**
**Source de coordination GitHub : branche `feature/link-m3r-unified-integration-20261019`, PR [#85](https://github.com/shinobione/SHINO-TV/pull/85) Draft.**
Cette page décrit des faits rapportés et vérifiés dans les commentaires de l'issue #81 et des états GitHub distincts. Elle ne remplace **ni** les BIN/manifeste/reçus privés **ni** une lecture physique nouvelle. Les SHA publics sont des commits, **pas** les empreintes du firmware installé.

## 1. État physique de référence — B5.4 après OTA

**OBSERVÉ/rapport Codex local, 19 octobre 2026 : `POSTBOOT_IDENTITY_B54_CONFIRMED`** ([rapport #81](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6275185762)).
Une seule opération logique GET de contrôle postboot a produit un challenge Digest 401 puis un GET authentifié 200, **2 GET réseau, 0 POST et 0 retry** pour cette vérification. Le lecteur a comparé les vrais champs `device`, `build_id`, `sha256`, `bytes`, protocole, descripteur et boot à **l'original privé B5.4**, manifeste et reçu recalculés/revérifiés. Taille du candidat / image identifiée : **431 920 octets**. `boot_id` changé depuis le prévol. Les empreintes et identités privées ne sont **pas** publiées ici.

Ce contrôle a suivi **une OTA réelle unique**, [staging explicitement accusé](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6274872177), puis un **premier diagnostic postboot expiré** et un arrêt `STOP_UNKNOWN_NO_RETRY`. La preuve GET ultérieure permet de conclure à l'identité B5.4 réellement démarrée. Elle **n'efface pas l'incident historique** ni la réservation OTA consommée.

| Sous-système | État au dernier rapport du 19 octobre | Portée |
| --- | --- | --- |
| Firmware exécuté | **P0+Updater512+B5.4 identifié** par GET Digest postboot et comparaison exacte aux preuves privées | **OBSERVÉ et rapporté par Codex local**, non relu par cette PR |
| LCD 240×240 | Quatre cartes de mesures, date et heure après reboot | **OBSERVÉ par le propriétaire**, pas par CI |
| SHINO // LINK installé | Télémétrie déclarée fraîche (`metrics_fresh=true`) ; quatre mesures observées visuellement | Fonctionnement complet, reconnexion et endurance **NON VÉRIFIÉS** |
| LittleFS | `fs_ok=true`, 24 fichiers, 181 402 octets | Champs de statut authentifiés ; intégrité complète du contenu **NON VÉRIFIÉE** |
| Route OTA du firmware | `ota_enabled=true`, `last_update=NONE` | Champs déclarés au GET ; **pas** une autorisation ni une preuve de future OTA |
| Météo B5.4 | Récepteur présent dans le chantier B5.4, rendu météo testé HOST sur PR #73 | Chaîne météo réelle sur appareil **NON QUALIFIÉE** |
| VM météo Freebox | VM **déjà installée et testée** selon propriétaire ; Open-Meteo HTTPS → VM → LAN → SmallTV | Publisher HMAC météo **rapporté OFF**, non relu ni activé |
| Modes M2 / M3-R et vérificateur Windows #83 | Travaux de laboratoire sur [PR #85](https://github.com/shinobione/SHINO-TV/pull/85) | **NON INSTALLÉS / NON ACTIVÉS** |

**Mesure mémoire ponctuelle postboot** issue du même GET : heap libre **28 168 o**, plus grand bloc **26 080 o**, CONT **2 180 o**, fragmentation **8 %**. Cela ne prouve pas la mémoire minimale en charge, le WDT, le risque de redémarrage ni la marge d'une future intégration. Aucun budget M3-R complet sur le B5.4 privé n'a été calculé.

## 2. Protections conservées malgré l'identité B5.4 confirmée

- Le reçu historique `STOP_UNKNOWN_NO_RETRY`, les réservations, tous les fichiers `.attempt`, les sauvegardes MASTER/VERIFY 4 MiB, les reçus et les secteurs LittleFS/SDK restent **intacts**, conformément à #81.
- Le GO OTA one-shot de l'issue #81 est **consommé**. **Aucune nouvelle OTA, flash, UART/COM, reboot, RTC, Wi-Fi, changement Freebox/VM, activation du publisher ni GET physique** n'est autorisé par ce checkpoint ou cette PR.
- Le GET postboot du 19 octobre est une **opération terminée**. Son accord n'autorise pas le bouton #83 à lire automatiquement, ni un retry.
- Les règles `4m2m`, HMAC, Digest, staging, identité, écran 240×240, quatre mesures CPU/GPU/RAM/GPU temp et retour sécurisé doivent être conservées. Vérifier les vrais offsets sur le BIN, le linker et les sources exacts avant toute opération risquée.

## 3. Un seul chantier de consolidation, plusieurs provenances préservées

**Branche unique de développement intégrateur :** `feature/link-m3r-unified-integration-20261019` / [PR #85](https://github.com/shinobione/SHINO-TV/pull/85), toujours **Draft**. Son ascendance contient M1/M2 et les laboratoires M3-A→Q ; les **12 fichiers exacts** du menu Windows issue #83 / PR #84 ont été importés dans #85. Un premier labo M3-R réutilise **un seul** `ShinoM3C::Gate` pour le chemin HMAC pré-body, en simulations HOST et compilations Xtensa **inertes**. Aucun listener productif ni commande d'écran n'est activé.

**Sources B5.4 distinctes, NON absorbées par #85 :** [#72 — revue publique](https://github.com/shinobione/SHINO-TV/pull/72), [#73 — tests météo/rendu 240×240](https://github.com/shinobione/SHINO-TV/pull/73), [#76 — politique Auto/Horloge-Météo](https://github.com/shinobione/SHINO-TV/pull/76). La correspondance entre leur arbre public assaini et le **BIN privé installé** est **NON VÉRIFIÉE par #85** ; les branches locales Codex et la copie Windows ne sont pas accessibles/synchronisées implicitement. Aucun cherry-pick ou merge implicite.

**Windows :** l'item « Vérifier le firmware du SmallTV… » fonctionne en HOST dans #85 et reprend le transport GET Digest borné ; l'EXE installé n'a pas été modifié. Le catalogue version↔identité n'est pas livré : seul un vrai couple BIN/manifeste local inspecté permet un nom B5.4, sinon afficher « Version inconnue ». La localisation de l'ensemble des marqueurs/réservations one-shot de l'OTA #81 et l'exclusion interprocessus avec le bouton #83 restent **HOLD avant distribution**.

Pour l'inventaire des PR, la matrice de dépendances et les critères de migration, voir **[SHINO_TV_LINK_UNIFICATION.md](SHINO_TV_LINK_UNIFICATION.md)**, puis [ROADMAP.md](ROADMAP.md) et [LINK_M3R_UNIFIED_BRANCH.md](LINK_M3R_UNIFIED_BRANCH.md).

## 4. Prochaine action unique (logiciel seulement)

**Établir la parité source et des routes entre le graphe B5.4 public, la provenance privée autorisée (contrôlée par Codex local), et le chemin M3-O/P→M3-C de #85 dans un laboratoire isolé.** Établir ensuite la preuve que les anciennes routes Digest/télémétrie/horloge/météo/OTA et l'écran 240×240 ne régressent pas et mesurer les ressources réelles du **candidat complet** avant toute décision physique. Conserver le menu Windows HOLD jusqu'à coordination avec l'état OTA réel et les reçus privés. Ne pas demander un nouveau flash ni activer la VM.

## 5. Traçabilité historique — à conserver, ne pas réinterpréter

La section suivante provient du checkpoint **antérieur à la preuve postboot B5.4** et reste archivée pour l'historique. Ses indications « P0 installé », « OTA non prouvée » et ses anciens GO ne sont **plus** l'état actif. Ne pas les réutiliser comme vérité présente.

---

## Archive documentaire antérieure à la preuve B5.4

**Checkpoint historique pré-confirmation B5.4 : 2026-10-19.** Ce document est un **journal de reprise**, pas une attestation matérielle ni un substitut à un BIN/manifeste/reçu. Le mettre à jour dès qu'une nouvelle preuve ou décision change une ligne. Les références locales et états physiques ci-dessous ont été rapportés dans les échanges propriétaires ; **GitHub ne les atteste pas**.

> **À lire avant toute mission** avec `AGENTS.md` et, sur les branches où ils existent, `docs/AGENT_HANDOFF.md` et `docs/ROADMAP.md`. L'état des fichiers sur `main` et les docs historiques peuvent être dépassés. La branche locale de Codex et l'appareil ne sont pas synchronisés automatiquement avec GitHub.

## 1. Acquis à préserver (dernier constat propriétaire : 18 octobre 2026)

| Sous-système | Dernier état constaté | Nature de preuve / limite |
| --- | --- | --- |
| SmallTV-Ultra ESP8266, flash 4 MiB, LCD 240×240 | P0+Updater512 installé par UART ; relecture intégrale postécriture vérifiée ; démarrage à froid, horloge et quatre cartes affichés | **OBSERVÉ sur appareil / rapports de relecture propriétaire**. N'implique pas qualification OTA ultérieure |
| SHINO // LINK Windows | CONNECTED, CPU/GPU/RAM/GPU temp évoluent sur l'écran | **OBSERVÉ par le propriétaire** après le dernier flash |
| Protection flash | Région hors image flashée rapportée identique à la sauvegarde de contrôle | **Rapport de comparaison physique propriétaire** ; conserver MASTER, VERIFY, reçus, LittleFS, SDK, marqueurs `.attempt` |
| Horloge | Affichée après redémarrage | **OBSERVÉ** ; cela ne prouve pas tous les scénarios de synchronisation/reconnexion |
| VM Freebox météo | **DÉJÀ INSTALLÉE ET TESTÉE** selon confirmation explicite du propriétaire ; chaîne Open-Meteo et service/cache/programmation ont fait l'objet de tests précédents | **Déclaration propriétaire**. Ne pas proposer de réinstaller, reconfigurer ni recréer cette VM |
| Publication météo signée de la VM vers l'appareil | Décrite comme volontairement **OFF** dans le dernier état transmis | **Dernier état rapporté, non relu en direct** ; ne pas activer sans accord distinct |

**Point crucial :** la météo passe par **Open-Meteo HTTPS → VM Freebox → LAN/Wi-Fi → SmallTV**, indépendamment du PC Windows. **Pas de HTTPS météo direct sur l'ESP8266.** La VM existante ne doit pas être redéployée dans le cadre de l'intégration B5.4.

## 2. Travail existant, NON équivalent à une fonctionnalité physique livrée

- **P0+Updater512 :** le binaire privé installé est distinct des branches GitHub publiques. Taille/empreinte, layout exact et reçus à lire **dans les véritables fichiers privés** avant nouvelle opération. Updater à tampon 512 octets présent dans le candidat installé, mais **aucune OTA post-P0+512 physiquement acceptée n'a été prouvée**.
- **B5.4 météo LAN :** branche de travail locale rapportée `codex/b54-lan-weather`, dernier HEAD *historique* rapporté `b242dbd4bffb5b97468c0f07d2ebc2f736557a45`. Récepteur météo signé `SHINO-WX/1`, SAMPLE 80 octets, publieur VM existant. Un candidat isolé a été préparé, **non installé**. Vérifier le HEAD et les sources actuels avant toute intégration.
- **Stabilisation P0 :** branche locale rapportée `codex/tv-stabilization-p0`, dernier HEAD *historique* rapporté `e78a95f7b30ba0a1b98a974daf9eca8ba6294907`. **Non synchronisée automatiquement avec GitHub**.
- **Mode control Windows / musique :** UX et plusieurs laboratoires HOST existent sur PR Draft séparées ; ne pas confondre prévisualisation/menu HOST avec contrôle natif déjà actif sur le SmallTV.
- **Diagnostics HTTP P0 :** tentative de lecture authentifiée terminée avec `UNEXPECTED_HTTP_STATUS` le 18 octobre. **Cause non établie ; aucun retry automatique**. L'identité HTTP courante et les minima mémoire physiques P0 restent **NON VÉRIFIÉS/HOLD**. Cet échec n'annule pas l'observation écran/LINK.

## 3. Décision propriétaire active et prochaine action

**GO logiciel donné le 19 octobre 2026 : intégrer B5.4 météo LAN dans P0+Updater512.** Périmètre précis :

1. Vérifier branches/HEAD/working trees actuels, PR et CI du SHA exact ; ne pas modifier la branche ou les travaux en cours d'un autre agent.
2. Créer une intégration **isolée, hors ligne** depuis les vraies sources privées locales ; conserver le système `4m2m`, HMAC P0, Updater512, Digest, télémétrie LINK, horloge, journal, LittleFS et OTA.
3. Résoudre les vrais conflits entre les générateurs/routes/guards et le contrat `SHINO-WX/1`. Vérifier intégrité et provenance ; ne pas élargir les listes de confiance ni affaiblir les seuils.
4. Compiler et tester le firmware combiné ; démontrer les budgets RAM statique, heap/bloc, CONT/stack, staging, ainsi que scénarios météo valide/expirée/absente/rejouée, LINK, Wi-Fi, OTA, LCD 240×240. **PASS HOST ≠ PASS appareil.**
5. Remettre code, artefacts exacts et compte rendu court avec **PASS / HOLD / NON VÉRIFIÉ**. Si un budget bloque, expliciter la mesure et proposer une correction ciblée.

**Hors autorisation :** flash, OTA, reboot, écriture UART/RTC/SDK/LittleFS, changement Wi-Fi du SmallTV, contact/déploiement/reconfiguration/activation HMAC sur la VM Freebox, suppression sauvegarde/marqueurs, push concurrent ou merge. Toute opération matérielle ou distante réelle requiert un accord nouveau pour l'opération exacte.

**Produit demandé :** quatre cartes permanentes **CPU, GPU, RAM, GPU temp** (libellés sur une ligne) quand LINK transmet ; horloge/météo autonomes lorsque le PC est éteint ; futur menu SHINO LINK Automatique / Horloge-Météo / Monitoring / Musique, puis pochette, artiste, titre et progression. Ne pas confondre un objectif UI et une fonctionnalité déjà déployée.

## 4. Protocole anti-oubli — obligatoire pour assistants et agents

1. **D'abord lire ce checkpoint**, `AGENTS.md`, les documents techniques applicables et les vraies sources. Avant de demander au propriétaire « la VM existe-t-elle ? », lire la section 1 : **oui, elle existe et a été testée**.
2. **Réconcilier quatre réalités** : (a) dépôt GitHub/PR, (b) worktree Windows local, (c) artefact BIN/manifeste/reçu, (d) appareil et VM réels. Ne jamais inférer l'un des trois autres depuis un seul.
3. **Marquer les preuves à chaque affirmation :** `PROUVÉ FICHIER`, `OBSERVÉ PROPRIÉTAIRE`, `TEST HOST/SIMULÉ`, `HYPOTHÈSE`, `HOLD/NON VÉRIFIÉ`. Les anciens HEAD et chiffres restent des repères historiques jusqu'à relecture.
4. **Une seule prochaine action concrète.** Pas de réaudit complet, seconde VM, nouvelle architecture, tutoriel PowerShell improvisé ou séries de tests sans lien avec le blocage. L'assistant vérifie lui-même ce qui est automatisable.
5. **En cas de désaccord**, vérifier les fichiers et preuves courants, consigner ce qui a changé et corriger cette page. N'effacer jamais un acquis prouvé au seul motif qu'un vieux README ou une autre branche dit le contraire.
6. **À chaque jalon**, mettre à jour date, acquisition, preuve/portée, blocages et prochain travail. Le statut humain ou matériel est un constat daté, pas une télémétrie continue.

## 5. Sources et limites du checkpoint

- Constat utilisateur et reçus privés de l'installation physique P0+Updater512 du **18 octobre 2026** : hors GitHub, non réexaminés par cette PR.
- Confirmation directe du propriétaire que la VM Freebox est **déjà installée et testée** et GO de l'intégration **19 octobre 2026**.
- Rapports d'intégration locaux P0/B5.4 de **18 octobre 2026** ; ne prouvent pas les HEAD actuels.
- Sur GitHub, les PR Draft historiques autour de l'OTA et SHINO LINK restent distinctes du firmware installé, notamment **#42** et **#68**. La branche `main` de GitHub avait encore un README **Phase 0** au checkpoint. Cette PR documentaire ne synchronise ni le code local ni l'appareil.

**Ne pas publier de secrets, fichiers propriétaires, identifiants réseau privés, clés météo/HMAC, dumps, reçus privés ou BIN spécifiques à l'appareil dans ce document public.**
