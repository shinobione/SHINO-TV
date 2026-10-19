# SHINO // TV — État opérationnel et décisions actives

**Checkpoint : 2026-10-19.** Ce document est un **journal de reprise**, pas une attestation matérielle ni un substitut à un BIN/manifeste/reçu. Le mettre à jour dès qu'une nouvelle preuve ou décision change une ligne. Les références locales et états physiques ci-dessous ont été rapportés dans les échanges propriétaires ; **GitHub ne les atteste pas**.

> **À lire avant toute mission** avec `AGENTS.md` et, sur les branches où ils existent, `docs/AGENT_HANDOFF.md` et `docs/ROADMAP.md`. L'état des fichiers sur `main` et les docs historiques peuvent être dépassés. La branche locale de Codex et l'appareil ne sont pas synchronisés automatiquement avec GitHub.

## Source de vérité GitHub / Windows — export source vérifié le 19 octobre 2026

**PR source canonique : [Draft #72](https://github.com/shinobione/SHINO-TV/pull/72).**
HEAD GitHub relu : `91969aceb45e0c43d44f93a702a3997b57e8f89e`.
Base : `main`, `8425dd7f2526c29e6c53b4294909a4bf03d3112f`.
445 fichiers : graphe source applicatif combiné, Core HTTP/Updater512/linker,
laboratoire HOST complet, protocole/publieur et dépendances source non secrètes.
Voir [le guide de lecture](https://github.com/shinobione/SHINO-TV/blob/91969aceb45e0c43d44f93a702a3997b57e8f89e/review/README.md)
et [la provenance publique/privée](https://github.com/shinobione/SHINO-TV/blob/91969aceb45e0c43d44f93a702a3997b57e8f89e/review/PROVENANCE.md).

**PROUVÉ GITHUB :** HEAD/arbre complet et445 fichiers/deltas vérifiés après push.
443 patches identiques ;2 patches volumineux vérifiés par lecture complète des
sources. L'endpoint diff global limite à300 fichiers ; API paginée et arbre complet
permettent la revue de l'ensemble. Sources clés lues directement depuis GitHub.

**TEST HOST/CI :**41 tests PASS,0 FAIL/ERROR/SKIPPED, sur ce SHA exact :
[run push](https://github.com/shinobione/SHINO-TV/actions/runs/39175173484),
[run PR](https://github.com/shinobione/SHINO-TV/actions/runs/39175222820).
Reproduction autonome : `python3 -B review/run_tests.py`, Python standard + GCC/G++
C++20 ou MSVC ; réseau127.0.0.1 seulement, flash/RTC/radio/SNTP/LCD simulés.

**PROVENANCE / CONFIDENTIALITÉ :** export allowlisté à nouvelle histoire depuis
la base publique, pas les commits privés. Audit local de tous les objets poussables,
y compris historique ; identités/clefs/localisation privées remplacées par fixtures
HOST explicitement interdites sur ESP8266. Correspondance vers la source compilée
conservée dans un reçu privé local. Aucun BIN/ELF/manifeste/reçu/dump/clé/identité
matérielle/marqueur privé publié ; aucune équivalence binaire privé/public annoncée.
Anciens guards et branches/worktrees/artefacts privés intacts.

**ÉTAT : PUBLICATION SOURCE VÉRIFIÉE.** La mise à jour du checkpoint main est
proposée par cette Draft #70, encore NON MERGÉE : ne pas annoncer PASS_SYNC global
au sens du critère « main documente la PR » avant sa revue/acceptation propriétaire.
Le firmware installé reste P0+Updater512 (OBSERVÉ PROPRIÉTAIRE), B5.4 NON INSTALLÉ,
VM existante déjà installée/testée et publication signée rapportée OFF.
Aucun contact appareil/VM, flash, OTA, UART, reboot, déploiement ou merge.
**REVUE DU CODE SOURCE GITHUB #72 EFFECTUÉE le 19 octobre 2026 :** [revue propriétaire sur le HEAD exact](https://github.com/shinobione/SHINO-TV/pull/72) déposée en commentaire GitHub ; publication/consultabilité source **PASS dans la portée HOST**. Le chemin source météo → `B52Clock::setWeather()` → `ArtworkPilot::Renderer` → Canvas LCD existe et gère frais/périmé. **PROGRÈS PRODUIT 19/10 : [PR Draft #73](https://github.com/shinobione/SHINO-TV/pull/73), HEAD `5ad551b12f850b6f88056f89340ff3dbeb073db0`** : test C++ ajouté au vrai `ArtworkPilot::Renderer` (Canvas espion 240×240), depuis un `B54LanWeather::Receiver` ayant accepté un SAMPLE signé, avec température/condition, quatre cartes lorsque LINK est actif, mode autonome PC absent, météo expirée et absente. **CI PR #73 SUCCESS** : [run #39176636215](https://github.com/shinobione/SHINO-TV/actions/runs/39176636215), marqueur `B54_WEATHER_RENDER_HOST_PASS`, 41 tests Python existants PASS. Test HOST du récepteur → renderer **PASS** ; **ne prouve pas** une requête HTTP à travers l'adaptateur LCD ST7789 physique, ni l'identité du BIN privé. **HOLD** : heap/CONT/OTA/récupération physiques et communication VM réelle. **NOUVEAU JALON HOST le 19/10 : [PR #73](https://github.com/shinobione/SHINO-TV/pull/73), HEAD `13d5d4f830f38c51b5cf0e31ffb6f4936333a89a`.** Le test a été étendu au **POST HTTP réel du labo combiné → B54LanNative → B52Clock → commandes du faux pilote GFX LCD**, couvrant météo `18.2`/`Cloudy`, fin de validité, quatre cartes LINK et météo sans PC. **CI [#39211310461](https://github.com/shinobione/SHINO-TV/actions/runs/39211310461) PASS : 43 tests, 0 FAIL/ERROR/SKIP**, nouveaux tests `test_http_signed_weather_reaches_lcd_when_pc_off` et `test_http_weather_and_link_share_actual_lcd` confirmés dans le log. Cela remplace l'ancien HOLD *sur le chemin HTTP→commandes LCD HOST*, mais **ne prouve toujours pas les pixels ST7789 physiques, le BIN privé ni la mémoire réelle**. **GARDE MÉMOIRE HOST AJOUTÉE (19/10) : [PR #73](https://github.com/shinobione/SHINO-TV/pull/73) HEAD `4d2a1b7b585fc51b9b496a408b379f9d09f0425b`, [CI #39212722944](https://github.com/shinobione/SHINO-TV/actions/runs/39212722944) PASS : 47 tests, 0 FAIL/ERROR/SKIP.** Quatre nouveaux tests injectent une ressource synthétique juste hors des seuils existants (heap 20479, bloc 16383, CONT 2044, fragmentation 26 %). Le handler météo réel du labo répond 503 avant réception et les tests constatent zéro écriture flash/SDK, zéro redémarrage et zéro valeur météo rendue. **Il s'agit de tests HOST de refus**, PAS de valeurs mesurées sur l'ESP8266. **Prochaine action : Codex local doit rejouer les régressions de #73 sur les vraies sources privées combinées et fournir la vérification mémoire/récupération du candidat exact avant toute décision matérielle.** La PR #70 reste non fusionnée et `main` inchangé.

**QUALIFICATION PRIVÉE #74 TERMINÉE — PASS_OFFLINE_PRIVÉ RAPPORTÉ PAR CODEX (19/10)** : [rapport local expurgé](https://github.com/shinobione/SHINO-TV/issues/74#issuecomment-6262136717), [revue propriétaire](https://github.com/shinobione/SHINO-TV/issues/74#issuecomment-6262221714). Codex déclare un seul BIN privé déjà construit, sans rebuild, **56 tests unitaires distincts PASS**, plus 69 cas HTTP, 6 Core/eboot, 2 interruptions OTA, 2 exécutables natifs PASS dans leurs périmètres respectifs (ne pas les additionner). Mesures recomptées **PAR CODEX DEPUIS LES FICHIERS PRIVÉS** : BIN 431920 octets (+5136), RAM statique 47964 (+460), IRAM 28175, sous-chemin OTA suivi 1152 ; pas de contrôle indépendant des octets privés depuis GitHub. Source réellement compilée rapportée `2c7d50c99ab3f6b95fedfcda7aedbb0c28829f79`; HEAD local documentaire postérieur. **La CI publique #73 est un test distinct et n'atteste pas le BIN privé.**

**GATE DE RÉCUPÉRATION EN COURS (19 octobre 2026) : [issue #75](https://github.com/shinobione/SHINO-TV/issues/75).** Revue statique locale du lanceur UART et de son **profil P0+Updater512 déjà allowlisté**, en scénario de firmware courant non bootable, sans port COM, aucune ouverture/appel flash, aucun contournement ni nouvelle autorisation B5.4. La revue propriétaire #74 a confirmé le blocage pour installer le **nouveau** BIN par cet exécuteur ; elle n'a pas démontré la récupération P0 après non-boot. **En attente du constat Codex local, aucune validation physique ni modification des sauvegardes/profils.**

**DÉCISION RÉCUPÉRATION :** l'exécuteur UART allowlisté refuse le *nouveau* combiné B5.4, mais cela ne signifie pas que restaurer **P0+Updater512 connu (profil déjà autorisé)** soit impossible. **À VÉRIFIER SANS COM/ÉCRITURE** sur le vrai code local : profil P0, validation d'un appareil en non-boot/état courant inconnu, récupération des backups/reçus/layout et protections LittleFS/SDK. Ne pas ajouter B5.4 à l'allowlist pour contourner ce STOP ; **retour à P0 non prouvé**, et app-only insuffisant si partitions protégées endommagées. **HOLD physique** heap/CONT/SDK/IRQ/WDT, OTA postboot, LCD réel, liaison VM→SmallTV et récupération. Aucun GO matériel, flash, OTA, UART ou activation du publisher VM. **Prochaine action unique : inspection statique/à blanc du chemin de restauration vers P0+Updater512 exact, sans contact matériel.**

## Validation OTA HOST — pannes Core et absence de commit (19 octobre 2026)

**PR Draft [#73](https://github.com/shinobione/SHINO-TV/pull/73) au HEAD `2fdb5c26545995018810affd8ca576bcf37a0c78` :** [CI #39213407800](https://github.com/shinobione/SHINO-TV/actions/runs/39213407800) **PASS, 50 tests Python, zéro FAIL/ERROR/SKIPPED**. Trois tests nouvellement ajoutés injectent dans le vrai Core HOST une panne d'effacement, d'écriture ou de relecture du staging. Le serveur combiné refuse le transfert (`422`), et les assertions montrent **aucune commande eboot RTC, aucun redémarrage, secteurs LittleFS/SDK simulés inchangés**. Le scénario positif conserve le commit RTC attendu. Aucune écriture sur l'appareil.

**Portée : HOST uniquement.** Ces contrôles ne qualifient pas un boot post-installation, un rollback automatique inexistant, la mémoire physique, les marqueurs locaux privés ou la voie de récupération UART. Le candidat combiné privé n'est pas synchronisé en BIN avec la branche publique. **Prochaine action distincte : relecture locale privée du candidat/reçu/layout + plan d'installation/récupération exact et mesures RAM/CONT sur le SmallTV avec un GO physique séparé**. Ne pas demander de retry OTA en cas de doute.

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
