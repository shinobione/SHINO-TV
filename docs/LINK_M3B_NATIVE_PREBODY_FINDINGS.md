# SHINO // LINK — M3-B : sûreté de l'entrée HTTP native (17 octobre 2026)

**Source de départ :** PR #56 M3-A à `d6aa1a7ded68b4997f9cf258d48124f3a0f99426`.
**État : AUDIT PINNED-CORE + C++ LABORATOIRE REJECT-ONLY. AUCUN ENDPOINT M3 ACTIF.**

## Pourquoi un POST ordinaire est bloqué

Le code Arduino Core ESP8266 **3.1.2** installé par PlatformIO
`framework-arduinoespressif8266@3.30102.0` est vérifié par les six SHA-256
de `tools/v07_pinned_core_probe.py` **avant** d'en tirer les assertions CI.
Les résultats de recherche existants de
`docs/V07_NATIVE_INGRESS_AUTH_REVIEW.md` (Mission 2) concordent :

- `Parsing-impl.h::_parseRequest` lit la ligne de requête par
  `client.readStringUntil('\r')` vers un `String` sans cap de ligne.
- Le hook `_hook(methodStr, url, &client, ...)` est appelé **après**
  cette allocation, **avant** la lecture des en-têtes.
- Les requêtes POST ordinaires lisent `Content-Length` dans un
  `plainBuf` `String` via `readBytesWithTimeout`, puis le corps
  est copié en argument `plain`. Le handler `server.on()` est
  exécuté seulement **après** la réussite de `_parseRequest`.
- Le Digest d'origine vérifie un URI déclaré par le client plutôt que
  de comparer systématiquement l'URI réel de la requête à celui de la preuve,
  utilise un nonce/opaque global au serveur et n'intègre ni
  `Content-Digest`, ni `auth-int`, ni protection complète contre
  les rejouements. L'obligation de Digest du handler applicatif ne
  répare pas cette séquence.
- `firmware/src/boot/M9NormalStageA.cpp` utilise actuellement
  `service.on` pour télémétrie et GET et `server.authenticate`
  dans le handler. **Ce chemin doit rester inchangé** pour B5.3/4 ;
  il ne constitue pas un adaptateur M3 sécurisé.

L'API `addHook` seule est donc **INSUFFISANTE**, et un
`service.on("/api/v1/display/mode", HTTP_POST, ...)` est
**BLOQUÉ** tant que l'authentification avant lecture du corps
n'est pas native et démontrée.

## Réalisation M3-B : preuve C++ bornée, pas authentification

Le fichier `experiments/link_m3_native_prebody/M3ModePrebodySyntax.h`
est une **implémentation C++ autonome, sans Arduino, socket ni route active**,
qui reçoit un octet de la seule *zone en-têtes* à la fois et s'arrête
exactement à CRLFCRLF. Ses bornes proposées :

| Ressource laboratoire | Limite |
| --- | --- |
| Tampon statique des en-têtes | 512 octets |
| Ligne | 256 octets |
| Nombre de champs | au plus 8 (seuls 6 champs exacts admis) |
| Corps déclaré `Content-Length` | de 1 à 240 octets |
| Échéance depuis début (temps injecté) | 1 000 ms |

Ces valeurs sont **des paramètres de prototype**, jamais un budget ESP8266
qualifié ou une borne temporelle du système réel. La boucle réseau
native n'existe PAS dans cette PR.

Le scanner refuse : ligne/target/méthode inattendus, alias/query,
Host différent, `Content-Type` erroné, CL mal formé, doublons de
noms (insensibles à la casse), en-têtes inconnus ou interdits
(`Transfer-Encoding`, `Expect`, `Content-Encoding`, Origin),
pipelining interprété comme header, fin de ligne LF isolée, lignes
malformées, faux schéma Basic/Bearer, champ transaction hexadécimal
mal formé et dépassements de budget. Aucun corps n'est *présenté*
à ce scanner ; une preuve grammaticale s'arrête avant le premier
octet de corps dans le laboratoire.

**Attention :** `Authorization: Digest ...` et `X-Shino-Tx`
sont seulement des **chaînes non fiables** dans ce composant.
Le scanner peut renvoyer `CandidateSyntaxOnly`, mais
`authorizedToReadBody()` renvoie **toujours `false`**.
Un attaquant pourrait écrire `Digest ATTACKER-FORGED`, qui
passe volontairement le test de forme mais **n'autorise
jamais le corps**. C'est un refus d'activation démontré,
pas un mécanisme d'authentification.

La grammaire de POST M3-A reste **proposée** ; la duplication du
`tx` dans `X-Shino-Tx` est un candidat de pré-admission
**non authentifié**, et devra être lié cryptographiquement au corps
et à la vraie cible. Le vrai serveur ne partage pas encore ce
contrat. Aucune sécurité n'est déduite du mot « Digest ».

## Résultats et limites exigées pour la suite

Le workflow `LINK M3-B pinned native prebody research` installe
le **cœur épinglé** puis exécute les assertions de source exactes
et la compilation/exécution de `test_m3_prebody.cpp`.
Il teste le scanner lui-même en C++, sans le confondre avec
un `WiFiClient`, un parseur HTTP complet ou un flux radio/Wi-Fi.
Il n'utilise pas de credentials, de simulateur réseau ni d'image BIN.

| Gate | Statut |
| --- | --- |
| 3.1.2 + six empreintes exactes, ordre parsing/hook/auth | À confirmer en CI SHA exact |
| C++ scanner syntaxe, tailles, doublons, no-body, deadline modèle | À confirmer en CI SHA exact |
| Lecture ligne HTTP réellement bornée **avant** `String` Arduino | **HOLD** |
| HTTP Digest pré-corps + exact target + nonce/boot/anti-rejeu | **HOLD** |
| Signature/Content-Digest ou MAC du corps, accord avec M3-A | **HOLD** |
| Propriétaire unique du port HTTP, récupération/interruptions | **HOLD** |
| Accès WiFiClient / timeouts absolus / équité télémétrie | **NON IMPLÉMENTÉ** |
| Vrai linkage Xtensa, heap, stack, IRAM et watchdog | **NON MESURÉS** |
| Mode ACK/status et écran 240×240 natifs | **NON IMPLÉMENTÉ** |
| SmallTV B5.3/B5.4 firmware, OTA, flash, Wi-Fi, reboot | **INCHANGÉS** |

**Décision M3-B :** ne jamais déplacer `M3ModePrebodySyntax.h`
sous `firmware/` sans une architecture pré-corps révisée qui
conserve **un seul** propriétaire du port, prouve l'authentification
et la livraison du corps authentifié à la machine d'état,
et établit ses budgets réels. Aucune modification
de `M9NormalStageA.cpp`, `shino_link.py`, LittleFS,
B5.4 Codex, ou des guards historiques Mission 9.

**Critère du prochain M3-C :** une vraie implémentation pré-body,
avec byte caps **avant** les `String` Arduino, garantie d'unique
port, cryptographie liée à la cible, au boot/transaction/corps,
preuves native Xtensa et scénarios concurrence, coupure/reboot,
sans écarter le risque de corruption d'image ou d'OTA.
Aucune opération physique avant nouveau consentement explicite.
