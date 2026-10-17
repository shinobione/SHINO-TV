# START/AUTH : preuve de verrouillage avant WRITE — recherche V10

**17 octobre 2026 — audit statique en lecture seule — HOLD_AUTHORIZATION_PREWRITE_BEGIN_FLASH_POSTBOOT_NOT_PROVEN.**

Ce document met en évidence le **verrou de sécurité non encore démontré** dans l'OTA constructeur. Il prolonge le [reçu V9 et l'attribution structurelle de `UpdaterClass::write`](UPDATER_CALLTRACE_V9.md), le [POST B V8](POST_UPLOAD_STATIC_V8.md) et le [callback POST A / défi Basic 401](POST_CALLBACK_V7.md). **Aucune modification de firmware, d'appareil, de Wi-Fi, d'OTA, de Codex ou de B5.3.**

## 1. Faits vérifiables dans les reçus antérieurs

- **V7 — POST A :** le code contient une construction de réponse 401 avec `WWW-Authenticate`, `Basic realm` et `Login Required`. **Ce n'est pas une preuve que POST B bloque les données non authentifiées.**
- **V8 — POST B :** `0x402143A7 : l32i a13,a3,0xa8`, `0x402143AC : l32i.n a14,a13,0`, `0x402143AE : bnez a14,...`. Le branchement distingue `status == 0` du reste ; les branches `status == 1` et `status == 2` sont confirmées dans les fenêtres aval. Les valeurs 0/1/2 concordent avec [`HTTPUploadStatus` du Core 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer.h), mais l'offset de statut et le type d'objet OEM n'ont pas été prouvés via symboles.
- **V9 — WRITE :** `0x40224608` a une très forte correspondance avec [`UpdaterClass::write`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp), y compris les offsets de ses champs, le contrôle d'espace et l'erreur `UPDATE_ERROR_SPACE=4`. **Cette attribution ne signifie pas qu'un contrôle d'accès précède toujours l'appel.**
- La fenêtre réelle V9 `0x402143B1` atteste les appels `0x402143B1 → 0x4020B454`, `0x402143D5 → 0x40222948`, `0x402143E1 → 0x40225404`. Aucun n'est encore baptisé « authenticate » ou « begin ».

## 2. Contrat de comparaison public : non transposable sans preuve

Le Core public [`ESP8266HTTPUpdateServer-impl.h` v3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) calcule un booléen `_authenticated` pendant `UPLOAD_FILE_START` :

```cpp
_authenticated = (_username == emptyString || _password == emptyString ||
                  _server->authenticate(_username.c_str(), _password.c_str()));
if (!_authenticated) return;
```

Pour WRITE/END, ses branches utilisent un test de `_authenticated` (ainsi qu'un garde d'erreur). **L'expression de référence accepte l'absence de mot de passe** comme condition authentifiée ; la seule présence de cette bibliothèque ne garantit donc pas qu'une authentification soit exigée en production. Le chemin constructeur **doit être validé indépendamment** sur les véritables callbacks, compte tenu des modifications possibles du fournisseur.

Le point de sécurité à prouver côté OEM est l'**affectation effective**, la **propagation** puis le **test** d'un état d'autorisation avant `Update.begin` et avant `Update.write`. Une réponse 401 produite lors d'une autre phase ne le démontre pas.

## 3. Observation de contrôle

D'après le désassemblage déjà vérifié :

```asm
4021439F  l32i.n a2, a2, 0
402143A3  l32i.n a3, a2, 4
402143A7  l32i   a13,a3,0xa8
402143AC  l32i.n a14,a13,0
402143AE  bnez   a14, ... ; chemin de non-START
402143B1  call0  0x4020B454 ; branche START probable
...
402144C0  beqz   a3,... ; garde aval observée
402144C3  bnei   a14,1,... ; branche WRITE candidate
```

La valeur de `a3` à `0x402144C0` provient **initialement** de champs d'objets ; **ne pas appeler ce `beqz` une vérification `_authenticated`** sans retracer tous les chemins et les registres qui l'alimentent. Dans le chemin START, des appels directs peuvent modifier les registres caller-saved ; les branches de cette région ne sont pas encore reconstituées intégralement.

**Verrou de preuve :** établir précisément si `WRITE` et `END` comportent un garde sur l'état d'autorisation, ou si celui-ci réside dans une couche distincte. **Ni une absence de garde ni un contournement ne sont démontrés.**

