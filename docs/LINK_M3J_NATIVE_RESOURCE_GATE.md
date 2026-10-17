# SHINO // LINK — M3-J : coût natif Xtensa, avant toute migration du port 80

**17 octobre 2026 — GO propriétaire logiciel hors ligne uniquement.**
Base PR #64 M3-I à `8b6eaf9bf0fee744e06580e5c71b921a9fb7c2db` :
**12/12 CI PASS** vérifiés au fork. PR empilée / Draft, aucun merge.

## Pourquoi M3-J change le critère de progression

M3-I a validé l'authentification HMAC-SHA256 pré-corps et les vraies
routes historiques Digest / `FslessMetrics.cpp` sur **un même socket
Linux POSIX**, mais rien de cela n'est encore le serveur ESP8266.

Sur le véritable firmware B5.3, `FirstBootBridge.cpp` possède un
`ESP8266WebServer server(80)` avec listener privé et handlers
enregistrés par `server.on` et `HomeLan::registerRoutes`.
Aucune méthode source vérifiée ne permet de céder en sécurité une
connexion partiellement lue à ce serveur. Le chemin POST hérité
utilise également une lecture bornée de corps **avant** son Digest,
ce qui ne convient pas pour une commande M3-C qui doit être
authentifiée avant **tout octet** de corps.

M3-J **ne branche donc pas un second serveur**, ne modifie pas
`FirstBootBridge` et ne simule pas la parité de ses handlers.
Il mesure d'abord le **coût réel de code généré** sur le vrai
toolchain Xtensa ESP8266 Core 3.1.2, avec une comparaison contrôlée.

## Deux exécutables de laboratoire Xtensa, jamais à installer

`experiments/link_m3j_native/platformio.ini` définit deux environnements
avec **même ESP8266 Platform 4.2.1, Core 3.1.2, ArduinoJson 7.4.3,
linker `eagle.flash.4m2m.ld`** et options de compilation :

- **A — `m3j_inert_baseline`** : vrai `FslessMetrics.cpp` B5.3
  inchangé compilé, `FslessMetrics::describe`, véritable
  `HomeLanPolicy::endpoint`, Core `WiFiServer` construit mais
  jamais démarré.
- **B — `m3j_inert_m3_gate`** : **même A**, plus le véritable
  `ShinoM3F::SinglePortPump<WiFiServer,WiFiClient,BearSslCrypto>`,
  le moteur M3-C HMAC/SHA256 pré-corps et ses buffers statiques
  (issus de M3-F), **retenus au linkage** par un test volatile
  toujours désactivé.

Les deux programmes ont des `setup()` vides et des `loop()`
qui n'appellent jamais les probes dans l'exécution normale.
`WiFiServer.begin()`, `WiFi.begin()`, `WiFi.mode()`, SDK
Wi-Fi, OTA, LittleFS, écoute port 80, LCD et RTC ne sont
pas invoqués. Les identifiants HMAC sont des **vecteurs de test
publics**, non une vraie clé ni un candidat firmware.

## Preuves automatiques fournies

Au **HEAD exact** de la PR, la CI M3-J doit :

1. Vérifier les blobs Git exacts `FirstBootBridge.cpp`,
   `HomeLan.cpp`, `HomeLanPolicy.h`, `FslessMetrics.cpp`
   et leur comportement attendu selon les tests existants.
2. Compiler/éditer **les deux vrais ELF Xtensa** ; vérifier
   que `m3j_baseline_probe` est conservé dans les deux
   symbol tables, `m3j_crypto_probe` seulement dans B.
   Ainsi la comparaison ne porte pas sur un code cryptographique
   éliminé par l'optimiseur.
3. Extraire automatiquement **text, data, bss, tailles/empreintes
   SHA-256 des BIN inertes** à partir des vrais fichiers produits.
   Rapporter **B moins A**, non une empreinte mémoire SHINO produit.
4. Relever les informations disponibles de `-fstack-usage`
   et les frames associées aux fonctions M3 et sondes, avec
   `NOT MEASURED` pour les appels dynamiques et pics réels.
5. Réexécuter les tests HOST M3-F et les 26 scénarios M3-A.

Le reçu JSON exact est produit par
`experiments/link_m3j_native/report_resource_delta.py`.
**Aucun chiffre de taille/stack n'est anticipé ou copié depuis
un ancien build** ; seules les sorties CI au SHA final sont valides.

