# Reçu OEM V9 — identification statique du chemin Updater WRITE

**17 octobre 2026 — Analyse lecture seule.** État : **WRITE fortement identifié statiquement ; END partiel ; auth/signature/eboot/postboot HOLD**.

Sources : reçu Windows propriétaire `SHINO-OEM-UPDATER-V9-20261017-113327.zip` et sources publiques [ESP8266 Core 3.1.2 `Updater.h`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.h), [`Updater.cpp`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp) et [`WString.h`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/WString.h). Le rapport précédent est [POST_UPLOAD_STATIC_V8.md](POST_UPLOAD_STATIC_V8.md).

## 1. Intégrité et niveau des preuves

- Archive V9 reçue : **6 850 octets**, SHA-256 **`fed135915e77f33c565429faa1aed4a2ceb611fdce3c369f1cbf1f0b01730ed0`**, test ZIP `testzip() == None` (**PASS**), SHA calculé directement sur l'archive de conversation.
- Contenu : `updater_calltrace_v9.json` + **11 listings Capstone Xtensa**, correspondant à **11 fenêtres décodées sur 12**. HOLD sur la fenêtre `0x402246C0`, « Capstone decoded zero instructions ».
- Reçu : `HOLD_UPDATER_FUNCTION_IDENTITIES_AND_OTA_SECURITY_NOT_PROVEN`. Les SHA du firmware officiel V9.0.44 cités dans le reçu concordent avec le [manifeste OEM de cet audit](EVIDENCE_MATRIX.md) : ZIP `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f`, BIN `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`, 494 144 octets. **Ces empreintes proviennent du reçu et de la provenance déjà établie ; ne pas présenter une nouvelle mesure OEM effectuée ici**.
- Contrôle indépendant du reçu : **215 lignes d'instruction** réparties sur les fenêtres qui se recouvrent, **179 adresses PC distinctes**. Toutes les **14/14 entrées CALL0** du champ `decoded_direct_calls` sont présentes dans les listings et correspondent par décodage indépendant à leurs **octets et destinations**. Ce sont 14 **enregistrements**, avec sites dupliqués entre fenêtres, pas 14 fonctions uniques. Une fenêtre décodée n'implique pas la couverture de la fonction complète.
- Aucune exécution sur le SmallTV, aucun flash/OTA, aucun symbole ELF constructeur retrouvé, aucune preuve de CI matérielle.

## 2. `0x4022FD4C` : identification de `String.length()` de haute confiance

Le désassemblage réel révèle :

```asm
4022FD4C  mov.n  a3, a2
4022FD4E  l8ui  a2, a2, 0xb
4022FD51  bbsi  a2, 7, ...
4022FD54  l32i.n a2, a3, 8
4022FD56  extui a2, a2, 0x18, 7
...
4022FD5C  l32i.n a4, a3, 0
4022FD60  beq a4, a2, ...
4022FD63  l16ui a2, a3, 6
4022FD66  ret.n
```

Le Core public `WString.h` 3.1.2 définit le `String` sur une union `_sso`/`_ptr` de 12 octets : dernier octet `+0x0B` contient `isHeap` bit 7 et la longueur SSO sur 7 bits ; en mode pointeur, `_ptr.len` est un `uint16_t` à `+0x06` et la validité dépend de `_ptr.buff` à `+0`. Cette séquence correspond précisément à la logique d'accès de `String.length()`. **Attribution statique de haute confiance**, pas une confirmation de l'identité exacte de la version Core livrée par GeekMagic.

Dans le code POST B, cet appel est effectué avant WRITE et END sur un sous-objet `String` ; cohérent avec le test `!_updaterError.length()` de [`ESP8266HTTPUpdateServer-impl.h`](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h). Le champ/mot passe d'authentification reste **HOLD**.

## 3. `0x40224608` : correspondance de plusieurs champs et erreurs d'`UpdaterClass::write`

Le listing `00_write_candidate_entry_40224608.txt` décode **54 instructions** depuis le prologue `0x40224608 : addi a1,a1,-0x30` jusqu'à `0x40224688`. Le listing `01` recoupe la région ; la fenêtre à `0x40224680` décodée depuis **une frontière décalée d'un octet** ne valide pas de continuation automatique : ne pas relier naïvement ses quatre instructions au flot principal.

Dans le corps d'entrée, les accès exacts dans l'objet du receveur (`a2` puis `a12`) sont :