## 4. V10 préparé : recherche ciblée des gardes START/AUTH

Kit documentaire local `SHINO_OEM_START_AUTH_V10_2026-10-17.zip` (non commité dans Git), comprenant scripts Python de lecture seule et README. Il reprend le téléchargement OEM épinglé et la validation SHA-256 du ZIP/BIN des outils V8/V9, puis fournit :

- **19 vérifications d'ancres : 11 groupes d'octets + 8 appels `CALL0`** ;
- **18 fenêtres Xtensa indépendantes et bornées**, dont des départs autour de `0x402143E4` (où V8 a cessé le désassemblage), des groupes START et du garde précédant WRITE ;
- collecte des `CALL0` réellement décodés par Capstone, et sortie **JSON + listings texte exclusivement** ;
- **15/15 tests synthétiques PASS**, `py_compile` PASS et archive ZIP intègre. Ces PASS attestent le fonctionnement du kit sur fixtures synthétiques, **pas** une authentification OEM ou des résultats Capstone V10 réels.
- **Exécution sur le véritable firmware OEM par Capstone Windows : NON VÉRIFIÉE à ce stade**, en attente du reçu `SHINO-OEM-START-AUTH-V10-*.zip`.

Même si des fenêtres sont décodées, leur inclusion dans un flux exécutable **doit être démontrée** par les branches et retours ; les départs décalés de 1–2 octets visent à expliquer les arrêts Capstone, **pas** à inventer des transitions.

## 5. Décision d'ingénierie

**ÉTAT :** forte correspondance OEM avec les API Arduino HTTPUpload/Updater. Les opérations WRITE et END sont candidates crédibles, la réponse Basic 401 existe dans le code.

**BLOCAGE :** aucune chaîne complète et indépendante `authentification → autorisation mémorisée → WRITE/END` n'est prouvée. `Update.begin`, signature cryptographique et eboot restent HOLD. Ne pas assimiler une CI/une exécution de scripts à une validation physique.

**RISQUE :** considérer à tort l'OTA OEM comme authentifiée ou non authentifiée et changer en conséquence la sécurité SHINO. **Aucun retrait de garde, test OTA physique ni diffusion de secret**.

**PROCHAINE ACTION :** analyser le reçu V10 réel et reconstruire les chemins ; sinon conserver HOLD. En parallèle, les garde-fous SHINO ne doivent jamais reposer sur la sécurité présumée du firmware OEM.


## 6. Analyse additionnelle : nature du garde non-START (lecture croisée V7/V8/V9, sans résultat V10)

**Résultat statique important du 17 octobre :** les vrais reçus Capstone **V7**, **V8** et **V9** sont disponibles dans la conversation, tandis que le ZIP **`SHINO_OEM_START_AUTH_V10_2026-10-17.zip` est seulement le kit de préparation**, et **aucun reçu d'exécution V10** n'a encore été fourni. Il serait erroné de déclarer des résultats V10 Capstone.

Contrôle automatique indépendant sur les trois archives déjà fournies : intégrité ZIP **PASS** pour chacune, empreintes calculées depuis les octets reçus :
- V7 `SHINO-OEM-CALLBACK-20261017-104339.zip` : 8 491 octets, SHA-256 `ac61a12abd87342579e8bed3c791382993bf7355091c36115cc1306a8e772eff` ;
- V8 `SHINO-OEM-UPLOAD-V8-20261017-110658.zip` : 7 625 octets, SHA-256 `fbfa24958fa96ea105521bfe145539abc1f5d665449f8f2894e847f0a853e8ff` ;
- V9 `SHINO-OEM-UPDATER-V9-20261017-113327.zip` : 6 850 octets, SHA-256 `fed135915e77f33c565429faa1aed4a2ceb611fdce3c369f1cbf1f0b01730ed0`.

**20/20 contrôles d'instructions ciblées** PASS (adresse, octets, mnémonique/opérandes) dans ces trois listings, dont les six instructions de préparation/saut et les deux chemins WRITE/END. Il s'agit d'un **test de cohérence sur des reçus**, pas d'un nouveau désassemblage complet. Cible de la branche `0x402143AE` recalculée : `0x402143AE + 3 + 0x10F = 0x402144C0` ; concordance avec la frontière d'instruction Capstone V8 : **PASS**.

### Disposition d'objet et contrôle discriminant

