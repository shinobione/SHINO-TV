# GeekMagic OEM V9.0.44 — callbacks POST et défi HTTP Basic (V7)

**17 octobre 2026 · Lecture seule · ÉTAT : AUTH-CHALLENGE-PATH STATICALLY SUPPORTED / OTA ACCEPTANCE HOLD.**

Ce document prolonge [l'analyse des pointeurs V7](CALLBACK_POINTERS_V7.md) et [l'audit de la route `/update`](UPDATE_ENTRYPOINT_TRACE.md). Il décrit le **code OEM statique** et les **listings Capstone Windows fournis par le propriétaire**, mais ni une réponse réelle observée du SmallTV ni une preuve de programmation OTA.

## 1. Reçu de preuve

- Archive utilisateur : `SHINO-OEM-CALLBACK-20261017-104339.zip`.
- Taille mesurée : **8 491 octets** ; SHA-256 calculé sur le ZIP reçu : `ac61a12abd87342579e8bed3c791382993bf7355091c36115cc1306a8e772eff` ; test intégrité ZIP : **PASS**.
- Contenu : `callback_trace_v7.json` + **14 listings Xtensa**. Les **14 fenêtres** ont `provider: CAPSTONE` et `reason: null`, mais plusieurs listings s'arrêtent après un petit nombre d'instructions : **décodage partiel, pas décompilation des fonctions complètes**.
- Reçu V7 : `HOLD_CALLBACK_AUTH_AND_FLASH_BEHAVIOR_UNVERIFIED`. SHA-256 ZIP et BIN OEM V9.0.44 concordants avec le [manifeste OEM épinglé](../../../recovery/factory_ota_v9_0_44.json). Les dix littéraux et cinq relais sont cohérents avec l'[audit V7 des pointeurs](CALLBACK_POINTERS_V7.md).
- Le ZIP et les listings complets **ne sont pas redistribués dans Git** ; seules des instructions significatives et observations nécessaires y figurent.

## 2. Callbacks POST : deux corps distincts

Le relais candidat **POST A** `0x40212178` mène à `0x40211FB8` : reçu V7 `03_POST_body_candidate_A_40211FB8.txt`, **109 lignes d'instructions**, de `0x40211FB8` à `0x402120CE`, incluant une instruction finale potentiellement mal délimitée hors chemin. La routine commence par un prologue de pile `addi a1,a1,-0x60`, effectue plusieurs appels et branches et **n'est pas entièrement parcourue jusqu'au retour** dans le listing.

Le relais candidat **POST B** `0x4021458C` mène à `0x40214398` : reçu `04_POST_body_candidate_B_40214398.txt`, **30 lignes d'instructions** de `0x40214398` à `0x402143E1`, avec un prologue `-0x10`, des accès mémoire, une branche `bnez` et des appels ; **son comportement principal n'est pas encore retracé**. La correspondance « A = callback de fin, B = callback d'upload » est **une hypothèse fondée sur la structure du code et la signature `on(..., HTTP_POST, cb, upload_cb)` du Core public, pas une attribution binaire prouvée**.

## 3. Découverte : chemin de défi HTTP Basic 401 dans POST A

**Octets OEM corroborés :** le BIN constructeur V9.0.44 a été récupéré de nouveau depuis le commit officiel épinglé, extrait **en mémoire**, puis les mots littéraux ci-dessous ont été relus indépendamment du reçu V7.

| Élément | Adresse et contenu directement vérifiés | Ce qui est établi |
|---|---|---|
| Lecture de champ objet | `0x40212021 : l8ui a14,a2,0x20` suivi de `0x40212026 : bnez a14,+0xaa` | Branche conditionnelle selon un champ ; sa signification exacte reste HOLD |
| Chaîne « Login Required » | littéral `0x40211F94` → `0x4026F994` | Texte OEM présent et référencé dans POST A |
| Nom d'en-tête `WWW-Authenticate` | littéral `0x40211F98` → `0x4026A9CC` | Texte OEM présent et référencé dans POST A |
| Préfixe de valeur `Basic realm="` | littéral `0x40211F9C` → `0x4026F984` | Construction d'un défi **HTTP Basic** fortement étayée |
| Code 401 | `0x402120BB : movi a3,0x191` | Valeur décimale **401** dans le même bloc |
| Appel après préparation | `0x402120C0 : call0 0x40211F7C` | Destination d'appel recalculée depuis les octets du listing ; comportement précis du callee HOLD |

