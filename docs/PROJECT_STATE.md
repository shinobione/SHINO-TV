# SHINO // TV — État opérationnel et décisions actives

**Checkpoint : 2026-10-19.** Ce document est un **journal de reprise**, pas une attestation matérielle ni un substitut à un BIN/manifeste/reçu. Le mettre à jour dès qu'une nouvelle preuve ou décision change une ligne. Les références locales et états physiques ci-dessous ont été rapportés dans les échanges propriétaires ; **GitHub ne les atteste pas**.

> **À lire avant toute mission** avec `AGENTS.md` et, sur les branches où ils existent, `docs/AGENT_HANDOFF.md` et `docs/ROADMAP.md`. L'état des fichiers sur `main` et les docs historiques peuvent être dépassés. La branche locale de Codex et l'appareil ne sont pas synchronisés automatiquement avec GitHub.

## Source de vérité GitHub / Windows — publication en cours

**Mission de synchronisation ouverte : [issue #71](https://github.com/shinobione/SHINO-TV/issues/71).** Lire [SOURCE_SYNC_POLICY.md](SOURCE_SYNC_POLICY.md). Le code local combiné P0+512/B5.4 reste **NON CONSULTABLE sur GitHub**, tant qu'une PR Draft source ne contient pas un HEAD distant relu, les sources et tests partageables et une provenance expurgée. Le rapport privé `DECISION.md` est utile mais n'autorise aucune assertion sur un code distant absent.

La décision du propriétaire autorise la **synchronisation du code source non secret vers une PR Draft après audit du contenu et de tout l'historique poussable**, pas la publication de BIN/ELF/reçus/identifiants, ni la fusion des branches, ni des actes matériels. Les branches P0, B5.4 et intégration restent préservées. **Ne pas déclarer PASS_SYNC avant preuve du HEAD GitHub et lecture de son diff.**

## 0. Dernière livraison : combinaison B5.4 + P0+512 (19 octobre 2026)

**Rapport Codex et dossier de décision fournis par le propriétaire** : `PASS_OFFLINE` pour compilation/intégration, tests HTTP/LINK/OTA simulée et réception météo. Le compte rendu annonce un **seul candidat privé combiné** avec un écart de **+5 136 octets BIN** et **+460 octets RAM statique** par rapport à P0+512, sans modification IRAM ou du sous-chemin OTA suivi. Les tests rapportés sont **69 HTTP + 9 météo intégrés + 6 Core/eboot + 2 interruptions OTA**, et les tests de provenance/publieur complémentaires. **Aucune relecture indépendante du BIN/ELF ou des logs locaux dans cette PR.** `PASS_OFFLINE` n'est pas un GO physique.

**HOLD** : heap/CONT/SDK/IRQ physiques, comportement et récupération après flash, réception effective depuis la VM, affichage météo réel sur ST7789, voie UART autorisée pour ce candidat. **Le fichier local Codex `DECISION.md` dit encore à tort « B5.3 installé / buffer 4096 » : c'est P0+Updater512 qui est actuellement installé d'après les essais propriétaires.** Corriger ce constat dans le travail Codex sans changer le firmware.

**Prochaine action prioritaire :** conclure une revue ciblée du chemin *trame météo acceptée → valeur rendue sur LCD* et du dossier de récupération/mémoire, avant toute demande séparée d'autorisation d'installation. Ne pas reconstruire la VM `SHINO-WEATHER`, déjà installée/testée ; publication HMAC toujours OFF selon dernier constat.

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
- **B5.4 météo LAN :** branche source locale `codex/b54-lan-weather`, HEAD de départ **rapporté** `b242dbd4bffb5b97468c0f07d2ebc2f736557a45`. Récepteur `SHINO-WX/1` et publieur VM existants. **Nouveau candidat combiné P0+Updater512+B5.4 produit hors ligne le 19/10**, non installé ; source compilée **rapportée** `2c7d50c99ab3f6b95fedfcda7aedbb0c28829f79` sur `codex/p0-512-b54-integration` (commit absent du GitHub distant au contrôle). Artefacts et reçu demeurent locaux privés. Voir [revue du candidat](B54_P0_REVIEW_2026-10-19.md).
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
