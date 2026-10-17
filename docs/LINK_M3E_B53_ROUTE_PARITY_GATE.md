# SHINO // LINK — M3-E, inventaire B5.3 du port HTTP unique (17 octobre 2026)

**GO propriétaire : poursuivre M3-E en logiciel hors ligne.**
**Statut : code C++ route-classifier HOST/Xtensa inerte ; migration serveur réelle HOLD.**
**Base : M3-D PR #59** à `9547135bd8144bcb93cce232c5f983fdcb964a06`.

## Correction de contexte essentielle

Le serveur StageA `M9NormalStageA.cpp` étudié pendant M3-B/M3-C
ne représente pas le serveur produit B5.3. Dans le graphe
B5.3 LEAN et B5.3 autonomous inspecté, les fichiers à préserver
sont **`firmware/src/boot/FirstBootBridge.cpp`** et
**`firmware/src/boot/HomeLan.cpp`**, ainsi que la liste d'accès
réseau **`firmware/include/boot/HomeLanPolicy.h`**.
Les trois blobs source sont identiques sur les deux branches B5.3
et la base M3-D au moment de cet audit. Cette égalité de source ne
prouve **pas** le firmware physiquement installé.

`test_b53_source_pins.py` impose les identités Git-blob des trois
fichiers observés et extrait/exige **l'ensemble des appels
`server.on(...)` et `s.on(...)`** dans ces sources :
aucune route supplémentaire non révisée ne doit passer silencieusement.

## Matrice exacte des routes déclarées — SOURCE uniquement

| Méthode | Cible | Contrainte d'enregistrement / réseau |
| --- | --- | --- |
| GET | `/`, `/ui.js` | navigateur et session de lecture |
| GET/POST | `/api/v1/bridge/metrics` | 4 mesures ; POST authentifié, RAM-only |
| GET | `/api/v1/bridge/status` | diagnostics |
| GET | `/api/v1/bridge/fs-plan` | GET sur AP seulement selon politique LAN |
| GET | `/api/v1/bridge/ota/capabilities` | **lecture seule**, aucune route OTA write |
| GET | `/api/v1/bridge/factory-return` | statut constructeur, accès protégé |
| POST | `/api/v1/bridge/factory-return` | **uniquement** `SHINO_ENABLE_FACTORY_RESTORE`, voie OEM critique |
| GET | `/api/v1/m9/fs-probe/status` | uniquement `SHINO_BOOT_PROFILE == 2` |
| POST | `/api/v1/bridge/wifi/recovery` | uniquement `SHINO_ENABLE_HOME_LAN`, Digest et politique réseau |
| GET | `/api/v1/bridge/wifi/intent` | uniquement HOME_LAN, **AP seulement** |
| POST | `/api/v1/bridge/wifi` | uniquement HOME_LAN, **AP seulement**, 99 octets et intent |
| POST | `/api/v1/display/mode` | **PROPOSÉ M3 — non enregistré** |
| GET | `/api/v1/display/capabilities`, `/api/v1/display/status` | **PROPOSÉS M3 — non enregistrés** |

Le fichier `HomeLanPolicy.h::endpoint(ap, path)` admet côté
**STA/LAN seulement** : `/`, `/ui.js`,
`/api/v1/bridge/metrics`, `/api/v1/bridge/status`,
`/api/v1/bridge/wifi/recovery`,
`/api/v1/bridge/ota/capabilities`.
**La nouvelle route M3 n'y figure pas** : un M3 déployé sur le LAN
serait actuellement rejeté en amont. Toute modification ultérieure
de la politique réseau devra être explicite et couverte par tests
AP/STA, IP locale, Host/Origin, Digest et protections de clé.

## Composant livré

`experiments/link_m3e_legacy/M3ELegacyRouteGate.h` : un inventaire
pur C++ de la cible, méthode, drapeaux de compilation et AP/STA.
Il classe les routes historiques, les réservations OTA interdites
et les futurs chemins M3 ; il rejette les alias, chemins inattendus,
queries, encodages suspects et méthodes non listées.

**Invariance absolue :**
`Classification.allowedToDispatch == false` **pour chaque route**.
Le composant ne contient pas de serveur ni de handler, et les tests
n'appellent aucun endpoint vrai. Il n'est donc ni une réimplémentation
du serveur B5.3, ni une authentification, ni une parité d'exécution.

Les tests C++ HOST vérifient le contenu de l'inventaire et les
gates AP/STA/Factory/FS-probe, l'interdiction des routes OTA write
et la non-exécution de toute commande. Un programme ESP8266 isolé
`experiments/link_m3e_legacy/platformio.ini` compile et lie
le classifieur avec Core 3.1.2, linker 4m2m ; **ce BIN est inerte
et ne doit jamais être installé**. Pas de second listener et
aucun appel à `server.begin` ou à `WiFiClient` dans ces nouveaux fichiers.

## Portée de CI et HOLD

| Gate | État M3-E |
| --- | --- |
| Identité exacte des trois sources B5.3, collection des routes | À confirmer CI |
| Classifieur pur C++ route/méthode/flags/AP/STA, aucun dispatch | À confirmer CI |
| Build/link Xtensa du classifieur isolé | À confirmer CI |
| Compatibilité effective des GET dashboard et POST télémétrie | **HOLD — aucune délégation** |
| Session navigateur vs Digest POST, auth avant corps | **HOLD** |
| Un vrai propriétaire unique du port 80 avec légacys | **HOLD** |
| Équité metrics 2 s / TTL 6 s en charge mixte | **HOLD** |
| Client dédié M3-D half-close sur ESP8266/lwIP | **HOLD** |
| Provisionnement de clé, boot/nonce, CAS atomique | **HOLD** |
| Heap/largest block/stack/WDT sur image SHINO réelle | **HOLD** |
| Météo B5.4 Codex et scénarios 240×240 | **HOLD séparé** |
| Appareil, OTA, LittleFS, Wi-Fi physique | **AUCUNE INTERVENTION** |

**Prochaine action sûre :** M3-F devra d'abord apporter une vraie
stratégie **de passage à un propriétaire unique du port**, puis
tester un chemin de GET/POST hérités avec les mêmes auth/états
et le contrôle M3 dans **le vrai graphe natif hors ligne**.
La seule identité source ne peut remplacer un test de parité et
un fichier compilé ne démontre ni boot ni bonne allocation mémoire.
Coordonner les modifications réseau avec Codex et ne pas toucher à
B5.3 en fonctionnement sans accord ultérieur sur candidat exact.