La définition publique épinglée [`ESP8266HTTPUpdateServer.h` (Core 3.1.2)](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer.h) fournit, dans l'ordre : `bool _serial_output`, pointeur `_server`, deux `String` (`_username`, `_password`), `bool _authenticated`, puis `String _updaterError`. D'après l'ABI 32 bits et la taille `String == 12` inférée de [`WString.h`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/WString.h), la disposition candidate est :

| Offset `this` | Champ selon le modèle source | Recoupement OEM |
|---|---|---|
| `+0x00` | `_serial_output` | accès dans START OEM `0x402143CA : l8ui a2,a2,0` |
| `+0x04` | `_server` | **`0x402143A3 : l32i.n a3,a2,4`**, suivi de `0x402143A7 : l32i a13,a3,0xA8` pour le pointeur upload |
| `+0x08` | `_username` | candidat utilisé dans START `0x402143DF : addi.n a2,a2,8` avant appel `0x40225404` ; identité fonctionnelle HOLD |
| `+0x14` | `_password` | non attribué dans les fenêtres actuelles |
| **`+0x20`** | **`_authenticated`** | **POST A : `0x40212021 : l8ui a14,a2,0x20`**, suivi d'un branchement vers le défi 401 |
| **`+0x24`** | **`_updaterError`** | POST B WRITE/END : `0x402144C6` et `0x40214503 : addi a2,a2,0x24`, appel `0x4022FD4C` fortement identifié comme `String.length()` |

**Lecture directe du chemin non-START :**

```asm
4021439F  l32i.n a2,a2,0        ; this selon modèle
402143A3  l32i.n a3,a2,4        ; pointeur _server candidat
402143A7  l32i a13,a3,0xa8     ; objet HTTPUpload
402143AC  l32i.n a14,a13,0     ; status
402143AE  bnez a14,+0x10f      ; si non-START → 0x402144C0
       [aucune instruction intermédiaire sur ce bord du graphe]
402144C0  beqz a3,+0xa9        ; **teste a3 inchangé depuis this+4**
402144C3  bnei a14,1,...       ; statut WRITE candidat
402144C6  addi a2,a2,0x24      ; _updaterError candidat
402144C9  call0 0x4022FD4C    ; String.length candidat
...                           ; si length == 0
402144EC  call0 0x40224608    ; Updater.write fortement identifié
```

Le registre **`a3` testé à `0x402144C0` conserve nécessairement la valeur chargée à `0x402143A3` sur cette arête directe** (aucun appel ni autre instruction entre les deux). Sous le modèle d'objet publiquement concordant, le `beqz a3` est donc un **test de pointeur serveur**, **pas un test direct du champ booléen `_authenticated` à `this+0x20`**. La branche END a le même test préalable, puis `String.length()` sur `this+0x24` avant l'appel END candidat.

**Statut de sécurité, formulé rigoureusement :**
- **PROUVÉ sur le flot local déjà décodé :** l'arête non-START porte `a3` inchangé vers le garde `beqz`, suivi d'un contrôle sur l'objet erreur puis d'appels WRITE/END candidats.
- **FORTEMENT ÉTAYÉ par les offsets de classe :** ce garde teste `_server` et n'est **pas en lui-même** une lecture de `_authenticated`.
- **HOLD :** rien ne prouve que ce chemin constitue une requête réseau non autorisée effectivement atteignable, qu'il manque tout garde en amont, ou que des données non authentifiées puissent être écrites. **Ne pas qualifier le firmware de vulnérable sans preuve de préconditions et de dispatch.**

La comparaison est pertinente : la source [`ESP8266HTTPUpdateServer-impl.h` (Core 3.1.2)](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) teste explicitement `_authenticated` dans ses conditions WRITE/END, alors que **les instructions OEM décodées sur cette arête directe ne le montrent pas**. Cela peut provenir d'une variante OEM, d'optimisations ou d'un contrôle réparti ; ces explications sont encore **HYPOTHÈSES**.

**Prochaine preuve prioritaire (V10)** : étudier le callee START et les régions `0x402143E4..0x402144C0` pour voir *comment* `_authenticated` est mis à jour et *si* le callback ou son invocateur empêche toute transition WRITE sans autorisation. Vérifier aussi les autres chemins qui accèdent à `this+0x20`, et démontrer un graphe fermé avant toute recommandation. **Aucune action physique autorisée ou réalisée.**


## 7. Reçu Windows V10 analysé : affectation du champ d'authentification et candidat BEGIN

