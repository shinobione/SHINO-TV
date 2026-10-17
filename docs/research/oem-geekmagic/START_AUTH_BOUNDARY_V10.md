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
