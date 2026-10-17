# Matrice des preuves — GeekMagic OEM V9.0.44 / V9.0.50

**Dernière consolidation : 2026-10-16** · **Lecture seule** · Ce fichier n'est ni une spécification de firmware installable, ni une preuve de fonctionnement matériel.

Ce document est l'annexe technique de [README.md](README.md). Chaque adresse ci-dessous est une **adresse virtuelle Xtensa ou un offset de fichier** explicitement qualifié. Une correspondance de pointeur ne prouve pas que le programme utilise une route ni qu'il appelle sa routine candidate.

## A. Acquisition et intégrité des archives officielles

| Valeur recalculée / observée sur les octets publics | V9.0.44 | V9.0.50 |
|---|---|---|
| Git constructeur | [commit 55d7877…](https://github.com/GeekMagicClock/smalltv-ultra/tree/55d7877fcba8b1cb7a66a0830d35d5b374bc8540) | [commit f7c8874…](https://github.com/GeekMagicClock/smalltv-ultra/tree/f7c887403a6ee1278efdb97bf4bbd3d7a791e9bd) |
| Archive | `Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip` | `Ultra-V9.0.50/FW-Smalltv-Ultra-V9.0.50.zip` |
| Git blob SHA **(pas SHA-256)** du ZIP | `a829d48766cbd2f4f62656523cc9646ba67017d3` | `52703938d3da105ad481d49e158e8eb9e43a4f55` |
| ZIP octets | **349 377** | **364 219** |
| SHA-256 ZIP calculé | `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f` | `83d051569465937feeaf12f19a8c45aada68e530809ad1801ebdcccda8fbe6ef` |
| Fichier BIN contenu | `FW-Smalltv-Ultra-V9.0.44.bin` | `FW-Smalltv-Ultra-V9.0.50.bin` |
| BIN octets (DEFLATE) | **494 144** | **505 200** |
| SHA-256 BIN calculé | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` | `a40e79eb3ff557acb8e55c7114faa8e64c82974030a54328ffc21adb75c9d32e` |
| CRC32 BIN du répertoire ZIP | `0xE3A25EDB` | `0x06DA984D` |
| CRC32 ZIP vérifié à l'extraction | **PASS** | **PASS** |

La V9.0.44 correspond au [manifeste historique déjà présent dans SHINO](../../../recovery/factory_ota_v9_0_44.json). Le paquet V9.0.50 contient aussi `md5sum.txt` (76 octets extraits) ; ne pas confondre ce fichier de distribution avec la vérification interne du firmware. **Ces BIN sont des applications OTA et non une sauvegarde complète de flash 4 MiB.**

**Méthode :** ZIP reçus depuis le connecteur GitHub ; contenu DEFLATE décodé **en mémoire** ; CRC32 membre validé ; SHA-256 recalculé sur ZIP et BIN. Une copie des octets OEM n'est **pas** publiée dans ce dépôt. Le conteneur de ce chat ne contenait pas de sauvegarde constructeur brute complète.

## B. Images ESP8266 et contrôles internes

| Champ | V9.0.44 | V9.0.50 |
|---|---:|---:|
| En-tête externe `0xE9` au fichier | `0x00000000` | `0x00000000` |
| Segments externes | 2 | 2 |
| Entrée externe | `0x4010F480` | `0x4010F480` |
| Checksum externe calculé / inscrit | `0x2B / 0x2B` | `0x2B / 0x2B` |
| En-tête interne `0xE9` au fichier | `0x00001000` | `0x00001000` |
| Segments internes | 5 | 5 |
| Entrée interne | `0x401000C0` | `0x401000C0` |
| Segment IROM commence à l'adresse | `0x40201010` | `0x40201010` |
| IROM octets | 454 832 | 465 820 |
| Taille déclarée LE à `0x1010` | 494 144 | 505 200 |
| CRC interne déclaré LE à `0x1014` | `0x64EFC000` | `0x5072FF7E` |
| CRC interne recalculé | `0x64EFC000` — **PASS** | `0x5072FF7E` — **PASS** |
| Checksum XOR de l'image interne corrigé | `0x67` — **PASS** | `0x3E` — **PASS** |

**Algorithme CRC trouvé :** polynôme non réfléchi `0x04C11DB7`, valeur initiale `0xFFFFFFFF`, **pas** de XOR final ; les huit octets `[0x1010, 0x1018)` sont traités comme zéro pendant le calcul. Le checksum XOR interne initialisé à `0xEF` neutralise la **même** plage pendant son parcours des segments. C'est ce détail qui expliquait les échecs du premier calcul naïf.

Sur V9.0.44 : XOR naïf `0xE1` contre checksum OEM `0x67` ; après neutralisation `0x67`. Sur V9.0.50 : naïf `0x5F` contre `0x3E` ; après neutralisation `0x3E`. Le contrôle CRC et le checksum de segments sont **deux mécanismes différents**.

**Interprétation :** intégrité accidentelle, pas preuve de signature/autorisation cryptographique ni de vérification effective lors d'un upload constructeur. Le schéma de validation est également présent dans le [validateur SHINO M9](https://github.com/shinobione/SHINO-TV/blob/542a8d744a6932c6e7a3e2128a8674ca55cc7e8c/ota/firmware/ShinoHttpOta.h), qui ajoute d'autres vérifications ; sa qualification physique est distincte.

## C. Routes, chaînes et pointeurs candidats

Les chaînes ci-dessous sont **présentes dans les BIN officiels**. Le pointeur IROM immédiatement associé dans la table de données **suggère** un gestionnaire. Les valeurs ne démontrent pas le graphe d'exécution.

| Chaîne | Offset de la chaîne V44 | Offset de référence V44 | Code IROM **candidat** V44 | Code IROM **candidat** V50 |
|---|---|---|---|---|
| `/doUpload` | `0x6E980` | `0x1142C` | `0x40211F68` | `0x40212758` |
| `/wifisave` | `0x6E9A8` | `0x1140C` | `0x402127DC` | `0x4021303C` |
| `/wifi.json` | `0x6E9C8` | `0x113EC` | `0x40212890` | `0x402130F0` |
| `/space.json` | `0x6E9B4` | `0x11404` | `0x402125A8` | `0x40212E08` |

Chaîne `/update` : offset fichier `0x7821C` (V44) ; dans un segment DRAM à adresse calculée `0x3FFE90AD`, référence relevée dans le fichier à `0x11440`. **NE PAS déduire que le pointeur précédent est l'OTA, ni identifier un callback `/update` sans autre désassemblage.**

Autres indices statiques communs : `/ntp.json`, `/rotation.json`, `/app.json`, `/config.json`, `/theme_list.json`, `Update Success`, `Unauthenticated Update`, `Not Enough Space`, `MD5 verification failed`, `Flash Erase Failed`, formulaire HTTP `firmware`. `/tz.json` apparaît en V9.0.50 ; la note OEM V9.0.50 mentionne précisément le mode manuel/auto de fuseau et le correctif DST. L'existence d'une chaîne ne garantit ni l'accès à la route ni le comportement de son handler.

Les **24 premiers octets** des fenêtres candidates ont été comparés entre versions :

| Candidat | Octets identiques V44 vs V50 | Portée |
|---|---:|---|
| `/doUpload` | 20/24 | Préfixe seulement |
| `/wifisave` | 21/24 | Préfixe seulement |
| `/wifi.json` | 24/24 | Préfixe seulement |
| `/space.json` | 21/24 | Préfixe seulement |

Cela suggère une continuité du code entre versions ; **ce n'est pas** une preuve d'identité fonctionnelle, de contrôles OTA ou de code exécuté.

## D. Désassemblage Xtensa Windows — preuve propriétaire reçue

**Source de preuve :** archive de résultats transmise par le propriétaire `SHINO-OEM-V3-20261016-195747.zip`, analysée dans cette conversation. Elle contient `audit.json` et les quatre listings texte. Les fichiers OEM ni ces listings complets ne sont versés dans Git ; seuls les faits utiles sont consignés ici.

**Empreinte du reçu Windows vérifiée sur l'archive fournie :** 3 740 octets ; SHA-256 `82ca692c299039c577c91f9c51802f262845a68e53ef803504a42bef8e9913de` ; contrôle d'intégrité des membres ZIP **PASS**. Cette empreinte identifie le *reçu d'analyse*, **pas** le firmware OEM ni un dump privé.

- `audit.json` indique version `44`, Git source `55d7877fcba8b1cb7a66a0830d35d5b374bc8540`, SHA-256 ZIP/BIN concordants, `candidate_count = 4`.
- Les quatre candidats ont chacun `provider = CAPSTONE`, `error = null` et un fichier de désassemblage.
- Le terminal de l'utilisateur indiquait **12/12 tests du kit V3 PASS** : cela valide les tests du kit sur leur périmètre, pas une couverture des fonctions OEM.
- `xtensa-lx106-elf-objdump.exe` GNU Binutils 2.32 avait d'abord renvoyé sous Windows `0xC0000005` sur **trois octets de test**, alors que `--version` et `-i` fonctionnaient. Origine de l'exception NON VÉRIFIÉE ; la panne n'accuse pas le BIN constructeur.
- Le moteur Capstone mode `CS_MODE_XTENSA_ESP8266` a ensuite permis le décodage de quatre fenêtres. **REA et Ghidra Xtensa n'ont pas été exécutés**.

### Routine candidate autour de 0x40211F68 (V44)

Constat dans `00_doUpload.txt` :

| Adresse IROM | Instruction Xtensa décodée | Portée |
|---|---|---|
| `0x40211F68` | `l32r a5, [0x402107D8]` | Charge un littéral |
| `0x40211F6B` | `l32r a2, [0x402113E8]` | Charge un littéral |
| `0x40211F70` | `movi a3, 0xC8` | Valeur décimale 200 ; lien HTTP non prouvé |
| `0x40211F73` | `l32r a9, [0x40211F64]` | Prépare un saut |
| `0x40211F76` | `jx a9` | Saut indirect |
| `0x40211F64` (données) | Mot LE `0x40211F2C` | Valeur cible déterminée depuis les octets du BIN |

**PROUVÉ :** Capstone a désassemblé ce préfixe ; la lecture directe du littéral à `0x40211F64` donne `0x40211F2C`. **NON VÉRIFIÉ :** que cette entrée soit un handler et que le chemin réellement appelé soit celui-là en pratique (il faut une analyse de flot), encore moins qu'elle gère l'OTA.

Dans `01_wifisave.txt` et `02_wifi_json.txt`, on observe de nombreuses instructions `call0`, `l32r` et de manipulation de pile. L'absence de symboles et de résolution des appels interdit encore de nommer ces fonctions. La routine candidate `/space.json` comporte également des appels et calculs, mais sa sémantique reste à établir.

## E. Correspondance avec le code source public de l'ESP8266 Core

| Indice présent dans OEM | Code Arduino ESP8266 **3.1.2** consulté | Interprétation |
|---|---|---|
| `Unauthenticated Update` | `ESP8266HTTPUpdateServer-impl.h`, lignes 68–72, 101–105 | Correspondance littérale |
| `Update Success! Rebooting...` | `ESP8266HTTPUpdateServer-impl.h`, ligne 36 | Correspondance littérale |
| `Update Success: %zu` | `ESP8266HTTPUpdateServer-impl.h`, ligne 129 | Correspondance littérale |
| `Update was aborted` | `ESP8266HTTPUpdateServer-impl.h`, lignes 134–136 | Correspondance littérale |
| Formulaire `.bin,.bin.gz`, `firmware` | `ESP8266HTTPUpdateServer-impl.h`, lignes 23–26 | Correspondance littérale ; HTML OEM personnalisé |

Le [serveur public de mise à jour](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) : configure une route GET et une réception POST, authentifie selon les paramètres reçus, utilise `getFreeSketchSpace`/`Update.begin`, `Update.write`, `Update.end(true)`, puis `ESP.restart()`. Le [Core Updater](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp) : calcule le staging selon la limite FS, peut vérifier MD5 ou signature **s'ils sont configurés**, et écrit une commande de copie eboot. **Ce sont des faits relatifs à la bibliothèque publique**, pas des résultats d'exécution OEM.

L'[option par défaut de signature du Core public](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater_Signing.h) est désactivée ; cela ne permet **pas** de conclure que la version GeekMagic est non signée, vulnérable ou sans authentification. L'absence de rollback automatique eboot dans ce Core est une propriété de cette implémentation, pas une mesure du bootloader OEM.

## F. Wi-Fi, horloge, flash, LCD — sources distinctes

- **Journal constructeur** V9.0.21 : trois tentatives Wi-Fi au boot, reconnection périodique annoncée après perte de réseau (5 min) ; V9.0.48 : synchronisation de l'heure de secours depuis le retour météo ; V9.0.50 : choix manuel/auto fuseau et correctifs DST. Ce sont des **notes produit constructeur**, pas des callbacks désassemblés.
- **Historique propriétaire SHINO** : `/space.json.total = 3 121 152` sur OEM V9.0.44, ce qui correspond au volume du layout 4m3m et suggère le début du FS `0x100000`. Le dump complet privé peut contenir des secrets et doit rester hors Git. Ce chiffre ne prouve pas une adresse OTA ni une stratégie de recovery.
- **SHINO** : le layout `4m2m` représente une autre organisation, avec FS à `0x200000` selon le linker projet consulté. Toute adresse spécifique pour un candidat OTA doit être vérifiée sur son vrai linker et vrai binaire.
- **LCD** : ST7789 240×240, GPIO/SPI documentés dans [Times-Z GeekMagic Open Firmware](https://github.com/Times-Z/GeekMagic-Open-Firmware) (référence communautaire). **Aucune séquence d'initialisation LCD OEM n'a été démontrée par désassemblage.**

## G. Ce qui reste en HOLD et méthode pour la suite

| Travail à mener | Preuve attendue | État |
|---|---|---|
| Associer `/update` à son callback binaire | Table de routes et références de code, graphe d'appels désassemblé | **HOLD** |
| Attribuer le code à l'OTA/Updater | Appels effectivement tracés vers validation, staging, commit ou authentification | **HOLD** |
| Évaluer authentification/signature OEM | Tests de flux ou branches statiques établissant les conditions (sans réseau/device) | **HOLD** |
| Identifier fonctions Wi-Fi/STA/AP | Fonctions nommées par preuves d'appel, pas par chaînes voisines | **HOLD** |
| Comprendre bootloader OEM/LCD | Cartographie complète et analyse de contrôle | **HOLD** |
| En tirer une correction SHINO | Diff d'implémentation concret + échec reproductible + tests + revue mémoire/sécurité | **NON PROPOSÉ** |

**ÉTAT :** extraction/empreintes, checksums, pointeurs et premiers listings Xtensa **PROUVÉS/OBSERVÉS**. **Limite :** aucun comportement OEM postboot ni vrai transfert OTA testé, aucun ELF source constructeur, ni décompilation complète.

**Sources internes :** [résumé décisionnel](README.md), [`docs/FIRMWARE_AUDIT_01.md`](../../FIRMWARE_AUDIT_01.md), [`docs/COMPARATIVE_FLASH_LAYOUT_AUDIT.md`](../../COMPARATIVE_FLASH_LAYOUT_AUDIT.md), [`docs/ROADMAP.md`](../../ROADMAP.md).