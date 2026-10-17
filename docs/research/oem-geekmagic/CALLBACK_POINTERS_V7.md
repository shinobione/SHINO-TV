# Audit OEM GeekMagic V9.0.44 — résolution des callbacks HTTP

**17 octobre 2026 — analyse statique hors ligne. Statut : PARTIAL ; comportement OTA/auth/flash HOLD.**

> **Mise à jour V7 exécutée sur Windows :** reçu propriétaire reçu et vérifié (**14 listings Capstone**) ; [analyse des deux callbacks POST et du défi HTTP Basic 401](POST_CALLBACK_V7.md). Le passage ci-dessous qui annonce « V7 non encore exécuté » décrit l'état **avant** réception, et est conservé comme historique ; la preuve actuelle se trouve dans le document lié. La présence d'un défi HTTP Basic **ne prouve pas** l'authentification efficace de toutes les étapes OTA.

Complément de [l'enquête `/update`](UPDATE_ENTRYPOINT_TRACE.md), du [Calltrace V6](UPDATE_ENTRYPOINT_TRACE.md) et du [registre des routes HTTP](HTTP_ROUTE_CROSS_REFERENCE.md).

## Preuves et source

Archive officielle OEM `Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip`, commit `55d7877fcba8b1cb7a66a0830d35d5b374bc8540` ; BIN 494 144 octets, SHA-256 `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`. Les valeurs ci-dessous ont été **relues directement dans les octets officiels extraits en mémoire** via le connecteur GitHub. Aucun dump OEM ni secret n'est ajouté à Git.

Le reçu Windows V6 du propriétaire avait décodé avec Capstone le corps `0x40211214` ; il prépare successivement des groupes ayant les constantes GET=1, OPTIONS=7, POST=3, correspondant exactement à l'[énumération ESP8266WebServer du Core 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer.h). Cela **renforce** l'hypothèse d'une architecture semblable à [ESP8266HTTPUpdateServer](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h), **sans prouver** que le code constructeur utilise cette version exacte ou la même configuration.

## Dix valeurs du pool IROM de 0x402111EC à 0x40211210

| Groupe déduit de V6 | Adresse du mot LE | Valeur IROM lue | Interprétation |
|---|---|---|---|
| GET | `0x402111EC` | `0x40214904` | relais candidat |
| GET | `0x402111F0` | `0x40230238` | adresse auxiliaire, rôle HOLD |
| OPTIONS | `0x402111F4` | `0x40212228` | relais candidat A |
| OPTIONS | `0x402111F8` | `0x4023024C` | adresse auxiliaire, rôle HOLD |
| OPTIONS | `0x402111FC` | `0x40214618` | relais candidat B |
| OPTIONS | `0x40211200` | `0x40230260` | adresse auxiliaire, rôle HOLD |
| POST | `0x40211204` | `0x40212178` | relais candidat A |
| POST | `0x40211208` | `0x40230274` | adresse auxiliaire, rôle HOLD |
| POST | `0x4021120C` | `0x4021458C` | relais candidat B |
| POST | `0x40211210` | `0x40230288` | adresse auxiliaire, rôle HOLD |

Chaque valeur provient du **mot littéral de l'image réelle**, pas d'une table supposée. Les cinq adresses auxiliaires `0x40230238/4C/60/74/88` sont espacées exactement de **20 octets** ; leurs premiers octets présentent des motifs répétitifs. **Ne pas les appeler destructeurs, no-op ou vérificateurs sans leurs vraies instructions et l'ABI.**

## Cinq relais et leurs destinations

Les cinq relais ont le préfixe exact `91 ff ff a0 09 00`, compatible avec `l32r a9, [VA - 4]` puis `jx a9` ; le mot LE situé 4 octets avant chacun contient la destination ci-dessous. Les octets de chaque relais et les cinq mots de destination ont été contrôlés.

| Groupe candidat | Relais indirect | Destination lue à VA-4 |
|---|---|---|
| GET | `0x40214904` | `0x40214868` |
| OPTIONS A | `0x40212228` | `0x40212188` |
| OPTIONS B | `0x40214618` | `0x40214594` |
| POST A | `0x40212178` | **`0x40211FB8`** |
| POST B | `0x4021458C` | **`0x40214398`** |

**PROUVÉ :** ces sauts indirects locaux sont cohérents avec les données OEM et les décodages Xtensa précédents. **NON VÉRIFIÉ :** quel relais POST est exécuté pour un upload effectif, quelles fonctions exactes il invoque, et s'il existe une vérification d'authentification, de SHA/signature ou un chemin vers eboot. La preuve de présence d'un pointeur ne vaut jamais preuve de son exécution.

## État de l'outil V7 et prochaine preuve

Un outil d'étude *lecture seule* `SHINO_OEM_CALLBACK_TRACE_V7` a été développé ici pour relire et vérifier les **dix mots** + **cinq relais**, désassembler **14 fenêtres** ciblées avec Capstone Xtensa déjà installé sur Windows, et émettre **uniquement** JSON + listings texte. Ses **9 tests synthétiques ont passé** ; **son exécution sur le véritable ZIP OEM sous Windows est NON VÉRIFIÉE** tant qu'aucun reçu V7 n'a été fourni. Il ne doit pas se substituer aux preuves d'exécution.

**PROCHAINE ACTION :** décoder d'abord les fonctions `0x40211FB8` et `0x40214398` (candidates POST), puis `0x40211070` / `0x402110F8` (helpers d'enregistrement) ; résoudre les instructions et le flot d'appels avant toute attribution fonctionnelle. Si le graphe n'établit pas la chaîne `HTTP POST → auth → Update.begin/write/end → eboot`, maintenir **HOLD**.

**Aucune modification firmware ou opération SmallTV, OTA, UART, Wi-Fi, Codex ou B5.3** dans cette recherche. Le dossier de documentation reste sur la branche isolée de la PR #50, non fusionnée.
