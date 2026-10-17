# GeekMagic OEM — poursuite statique du callback POST B (V8)

**17 octobre 2026 · Lecture seule · ÉTAT : PARTIAL / HOLD sur la chaîne d'upload.**

Suite de [l'analyse du V7](POST_CALLBACK_V7.md), des [pointeurs GET/OPTIONS/POST](CALLBACK_POINTERS_V7.md) et du [tracé `/update`](UPDATE_ENTRYPOINT_TRACE.md).

## 1. Preuves reçues et contre-vérifications

Le propriétaire a envoyé `SHINO-OEM-CALLBACK-20261017-104339.zip` : taille **8 491 octets**, SHA-256 du ZIP **`ac61a12abd87342579e8bed3c791382993bf7355091c36115cc1306a8e772eff`**, intégrité ZIP **PASS**, et **14 listings Capstone**. Le listing POST B `04_POST_body_candidate_B_40214398.txt` démarre à `0x40214398` et s'arrête après le `call0` de `0x402143E1`. Cela **ne prouve pas** la fin de la fonction.

Une nouvelle lecture indépendante du fichier officiel **OEM V9.0.44** du dépôt `GeekMagicClock/smalltv-ultra` au commit `55d7877fcba8b1cb7a66a0830d35d5b374bc8540` confirme son archive ZIP de **349 377 octets**, l'image d'application de **494 144 octets**, et les octets **présents jusqu'à `0x40214585`**. La SHA-256 connue du BIN, établie auparavant à partir des octets OEM, est `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`.

## 2. Constat : le listing V7 s'arrête avant plusieurs blocs et appels

Dans le BIN officiel, les octets du `call0` déjà décodé par V7 à `0x402143E1` sont `05 02 11`, soit une cible **`0x40225404`** selon l'encodage Xtensa CALL0. Le site `0x402143F5` a le motif `c5 00 11`, également vers `0x40225404`.

D'autres sites correspondent exactement au format binaire CALL0 et aux destinations calculées :

| Adresse du site, IROM VA | Octets directs relus dans le BIN OEM | Cible CALL0 calculée |
|---|---|---|
| `0x402143D5` | `05 57 0E` | `0x40222948` |
| `0x402143E1` | `05 02 11` | **`0x40225404`** — instruction décodée V7 |
| `0x402143F5` | `C5 00 11` | `0x40225404` |
| `0x40214459` | `05 41 0F` | **`0x4022386C`** |
| `0x40214462` | `45 FE 10` | `0x40225448` |
| `0x40214545` | `05 40 0E` | `0x40222948` |

**Attention à la portée :** pour tous les sites qui n'ont pas été décodés dans le listing Capstone V7, ces adresses sont des **motifs CALL0 contrôlés au niveau des octets**, **pas encore des instructions atteignables prouvées**. Le désassemblage V8 devra contrôler les frontières exactes, les branches, les littéraux et les appels, et ne pas fusionner artificiellement les différentes fenêtres. Rien ne permet encore d'identifier `0x40225404` à `Update.begin/write/end`.

Autres ancres directement retrouvées dans l'image OEM :
- `0x40214398: 12 c1 f0` — prologue déjà décodé V7 ;
- `0x402143AE: 56 be 10` — branche `bnez` décodée V7, **cible et sémantique non attribuées** ;
- `0x402143E4: 8c 42 0c` — début de la zone non décodée ;
- `0x402144C0: 16 53 0a` — zone voisine d'une branche ;
- `0x40214585: 0d f0` — motif de retour `ret.n` plausible, mais frontière de fonction non démontrée.

Le chemin de réponse **Basic 401** est décrit séparément dans [POST_CALLBACK_V7](POST_CALLBACK_V7.md). Il ne prouve toujours pas que POST B refuse les écritures lorsque l'accès n'est pas authentifié.

## 3. Outil de poursuite V8 — garde-fous

Un kit indépendant `SHINO_OEM_UPLOAD_FOLLOW_V8` a été préparé pour Windows. Il **réutilise les trois modules Python déjà éprouvés**, impose les SHA du ZIP/BIN OEM officiel, vérifie **8 ancres d'octets + 6 appels CALL0**, puis demande à Capstone **15 fenêtres ciblées et bornées**, notamment plusieurs points après `0x402143E1` et quatre destinations d'appels. Il n'écrit **aucun BIN**, ne contacte aucun SmallTV, ne touche ni aux branches SHINO opérationnelles ni à Codex.

**Tests synthétiques locaux : 14/14 PASS**, y compris détection de mauvais octets, dépassement IROM, mauvais opcodes, collision de sortie et vérification des destinations CALL0. **État à la création du kit : exécution réelle du V8 NON VÉRIFIÉE ; désormais remplacé par le reçu Windows authentiquement reçu et analysé en section 4.**

Le reçu V8 conserve intentionnellement le statut `HOLD_UPLOAD_AUTH_FLASH_POSTBOOT_UNVERIFIED`, même quand une fenêtre est décodée : des instructions réelles et leurs cibles ne suffisent pas à établir les conditions d'authentification, les opérations flash ou le succès postboot.

## 4. Reçu Windows V8 — états d'upload candidats, bornes de preuve

**Nouvelle preuve reçue le 17 octobre 2026 :** `SHINO-OEM-UPLOAD-V8-20261017-110658.zip`, vérifiée directement depuis le fichier de la conversation.

- ZIP **7 625 octets** ; SHA-256 ZIP **`fbfa24958fa96ea105521bfe145539abc1f5d665449f8f2894e847f0a853e8ff`** ; test intégrité **PASS**.
- Contient `upload_follow_v8.json` + **11 listings Capstone**, avec les empreintes ZIP/BIN officiel V9.0.44 et le commit épinglé concordants avec cet audit.
- Sur **15 fenêtres demandées** : **11 CAPSTONE**, **4 HOLD** à `0x402143E4`, `0x40214400`, `0x4021443B` et `0x40214470` (« Capstone decoded zero instructions »). L'arrêt de décodage ne démontre pas une absence d'instruction/code : la région comporte des branches et des frontières à reconstruire.
- Reçu : **`HOLD_UPLOAD_AUTH_FLASH_POSTBOOT_UNVERIFIED`**. Les **14 ancres** sont listées et **33 enregistrements d'appels décodés**, comprenant des doublons entre fenêtres chevauchantes ; **29 sites CALL0 distincts**.

### La preuve nouvelle : comparaison de trois valeurs d'état dans POST B

Le listing `00_POST_B_original_entry_40214398.txt` montre :

```asm
402143A7  d2232a   l32i a13, a3, 0xa8
402143AC  e80d     l32i.n a14, a13, 0
402143AE  56be10   bnez a14, . +0x10f  ; cible calculée 0x402144C0
```

La branche **`a14 == 0`** continue vers un bloc de travail situé à `0x402143B1` ; si `a14 != 0`, l'instruction pointe vers `0x402144C0`.

Deux fenêtres V8 supplémentaires décodent :

```asm
402144C0  16530a   beqz a3, . +0xa9
402144C3  661e39   bnei a14, 1, . +0x3d  ; cible calculée 0x40214503
...
40214500  662e48   bnei a14, 2, . +0x4c ; cible calculée 0x4021454F
```

La branche conditionnelle supplémentaire `beqz a3` représente une **condition/garde inconnue** ; aucun accès n'est considéré autorisé sur cette base.

Dans le [Core ESP8266 3.1.2 épinglé, `ESP8266WebServer.h`](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer.h), l'énumération `HTTPUploadStatus` est exactement `UPLOAD_FILE_START=0`, `UPLOAD_FILE_WRITE=1`, `UPLOAD_FILE_END=2`, `UPLOAD_FILE_ABORTED=3`. Les tests OEM `0`, `1`, `2` apparaissent **dans le callback POST candidat déjà relié par ses littéraux à la route `/update`**.

**Verdict :** concordance structurelle **forte** avec une machine d'états d'upload `START / WRITE / END`. Il est **hautement plausible**, mais **non démontré par reconstruction des objets C++**, que le champ lu à `+0xA8` puis `+0` représente `HTTPUpload.status`. L'état `ABORTED=3` **n'a pas été identifié dans un chemin distinct**. Ne pas attribuer les branches/callees aux opérations flash, à leur authentification ou à l'acceptation de l'OTA avant désassemblage supplémentaire.

### Fonctions appelées décodées : destinations, pas identités OTA

- POST B, `0x402143E1 → 0x40225404` : listing `11_POST_B_early_callee_candidate_40225404.txt`, prologue de pile `-0x20`, 37 instructions puis `ill` après `ret.n` et entrée distincte à `0x40225448`. Cette fonction effectue des appels et retourne un booléen/flag plausible ; **fonction métier NON VÉRIFIÉE**.
- POST B, `0x402144E1 → 0x4022386C` : 44 instructions décodées ; prologue avec allocation de pile `0xA0` (**160 octets statiques locaux**, pas une mesure de marge mémoire globale), appels et tests, fin non démontrée. **Aucune identification en `Update.write`**.
- POST B, `0x402143D5 → 0x40222948` : six instructions seulement, comportement **HOLD**.
- POST A, fenêtre `0x402120D0..0x40212172` : un `movi a3,0xC8` (**200**) apparaît dans deux blocs, et `movi a2,0x64` (**100**) précède un appel. Il existe aussi un `callx0 a3` (appel indirect). **Ces nombres sont compatibles** avec réponse HTTP 200 / temporisation 100 ms d'Arduino, mais **ni l'identité des appels, ni un reboot, ni une acceptation OTA ne sont établis**. Cela complète sans remplacer le défi Basic 401 démontré dans [le V7](POST_CALLBACK_V7.md).

**ÉTAT : PROUVÉ sur les instructions extraites** : les comparaisons 0/1/2, les cibles d'appels vérifiées et la réponse candidate 200. **HYPOTHÈSE** : interprétation comme états `UPLOAD_FILE_*`. **HOLD** : définition exacte de l'objet `upload`, blocage d'écriture par authentification, `Update.begin/write/end`, eboot et redémarrage physique.

**Prochaine preuve ciblée :** établir la continuité de POST B dans les quatre zones non décodées, notamment entre `0x402143E4` et `0x402144C0` et autour de `0x4021454F` ; suivre les cibles directes `0x4022FD4C`, `0x40224608` et `0x40224830` et corréler leurs effets aux champs de `HTTPUpload` et de l'Updater. Les 11 listings réussis **ne prouvent pas** la couverture du callback entier. Aucune OTA, UART, écriture flash, reboot, Wi-Fi ni modification B5.3.

## 5. Corrélation des appels WRITE/END avec `HTTPUpload` et `UpdaterClass` (17 octobre)

**Nouvelle qualification statique, fondée sur le ZIP V8 réellement reçu :** lecture directe des fichiers Capstone, vérification automatique de **15 instructions à leurs adresses exactes** et de **4 destinations CALL0 recalculées**. Toutes les assertions sont **PASS**, uniquement sur les listings du reçu OEM V8 ; elles ne constituent ni une décompilation de la cible, ni une mesure mémoire native, ni une OTA.

**Confrontation à deux sources épinglées :** [`ESP8266WebServer.h` du Core 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer.h) définit `HTTPUpload` avec `status`, trois `String` (`filename`, `name`, `type`), puis `totalSize`, `currentSize`, `contentLength`, et enfin `uint8_t buf[HTTP_UPLOAD_BUFLEN]`. [`WString.h` du même tag](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/WString.h) fournit un `String` avec union pointeur/SSO compatible avec **12 octets** sur ESP8266 32 bits. Le modèle de disposition mémoire *dans l'ABI 32 bits usuelle* donne :

| Position calculée dans `HTTPUpload` | Champ / taille modèle |
|---|---|
| `+0x00` | `HTTPUploadStatus` / 4 octets |
| `+0x04`, `+0x10`, `+0x1C` | trois `String` / 12 octets chacun |
| `+0x28` | `totalSize` |
| **`+0x2C`** | **`currentSize`** |
| `+0x30` | `contentLength` |
| **`+0x34`** | **`buf`** |

**Limite :** ces offsets sont le **résultat d'un calcul ABI sur les sources publiques**, pas des `offsetof` mesurés dans le binaire propriétaire. Leur concordance avec deux accès indépendants dans les listings OEM constitue une forte indication de la même structure/layout.

### Branche WRITE candidate, depuis le désassemblage réel `0x402144C0`

```asm
402144C3  bnei    a14, 1, ...
402144C6  addi    a2, a2, 0x24
402144C9  call0   0x4022FD4C
...
402144E4  l32i.n  a4, a13, 0x2C   ; size argument candidate
402144E6  l32r    a2, 0x40211FA0 ; literal holding global object pointer
402144E9  addi    a3, a13, 0x34   ; buffer address candidate
402144EC  call0   0x40224608
402144EF  l32i.n  a3, a13, 0x2C
402144F1  bne     a2, a3, ...     ; compare returned bytes to requested length
```

L'ABI Xtensa CALL0 permet l'interprétation candidate `a2=this`, `a3=data`, `a4=len`. La fonction du Core [`UpdaterClass::write(uint8_t* data,size_t len)`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp) retourne précisément un `size_t` comparé par l'appelant à `upload.currentSize`. **Attribution `0x40224608 ≈ Update.write` : HYPOTHÈSE FORTEMENT ÉTAYÉE ; contenu de `0x40224608` NON ENCORE DÉSASSEMBLÉ.**

Le callee `0x4022FD4C`, appelé juste avant le traitement WRITE puis END sur un sous-objet à `+0x24`, peut représenter un test de longueur/erreur semblable à `_updaterError.length()` dans le [serveur HTTP OTA 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h). **NON ATTRIBUÉ** tant que son corps n'est pas examiné.

### Branche END candidate, depuis `0x40214500`

```asm
40214500  bnei    a14, 2, ...
40214503  addi    a2, a2, 0x24
40214506  call0   0x4022FD4C
...
4021450F  l32r    a2, 0x40211FA0
40214512  movi.n  a3, 1
40214514  call0   0x40224830
```

La signature correspond à `UpdaterClass::end(bool evenIfRemaining)` appelé avec `true` dans [ESP8266HTTPUpdateServer-impl.h](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h). **Attribution `0x40224830 ≈ Update.end(true)` : HYPOTHÈSE FORTEMENT ÉTAYÉE, pas encore prouvée par le corps du callee.**

### Contrôle automatique exact sur V8

- **15/15** correspondances instruction/adresse/opcode/opérandes **PASS**, sur les listings `05_POST_B_first_branch_target_area` et `07_POST_B_downstream_2`.
- **4/4** calculs de cibles de **CALL0** **PASS** :
  - `0x402144C9 → 0x4022FD4C` ;
  - `0x402144EC → 0x40224608` ;
  - `0x40214506 → 0x4022FD4C` ;
  - `0x40214514 → 0x40224830`.
- Le ZIP reçu a de nouveau passé `ZipFile.testzip()` et son SHA-256 est identique au reçu V8 ci-dessus. Aucune nouvelle analyse Capstone réelle ni build du firmware effectuée durant cette corrélation.

**Ce qui est plus solide désormais :** trois correspondances indépendantes avec le code public — tests de statut START/WRITE/END, **offsets `currentSize/buf`**, et **signature + contrôle du résultat `write` / argument `end(true)`**. Cette convergence identifie de façon **fortement probable** le moteur Updater utilisé. Elle **ne prouve pas** la branche START/`Update.begin`, la protection effective avant écriture, les éventuelles signatures, le retour d'erreur, la commande eboot ou le postboot.

**PROCHAINE ACTION UNIQUE :** valider les **corps réels** de `0x40224608` et `0x40224830` et le test commun `0x4022FD4C` par un désassemblage Xtensa borné (sans balayage large, sans opération appareil) ; ensuite seulement retracer `Update.begin` dans START et les contrôles d'authentification.

## 6. Verrou historique et objectif restant

Identifier, dans les futurs listings Capstone, les instructions/branches réellement exécutables à partir de POST B et attribuer les transitions `UPLOAD_FILE_START`, `WRITE`, `END`, `ABORTED` **sans les importer du code Arduino par hypothèse**. Il faudra ensuite prouver ou maintenir HOLD pour les appels `Update.begin/write/end`, la protection avant écriture, et eboot.

**Risque :** une mauvaise attribution peut mener à transposer des protections fictives vers SHINO ; aucune modification de sécurité SHINO ne sera fondée sur les seules similitudes OEM.

**Aucune opération physique** (USB/UART, Wi-Fi, OTA, flash, reboot) et aucun changement du code firmware B5.3.

## 7. Poursuite ciblée des corps WRITE/END/contrôle — préparation V9 (17 octobre)

**Lecture indépendante des octets du firmware OEM V9.0.44**, depuis l'archive officielle épinglée (ZIP 349 377 octets ; application 494 144 octets). Vérification des premiers octets de trois cibles et des appels POST B du reçu V8 :

| Cible OEM | Premiers octets observés | Interprétation limitée |
|---|---|---|
| `0x40224608` | `12 c1 d0 c2 61 0a e2 61 08` | Cible CALL0 probable de WRITE ; prologue présent, fonction non encore étudiée |
| `0x40224830` | `92 a0 c0 90 11 c0 c2 61 2e` | Cible CALL0 probable de END ; frontière de fonction non établie |
| `0x4022FD4C` | `3d 02 22 02 0b 77 e2 07` | Petit contrôle commun ; lecture octet +0x0B compatible avec gestion interne de String (HYPOTHÈSE) |

Les sites `0x402144C9`, `0x402144EC`, `0x40214506`, `0x40214514` appellent respectivement `0x4022FD4C`, `0x40224608`, `0x4022FD4C`, `0x40224830` selon les octets réels `05 88 1B`, `85 11 10`, `45 84 1B`, `85 31 10` et l'encodage CALL0. Cela confirme les **adresses**, mais **pas** les noms C++ ou la sûreté OTA.

Un outil privé `SHINO_OEM_UPDATER_CALLTRACE_V9` a été préparé : **12 fenêtres de lecture** ciblées sur les trois fonctions et un appelé START `0x4020B454` ; **6 ancres de bytes + 4 ancres CALL0** vérifiables ; contrôle strict SHA-256 du ZIP et BIN OEM ; refus de réécrire une sortie préexistante ; uniquement JSON et listings texte. **11/11 tests synthétiques PASS**, compilation Python PASS, archive de livraison ZIP intègre. **Exécution V9 avec Capstone Windows sur les vrais octets NON ENCORE EFFECTUÉE / NON VÉRIFIÉE**.

**HOLD :** on n'a pas démontré l'identité des trois fonctions cibles, l'authentification effective avant écriture, le contrôle cryptographique constructeur, les conditions de staging/flash/eboot ni le postboot. Les analogies avec Arduino Core 3.1.2 ne sont pas des preuves d'exécution OEM. Aucune modification du firmware SHINO, du SmallTV, de l'OTA, du Wi-Fi, de Codex ou de B5.3.

**Prochaine preuve :** recevoir le V9 Capstone, confirmer les corps des cibles et tracer leurs branches ; éviter toute modification matérielle à ce stade.
