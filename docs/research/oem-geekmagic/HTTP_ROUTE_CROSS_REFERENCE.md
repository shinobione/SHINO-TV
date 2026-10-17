# GeekMagic V9.0.44 — comparaison des routes HTTP et des appels Xtensa

**17 octobre 2026 · Analyse statique en lecture seule · Statut : PARTIAL.**

Complément aux analyses [OEM](README.md) et [`/update`](UPDATE_ENTRYPOINT_TRACE.md). Ce document **ne prétend pas** avoir identifié le mécanisme OTA constructeur. Aucune OTA, commande UART, opération SmallTV, modification B5.3 ou firmware.

## 1. Méthode et ancrage

Image : `GeekMagicClock/smalltv-ultra`, ZIP officiel `Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip` au commit `55d7877fcba8b1cb7a66a0830d35d5b374bc8540` ; ZIP **349 377 octets**, BIN **494 144 octets**, SHA-256 BIN `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`.

Les octets OEM ont été **redécodés en mémoire via le connecteur GitHub**. Un index statique a recherché :
1. une occurrence littérale **terminée par NUL** des noms de route dans les segments OEM ;
2. les mots 32 bits LE correspondant aux adresses IROM/DRAM des chaînes ;
3. les motifs bruts Xtensa `l32r` qui désignent ces mots ;
4. les motifs bruts `call0` dont les destinations calculées correspondent aux candidats suivis.

**Limites :** recherche par motifs **sans désassemblage intégral ni validation de frontières d'instructions** ; les correspondances peuvent inclure des octets de données ou du code non atteignable. Les sites listés ci-dessous sont des **candidats statiques**. Certains (signalés comme tels) ont été décodés séparément dans le **reçu Capstone V5 propriétaire** ; le reste n'a pas encore été validé par Capstone. Les valeurs 32 bits sont des adresses virtuelles ; `IROM VA = 0x40200000 + offset fichier` pour les plages IROM étudiées.

## 2. Références croisées des routes

| Route OEM | Chaîne / VA vérifiées | Mot IROM pointant vers chaîne | Instruction `l32r` candidate |
|---|---|---|---|
| `/update` | `0x7821C` / DRAM `0x3FFE90AD` | `0x40211440` | `0x40211648` — **décodée V5** |
| `/doUpload` | `0x6E980` / `0x4026E980` | `0x4021142C` | `0x402115C4` |
| `/wifi.json` | `0x6E9C8` / `0x4026E9C8` | `0x402113EC` | `0x4021148B` |
| `/space.json` | `0x6E9B4` / `0x4026E9B4` | `0x40211404` | `0x40211500` |
| `/wifisave` | `0x6E9A8` / `0x4026E9A8` | `0x4021140C` | `0x40211527` |
| `/delete` | `0x6E98C` / `0x4026E98C` | `0x40211424` | `0x4021159C` |

**Observation précise :** cinq des six motifs `l32r` sont concentrés dans la plage `0x4021148B..0x402115C4`, tandis que `/update` a une référence séparée à `0x40211648`. Ceci **suggère une voie d'enregistrement différente**, pas une preuve de `server.on` ni de validation OTA. La différence DRAM/IROM de la chaîne doit être conservée dans toute comparaison.

Le contrôle d'une éventuelle route `/update` GET/POST ne découle pas de cette table : la même chaîne peut être utilisée dans la construction de plusieurs callbacks, et la table d'association finale n'a pas été reconstruite.

## 3. Cibles des appels directs dans la zone `/update`

**Méthode contrôlée sur les vrais octets d'instruction relevés dans Capstone V5 :** instruction `call0` (3 octets `a,b,c`) : immédiat signé 18 bits `(a>>6)|(b<<2)|(c<<10)`, destination calculée à partir de `(PC+4)&~3` plus `4*imm18_signé`. **7 couples instructions/cibles sur 7 recalculés PASS**, par script Python local utilisant uniquement ces octets vérifiés. C'est un test de calcul d'adresses, **pas un test de sécurité/OTA**.

| Site CALL0 | Octets OEM | Cible recalculée |
|---|---|---|
| `0x4021163F` | `c5 6f 1e` | `0x4022FD3C` |
| `0x40211645` | `45 6f 1e` | `0x4022FD3C` |
| `0x4021164D` | `c5 69 13` | `0x40224CEC` |
| `0x4021165C` | `45 bb ff` | **`0x40211214`** |
| `0x40211661` | `45 49 13` | `0x40224AF8` |
| `0x4021166A` | `05 22 0f` | **`0x4022088C`** |
| `0x40211679` | `05 cd ff` | **`0x4021134C`** |

