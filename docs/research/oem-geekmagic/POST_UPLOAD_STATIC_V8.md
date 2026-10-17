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

**Tests synthétiques locaux : 14/14 PASS**, y compris détection de mauvais octets, dépassement IROM, mauvais opcodes, collision de sortie et vérification des destinations CALL0. **Exécution réelle du V8 sur l'OEM avec Capstone Windows : NON ENCORE EFFECTUÉE / NON VÉRIFIÉE**.

Le reçu V8 conserve intentionnellement le statut `HOLD_UPLOAD_AUTH_FLASH_POSTBOOT_UNVERIFIED`, même quand une fenêtre est décodée : des instructions réelles et leurs cibles ne suffisent pas à établir les conditions d'authentification, les opérations flash ou le succès postboot.

## 4. Prochain verrou exact

Identifier, dans les futurs listings Capstone, les instructions/branches réellement exécutables à partir de POST B et attribuer les transitions `UPLOAD_FILE_START`, `WRITE`, `END`, `ABORTED` **sans les importer du code Arduino par hypothèse**. Il faudra ensuite prouver ou maintenir HOLD pour les appels `Update.begin/write/end`, la protection avant écriture, et eboot.

**Risque :** une mauvaise attribution peut mener à transposer des protections fictives vers SHINO ; aucune modification de sécurité SHINO ne sera fondée sur les seules similitudes OEM.

**Aucune opération physique** (USB/UART, Wi-Fi, OTA, flash, reboot) et aucun changement du code firmware B5.3.