**17 octobre 2026 — preuve réellement reçue après la préparation V10.** La section 4 et la section 6 reflètent l'état **avant** cette réception ; le statut actuel est donné ici.

### Intégrité, couverture et limites du reçu

- Fichier reçu : `SHINO-OEM-START-AUTH-V10-20261017-122743.zip` ;
- **6 410 octets**, **SHA-256 calculé `88e71bd82d9d056a7b012abf121dbf3d3c9abc67332b9710ae7efd0bfd48dcd4`**, intégrité `ZipFile.testzip()` **PASS** ;
- `start_auth_v10.json` + **12 listings Capstone**, **18 fenêtres** vérifiées par rapport au manifeste du rapport : **12 CAPSTONE**, **6 `HOLD_DECODE_STOP`** ; toutes les **19 ancres** requises sont présentes dans le reçu (11 ancres d'octets et 8 CALL0) ;
- le reçu présente le statut **`HOLD_AUTHORIZATION_PREWRITE_BEGIN_FLASH_POSTBOOT_NOT_PROVEN`** et les SHA ZIP/BIN du firmware OEM V9.0.44 épinglé ;
- les sorties Capstone sont **des fragments avec points d'entrée choisis**, pas un graphe d'atteignabilité ni une preuve matérielle. Les fenêtres depuis `0x402143E4`, `0x402143F0`, `0x4021440D`, `0x4021441B`, `0x40214438`, `0x40214470` restent HOLD.

### Résultat nouveau : écriture du booléen d'autorisation pendant START

Le listing `11_start_store_b_40214420.txt` contient, au mot près :

```asm
40214420  l32i a3,a12,0        ; retrouver this depuis objet lambda
40214423  s8i a2,a3,0x20       ; mémoriser résultat booléen dans this+0x20
40214426  l8ui a3,a3,0         ; lire this+0, candidat _serial_output
40214429  bnez a2, . +0x1d    ; résultat non nul → cible calculée 0x40214449
4021442C  beqz a3, . +0x14e   ; résultat nul et pas de sortie série → cible calculée 0x4021457D
4021442F  l32i.n a0,a1,0xc
...
40214440  l32r a9,0x40214390
40214443  jx a9
```

La disposition de l'objet correspond aux champs de [`ESP8266HTTPUpdateServer.h` 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer.h) : `this+0x20` est l'emplacement candidat `_authenticated` et `this+0` celui du booléen `_serial_output`. Le chemin en cas de résultat nul rejoint une sortie ou une action de diagnostic, conforme à l'architecture du serveur OTA public. **La source précise du booléen `a2`, calculée dans le trou de désassemblage `0x402143E4..0x40214420`, n'est pas établie** : nous prouvons sa sauvegarde et son branchement, pas les conditions exactes de `authenticate()`.

**Constat local fortement étayé :** le firmware constructeur **sauvegarde puis teste** un résultat d'autorisation pendant START. Cela ne prouve pas que la configuration OEM impose un mot de passe non vide.

### Le chemin WRITE reste distinct : absence de lecture directe observée, pas preuve de vulnérabilité

Le reçu V10 recoupe `0x402143A3 : l32i.n a3,a2,4` puis `0x402143AE : bnez a14,...` sur l'arête non-START vers `0x402144C0 : beqz a3,...`. Le registre `a3` conserve sur **cette arête directe** le pointeur `this+4` (candidat `_server`). `0x402144C3` discrimine le statut WRITE, puis `0x402144C6 : addi a2,a2,0x24` précède `String.length()` sur le champ erreur candidat, et `0x402144EC` appelle `0x40224608` (WRITE très fortement identifié par V9).

**Nous n'observons pas de lecture de `this+0x20` sur l'arête non-START décodée avant WRITE.** Le premier garde de ce chemin (`beqz a3`) ne teste donc pas directement `_authenticated`, contrairement aux clauses `_authenticated && status == UPLOAD_FILE_WRITE` et `_authenticated && status == UPLOAD_FILE_END` de la [source publique 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h).

**HOLD :** aucune preuve que le dispatch OEM appelle ce callback sur des chunks non autorisés, qu'il n'existe aucun contrôle en amont, que `Update` puisse rester actif entre requêtes, ou qu'une écriture non authentifiée soit effectivement possible. **Ne pas conclure à une vulnérabilité exploitable.** Il est néanmoins **non justifié** de déclarer que le chemin WRITE OEM est protégé par une lecture explicite de `_authenticated` dans le callback décodé.

### Nouvelle cible BEGIN probable vérifiée dans les octets OEM officiels

En plus du reçu Capstone V10, **les octets réels du BIN OEM V9.0.44 ont été relus séparément depuis son ZIP officiel**, au commit déjà épinglé `55d7877fcba8b1cb7a66a0830d35d5b374bc8540`. Deux motifs `CALL0` présents dans les blocs START convergent :

| Site OEM | Octets directement lus | Cible CALL0 calculée depuis les octets | Note |
|---|---|---|---|
| `0x40214481` | `85 25 10` | **`0x402246DC`** | précédé de `42 a0 64` à `0x4021447C`, conforme à `movi a4,100` / **`U_FS=100`** |
| `0x402144B2` | `85 22 10` | **`0x402246DC`** | branche voisine correspondant au candidat firmware |

À la cible `0x402246DC`, les octets initiaux OEM sont **`12 c1 d0`** (prologue compatible avec fonction Xtensa). Le Core public définit [`U_FS=100` et `U_FLASH=0`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.h) et expose `UpdaterClass::begin(size,command,...)`. La convergence des deux branches et la constante `U_FS` constituent une **attribution forte mais encore HYPOTHÉTIQUE** de `0x402246DC ≈ Update.begin()` : **ces deux motifs CALL0 n'ont pas encore été décodés comme instructions atteignables dans les fenêtres V10**, et le corps de `0x402246DC` n'a pas été désassemblé.

**Prochaine investigation bornée :** (1) décoder le trou `0x402143E4..0x40214420` pour trouver la provenance du booléen d'autorisation ; (2) décoder les deux frontières `0x40214481` et `0x402144B2` et `0x402246DC` pour confirmer BEGIN ; (3) étudier le **dispatch / préconditions** de la lambda d'upload avant de déclarer une garantie ou une faille. **Aucune modification SmallTV, UART, OTA, Wi-Fi, flash, firmware SHINO, Codex ou B5.3**.


## 8. Chronologie des callbacks dans le Core public : importance du contrôle pré-écriture

**Comparaison à une source publique précise — ne constitue pas une mesure du firmware OEM.** Dans [`ESP8266WebServer/src/Parsing-impl.h` tag `3.1.2`](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/Parsing-impl.h), la séquence de traitement d'un `multipart/form-data` est :

1. `_parseRequest` sélectionne `_currentHandler` selon URI/méthode, puis **appelle `_parseForm(client,...)` avant de retourner** ;
2. `_parseForm` crée `HTTPUpload`, fixe `UPLOAD_FILE_START` et appelle `_currentHandler->upload(...)` ;
3. le parseur met le statut à `UPLOAD_FILE_WRITE`, traite les octets, et rappelle `upload(...)` en cours de transfert dans `_uploadWriteByte` ;
4. à la fin, il rappelle `upload(...)` pour les derniers octets, puis avec `UPLOAD_FILE_END` ; en cas de problème, il peut appeler `UPLOAD_FILE_ABORTED` ;
5. le serveur [`ESP8266WebServer-impl.h` du même tag](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h) n'appelle `_handleRequest()` (gestionnaire de réponse POST final) **qu'après** le retour normal de `_parseRequest`.

**Conséquence architecturale PROUVÉE POUR LE CODE PUBLIC :** la réponse HTTP 401 de la phase finale ne constitue **pas** une barrière *pré-body* : les appels d'upload ont lieu plus tôt. L'authentification doit donc soit filtrer avant ce dispatch, soit **empêcher tout `Update.begin/write/end` dans les callbacks non autorisés**. La version publique [`ESP8266HTTPUpdateServer-impl.h` 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) teste effectivement `_authenticated` dans les branches WRITE/END.

**Limite appliquée à GeekMagic :** les octets OEM V10 montrent très fortement un stockage/test d'état `_authenticated` en START, et une branche WRITE où la lecture correspondante n'apparaît pas ; mais **la provenance exacte du serveur compilé, les contrôles supplémentaires avant dispatch, les préconditions du moteur Update et les chemins complets d'erreur restent non démontrés**. La différence statique justifie une revue de sécurité **HOLD**, pas une déclaration de vulnérabilité exploitable et pas une expérimentation réseau sur le SmallTV.

**Décision pour SHINO :** conserver une autorisation indépendante, authentifiée et **effective avant toute écriture**, liée à chaque transaction, y compris ERROR, INTERRUPTION, RESTART et END ; ne jamais tenir le code HTTP final comme une garantie d'intégrité/accès. Cette préconisation est une règle de conception, **pas une modification du firmware effectuée dans cette recherche**.

## 9. Invariants de session Updater à ne pas confondre avec l'authentification — audit complémentaire

**Date : 17 octobre 2026.** Nouvelle lecture **des sources publiques exactes**, pas un désassemblage supplémentaire du constructeur et **pas un test physique**. Les quatre ZIP de reçus propriétaires **V7/V8/V9/V10** ont été relus et leur intégrité `ZipFile.testzip()` contrôlée **PASS**. Dans ces fragments seulement, les accès `this+0x20` attribuables à l'état d'authentification se trouvent dans **POST A** (lecture à `0x40212021`) et **START/POST B** (écriture à `0x40214423`) ; les fragments délimités de WRITE/END montrent l'accès au champ `this+0x24` d'erreur et non au booléen d'autorisation. Cette observation est **limitée aux fenêtres décodées** et n'établit pas l'absence de garde dans tout le logiciel.

### Contrat vérifié de l'Updater Arduino ESP8266 3.1.2

Les routines ci-dessous ont été lues dans [`Updater.cpp` au tag 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp), avec constantes/structures dans [`Updater.h`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.h).

| Situation | Effet prouvé dans le code public | Ce que cela **ne** garantit **pas** |
|---|---|---|
| `begin(size, ...)` alors que `_size > 0` | Retourne `false` si une session Updater est déjà active | Aucune liaison à l'identité réseau ni annulation de l'ancienne session |
| `write(data,len)` avec `hasError()` ou `!isRunning()` | Retourne **0**, sans écrire les données fournies dans cet appel | Pas un test d'authentification ; un Updater déjà actif peut accepter les écritures du mauvais appelant si l'application les laisse passer |
| `write` au-delà de la taille autorisée | Déclenche `UPDATE_ERROR_SPACE`, puis le chemin `_setError()` invalide la session | Ne prouve pas que l'appelant a été autorisé à commencer la mise à jour |
| `_setError(...)` | Réinitialise l'état de mise à jour en appelant `_reset()` | Ne prouve pas l'effacement physique de données déjà placées en zone staging |
| `end(true)` | Autorise à finaliser selon les octets effectivement reçus : `_size = progress()` si les autres vérifications passent | **N'impose pas à lui seul** la taille exacte attendue d'un candidat SHINO |
| `end` sur `U_FLASH` après les vérifications de ce Core | Programme la commande `eboot ACTION_COPY_RAW` | Ne prouve ni l'exécution eboot, ni le boot d'une image OEM, ni la validation postboot |

Une lecture directe de [`ESP8266HTTPUpdateServer-impl.h` 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) montre que le callback START retourne immédiatement si l'authentification échoue, **sans appeler explicitement `Update.end()` dans cette branche** ; cela n'autorise **aucune conclusion de vulnérabilité OEM** puisque les requêtes, préconditions et lifetimes réels ne sont pas établis. Pour le produit SHINO, il faut néanmoins vérifier la gestion des sessions déjà ouvertes, des interruptions et des transferts suivants.

### Critères concrets pour SHINO, à vérifier dans son code actuel et ses tests

Une solution robuste exige que chaque réception fasse l'objet d'une **autorisation liée à une transaction identifiée et bornée**, validée **avant les effets flash** ; qu'un nouveau START invalide proprement tout état précédent non autorisé ; que WRITE/END/ABORTED et les interruptions refusent les anciennes transactions ; que `end(true)` ne soit jamais pris pour une validation de taille sans contrôle applicatif de la **longueur, du SHA et de la signature attendus** ; et que **commande eboot créée, firmware installé et firmware effectivement démarré** restent trois résultats distincts.

**ÉTAT :** vérification de contrat source **PROUVÉE POUR LE CORE PUBLIC**. **HOLD POUR LE BINAIRE OEM** : version exacte du Core compilé, état d'autorisation effectif de chaque requête, appel BEGIN `0x402246DC` encore non désassemblé, activation eboot et postboot. **HOLD POUR LE FIRMWARE SHINO** tant qu'une revue/test sur son code au commit concerné n'a pas été faite. Ce document n'implémente pas ces contrôles et ne change aucun composant.

**Aucune opération SmallTV, Wi-Fi, UART, flash, OTA, reboot, fusion, modification du firmware ni intervention B5.3.**