**Observations nouvelles sur les fréquences dans l'IROM OEM V9.0.44 :** les **motifs bruts** correspondant à `call0 → 0x40224CEC` se trouvent **147 fois**, vers `0x40224AF8` **778 fois**, vers `0x40211214` **1 fois** (`0x4021165C`), vers `0x4021134C` **1 fois** (`0x40211679`), et vers `0x4022088C` **3 fois** (`0x4021166A`, `0x40216068`, `0x402208D0`). Ces comptes sont issus d'un **scan de motifs non validés comme frontières de code**. Ne pas les interpréter comme le nombre exact d'appels exécutables.

**Hypothèse de travail :** `0x40224CEC` / `0x40224AF8` sont des routines utilitaires partagées (un grand nombre de sites potentiels), tandis que `0x40211214` / `0x4021134C` peuvent être des méthodes spécialisées appelées pendant la configuration de `/update`. **Ni leurs signatures C++ ni leur effet fonctionnel ne sont établis.**

### Octets aux entrées ciblées (binaires OEM, pas une décompilation)

| Cible | 16 octets depuis l'entrée observée | État |
|---|---|---|
| `0x40211214` | `12c1b0026113c26112d26111e26110f9` | Prologue ressemblant à une fonction, identité **HOLD** |
| `0x40224CEC` | `12c1f0c921cd020c02d9110931290c` | Prologue, probablement partagé, identité **HOLD** |
| `0x4022088C` | `12c1f0c2610220c220222204093116` | Prologue, identité **HOLD** |
| `0x402208BC` | `12c1f0e2610040e074c921d9110931` | Début déjà décodé V5, identité **HOLD** |
| `0x4021134C` | `12c1e0d2610520d22022222e026107` | Prologue, identité **HOLD** |

La région `0x4021131F` charge un littéral renvoyant au texte `text/html`; des motifs bruts `l32r` à `0x4021139D` et `0x402113B4` chargent respectivement les chaînes `Authorization` et `If-None-Match`. **Leurs frontières de fonctions ne sont pas établies** : ces chaînes peuvent appartenir à des routines HTTP génériques distinctes. **Il serait erroné de conclure « authentification de /update prouvée »**.

## 4. Comparaison avec Arduino ESP8266 Core 3.1.2 — seulement au niveau des sources

[ESP8266HTTPUpdateServer-impl.h](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) configure **GET**, **OPTIONS** et **POST** pour le chemin reçu, et fournit deux callbacks à certains enregistrements (`on(path.c_str(), HTTP_POST, completion_cb, upload_cb)`). La bibliothèque configure en option une authentification selon l'existence de `username` et `password`. Le gestionnaire utilise `ESP.getFreeSketchSpace()`, `Update.begin(...,U_FLASH)`, `Update.write()`, `Update.end(true)` et `ESP.restart()`.

**Seules les chaînes de diagnostic OEM identiques à celles de la bibliothèque et l'existence de la route /update ont été confirmées côté constructeur.** La version, les options, les objets/classes et le chemin d'exécution OEM sont **NON VÉRIFIÉS**. Le lien GET/POST ↔ `0x40211214` et toute conclusion sur HMAC, mot de passe ou signature OEM restent **HYPOTHÈSE**.

## 5. Décision et prochaine preuve

**ÉTAT :** recherche croisée des six chaînes OEM et recalcul de sept appels Xtensa terminés ; le périmètre de code spécifique à examiner est davantage circonscrit.

**FAIT :** aucun code SHINO, dump OEM, appareil ou secret modifié ; pas de décompilation C++ ni de désassemblage complet de ces cinq fonctions. Les motifs et empreintes sont documentés dans cette branche Draft pour reproduction ultérieure.

**BLOCAGE (HOLD) :** désassembler **à partir des vraies frontières** de `0x40211214`, `0x4021134C`, `0x4022088C` et leurs descendants, reconstruire leurs paramètres C++ et comparer à un chemin public ESP8266HTTPUpdateServer, sans sauter de « chaîne présente » à « authentification exercée ». Aucun test physique n'est autorisé ou nécessaire pour cette étape.

**RISQUE :** confusion avec des fonctions HTTP génériques et faux positifs dus au balayage brut `call0/l32r`. Ne pas proposer de modification firmware SHINO ni d'affaiblissement de son authentification sur cette base.

**PROCHAINE ACTION CONCRÈTE :** un désassemblage Capstone **borné et à partir des cinq adresses exactes**, puis résolution des paramètres et des callbacks, est plus utile qu'un scan libre ou qu'une nouvelle mission. Il peut être préparé avec les outils déjà fonctionnels sur Windows ; pas de nouveau kit ni d'installation lancés à ce stade.