## Première mesure CI Xtensa (artefacts inertes uniquement)

La première exécution ciblée
[workflow M3-J #39068885963](https://github.com/shinobione/SHINO-TV/actions/runs/39068885963)
a terminé **SUCCESS sur deux jobs** au SHA antérieur de cette branche
`7a5228f966d48b7f1b3222748dfbc333cd3cf99f`.
Ce sont des **octets d'ELF/BIN produits par CI**, non des
valeurs recopiées depuis une illustration ni du firmware installé.
Le workflow doit être **rejoué sur le HEAD final** avant réception.

| Grandeur de programme inerte | A (code métriques original) | B (A + HMAC/Core natif) | B − A |
|---|---:|---:|---:|
| BIN dérivé | 259 760 octets | 276 544 octets | **+16 784 octets** |
| ELF `.text` | 254 111 octets | 270 895 octets | **+16 784 octets** |
| ELF `.bss` | 25 688 octets | 27 392 octets | **+1 704 octets** |
| ELF `.data` | 1 556 octets | 1 556 octets | 0 |

Dans les `.su` du vrai compilateur Xtensa, la frame statique
de `ShinoM3C::Gate::authenticateHeader<BearSslCrypto>` apparaît à
**992 octets**, et celle de `bodyByte<BearSslCrypto>` à
**352 octets**. Ces valeurs ne sont ni une mesure de pile CONT
en fonctionnement ni la somme des frames sur un chemin d'appel
complet. **Aucun maximum total de pile produit ne peut être
certifié par ces résultats.** La compilation PASS n'efface
pas l'ancien STOP/HOLD physique de B5.3.

L'artefact de CI `m3j-inert-xtensa-resource-delta` contient
les tailles et SHA calculés à partir des fichiers réellement
émis (binaire de laboratoire uniquement). Les hash ne sont pas
présentés ici comme des identités de firmware installé.
Ce surcoût indique que l'intégration **ne doit pas être activée**
sur la seule base d'une compilation ; réduction/profiling
de pile et contrôle d'ordonnanceur natif requis.

## Pourquoi le statut matériel ne peut PAS devenir GO

Le préflight physique B5.3 communiqué par le propriétaire a
observé une **CONT minimale de 2 128 octets pour un seuil
de 2 048 octets**, soit **80 octets de marge**, alors que les
piles SDK et les pointes ne sont pas toutes mesurées. Une
augmentation de frames compilateur n'est **pas additionnable
automatiquement** à cette mesure observée de continuation,
mais elle interdit de décréter une marge garantie sans
profil réel. Le préflight s'est terminé en STOP/HOLD.
M3-J ne contacte pas cet appareil et **ne clôt pas ce HOLD**.

Les deux ELF de comparaison ne contiennent **pas** le produit
B5.3 et ne relient **pas** les vraies routes de
`FirstBootBridge`/`HomeLan`, le renderer, les chemins
M8 media, HMAC propriétaire, Wi-Fi recovery, OTA, le journal
ni le scheduler temps réel. Un **PASS compilation**
ne prouve ni boot, ni heap libre / largest block, ni
CONT runtime, ni WDT, ni que l'utilisateur puisse changer
d'écran. Pas de clé de production, pas de vrai ACK/GET
d'état, pas de connexion HTTP au SmallTV.

## Décision et prochain jalon

**M3-J PASS ciblé = compabilité API native + mesures de codegen
Xtensa A/B**, **M3 produit = HOLD**, jusqu'à :

- une vraie stratégie de **remplacement unique** du serveur HTTP,
  incluant toutes les anciennes routes et authentifications, sans
  second listener ni passage POST M3 par l'ancien parseur ;
- vérification du budget RAM, pile et scheduler dans une **image
  de qualification complète**, fondée sur le bon firmware et
  non sur ces deux exécutables inertes ;
- preuve d'une voie de secours, continuité LINK/M8/OTA/LittleFS
  et approbation ultérieure du propriétaire sur un candidat exact.

SHINO LINK Windows installé, appareil, Freebox, météo, B5.4 Codex,
fichiers `firmware/` et `companion/` ne sont pas modifiés.
Aucun push concurrent sur branche Codex, aucune OTA/flash,
écriture SDK/FS, reboot ni changement de Wi-Fi.