Deux autres littéraux du POST A pointent sur `Access-Control-Allow-Headers` et `Access-Control-Allow-Origin`, à `0x40211F8C` et `0x40211F90`, respectivement. Cela recoupe la structure OPTIONS/POST du [serveur de mise à jour Arduino public](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h).

**Comparaison de source exacte :** dans [`ESP8266WebServer-impl.h`, tag 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h), `requestAuthentication(HTTPAuthMethod, realm, authFailMsg)` :
- définit le royaume par défaut `Login Required` ;
- construit `WWW-Authenticate: Basic realm="..."` lorsque `mode == BASIC_AUTH` ;
- envoie une réponse **401**.

La **combinaison de ces trois chaînes, de la constante 401 et de l'appel dans une branche commune** concorde étroitement avec cette routine publique. Le résultat est **plus fort qu'un simple scan de chaînes ou du nombre 401**. Mais il ne prouve **ni** que GeekMagic utilise exactement le Core 3.1.2, **ni** la configuration `username/password`, **ni** que toute réception POST soit correctement bloquée en cas de mauvais mot de passe.

**Formulation autorisée : « Le firmware OEM contient, sur un chemin du callback POST candidat, la construction statique d'une réponse 401 avec défi HTTP Basic ».** Formulation interdite : « La mise à jour GeekMagic est sécurisée / accepte ou refuse toutes les images avec authentification », faute de validation des branches et de l'upload réel.

## 4. Indices supplémentaires, encore sans attribution métier

- La fonction `0x40211070` alloue/initialise un objet et effectue un `callx0` indirect ; `0x402110F8` prépare un objet et appelle `0x40211070`. Cela **suggère** des helpers de callback/route, mais leurs structures C++ ne sont pas rétablies.
- Les fonctions auxiliaires `0x40230238` et `0x40230274` montrent le même petit motif de branchement sur `a4` (`bnei a4,1`, `bnei a4,2`) et copie de pointeur. **Rôle exact HOLD** (ne pas les qualifier destructeurs, gestionnaires OTA ou validateurs sans ABI).
- POST B `0x40214398` lit un objet à `+0xA8` et des indicateurs, mais le listing s'arrête prématurément. **Aucune preuve encore** de contrôle `UPLOAD_FILE_START/WRITE/END/ABORTED`, `Update.begin/write/end`, staging ou commande eboot.
- Le POST A n'est pas non plus retracé jusqu'à un succès, un redémarrage ou la gestion détaillée d'un échec.

## 5. Verdict et action suivante

**ÉTAT :** les callbacks probables GET/OPTIONS/POST et **une branche de défi HTTP Basic 401** sont maintenant localisés sur de vrais octets OEM. Cette amélioration vient du reçu utilisateur V7 et d'une nouvelle vérification des littéraux officiels.

**BLOCAGE :** l'affectation exacte des deux callbacks POST et surtout le chemin d'upload `START/WRITE/END/ABORTED → Update.begin/write/end → eboot` ne sont pas démontrés. Le champ utilisé au branchement d'authentification n'est pas encore nommé, et le contrôle des credentials réel reste **HOLD**.

**RISQUE :** prendre la présence d'un défi 401 pour une preuve que l'upload ne peut pas commencer sans authentification, ou transposer les garanties supposées du constructeur dans l'OTA HMAC/SHA-256 SHINO.

**PROCHAINE ACTION TECHNIQUE :** examiner *en priorité* la suite de `0x40214398` au-delà de `0x402143E1` et le chemin de contrôle de `0x40211FB8` au-delà de la fenêtre de 288 octets ; chercher les appels vérifiables vers l'Updater et les états d'upload. Pour éviter le coût des relances en série, regrouper les deux dans **une seule investigation bornée** ; conserver HOLD si les pointeurs n'établissent pas les appels.

**Actions exécutées sur le SmallTV : AUCUNE.** Pas de flash, OTA, reboot, changement Wi-Fi, modification B5.3, secrets publiés ou intervention Codex.