| Adresse OEM | Instruction réelle | Correspondance source `Updater.h` (ABI ESP8266 32 bits) |
|---|---|---|
| `0x4022461A` | `l8ui a4,a2,1` | `_error` à **+1** |
| `0x40224629` | `l32i.n a15,a2,0x10` | `_size` à **+0x10** |
| `0x4022462E` | `l32i.n a3,a12,0x18` | `_currentAddress` à **+0x18** |
| `0x40224630` | `l32i.n a2,a2,8` | `_bufferLen` à **+0x08** |
| `0x40224636` | `l32i.n a3,a12,0x14` | `_startAddress` à **+0x14** |
| `0x40224650` | `l32i a6,a12,8` | `_bufferLen` |
| `0x40224656` | `l32i.n a2,a12,4` | `_buffer` à **+0x04** |
| `0x4022465B` | `l32i.n a7,a12,0xc` | `_bufferSize` à **+0x0C** |

La fonction sauvegarde `len` depuis `a4` vers `a14`, puis combine `_currentAddress + _bufferLen + len - _startAddress` et compare cette progression à `_size` (instructions `0x4022462E..0x4022463D`). La branche de dépassement fait `movi.n a3, 4` à `0x40224640`, puis `call0 0x40224458` à `0x40224646`. Le Core épinglé définit **`UPDATE_ERROR_SPACE == 4`**, et `UpdaterClass::write()` appelle `_setError(UPDATE_ERROR_SPACE)` à ce même endroit logique.

Une autre portion calcule des pointeurs de source/destination et copie des octets avec `callx0` à `0x40224674`, puis incrémente `_bufferLen` et appelle `0x40224528` à `0x40224681`. **L'identité de l'appel indirect (par exemple `memcpy`) et de `0x40224528` reste à déterminer avant de les nommer.**

**Verdict WRITE :** correspondance indépendante de l'ABI, du contrôle d'erreur, de l'arithmétique de progression, du contrôle d'espace et du code d'erreur. Il est **très fortement étayé** que `0x40224608` implémente un `UpdaterClass::write(uint8_t*,size_t)` compatible avec le Core Arduino 3.1.2. Cela ne prouve pas que le corps est **binaire-identique**, que l'OTA constructeur applique une signature ou que toute écriture soit précédée d'un contrôle d'accès.

## 4. `0x40224830` : fonction END cohérente mais encore discontinue

Le listing `04_end_candidate_entry_40224830.txt` décode dix instructions, incluant :

```asm
40224830  movi a9, 0xc0
40224833  sub a1, a1, a9          ; pile locale 192 octets
4022483B  l32i.n a2, a2, 0x10    ; candidat _size
40224849  extui a13, a3, 0, 8   ; argument booléen
```

Ce préfixe est compatible avec `UpdaterClass::end(bool evenIfRemaining)`. Le listing séparé `06_end_candidate_middle_b_402248A0.txt` montre des conditions sur `_size` et la progression, des appels directs vers `0x4022226C`, `0x40224458` et `0x402243EC` ; **mais aucune preuve de continuité d'exécution entre l'entrée et cette fenêtre**. La fenêtre `0x402248E0` produit une séquence de quatre instructions ambiguës qui ne doit pas être considérée atteignable.

**Verdict END :** attribution `0x40224830` à une fonction du type `UpdaterClass::end(true)` **fortement plausible**, mais **pas encore prouvée** pour les étapes de vérification d'intégrité/signature, d'activation eboot et de succès postboot.

## 5. START, authentification et limites

Le désassemblage V9 `0x4020B454` efface un pointeur global, libère conditionnellement une ressource via un appel et remet le pointeur à zéro. **Ne pas l'attribuer à `UpdaterClass::begin`** : il est seulement un *callee observé* dans une branche START candidate. Les véritables appels du START vers `Update.begin(...,U_FLASH)` doivent encore être isolés.

**Bloqueurs actuels :** code de vérification des identifiants avant `UPLOAD_FILE_START`, suivi exact des erreurs et `UPLOAD_FILE_ABORTED`, contrôle éventuel de signature/MD5, activation eboot et validation postboot. Le fait que POST A construise un défi Basic 401 ne constitue pas une preuve du blocage pré-écriture dans POST B.

**Prochaine action bornée :** privilégier l'examen des corps `0x40224528` (flush/buffer candidat), `0x40224458` (erreur candidate) et du *vrai* callee BEGIN dans START ; pour END, reconstruire les branches d'entrée avant de suivre eboot. Si l'identité ou la continuité n'est pas prouvée, conserver HOLD. Pas de nouveau test matériel ni de modification du firmware SHINO à ce stade.

**Sécurité :** aucune écriture de flash/OTA/reboot, aucune intervention USB/UART ou Wi-Fi, aucun secret, aucune modification Codex/B5.3. La PR documentaire reste Draft et ne doit pas être fusionnée sans relecture.
