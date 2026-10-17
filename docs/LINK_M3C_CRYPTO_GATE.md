# SHINO // LINK — M3-C : prototype cryptographique pré-corps isolé (17 octobre 2026)

**Décision propriétaire : GO M3-C logiciel/qualifications offline.**
**ÉTAT : PROTOTYPE HORS LIGNE — PAS DE NOUVEL ENDPOINT, PAS DE FIRMWARE DÉPLOYABLE.**

Base : PR #57 M3-B (`f6a7eca739b391bb5d912257947ace722096b75d`), dont les six
workflows CI étaient SUCCESS avant branchement. M3-C utilise une branche
distincte de Codex B5.4 ; B5.3 est conservée sur le SmallTV.

## Ce qui existe réellement

`experiments/link_m3c_crypto/M3CAuthenticatedIngress.h` met en œuvre,
dans un **composant C++ isolé et à allocations fixes**, les deux étages
d'une future commande de mode :

1. **Avant tout octet de corps**, vérifier le début de requête HTTP/1.1
   exact (méthode POST, chemin `/api/v1/display/mode`, Host attendu),
   les onze en-têtes exigés, l'absence de champs supplémentaires ou doublés,
   les tailles, le mode, l'appareil, le boot et la révision CAS attendus.
   Calculer et comparer en temps indépendant du contenu la preuve HMAC-SHA-256
   de **tous** ces éléments et de l'empreinte du corps annoncée.
2. **Après authentification de l'en-tête seulement**, absorber exactement
   le nombre d'octets annoncé (maximum 240), calculer SHA-256 sur les octets
   reçus, contrôler l'empreinte annoncée et l'égalité exacte au JSON
   canonique M3-A (six champs exacts). Exiger ensuite un FIN propre, sans
   octets supplémentaires en attente, avant le statut `VerifiedFrame`.
   Aucun mode, pixel, LittleFS, RTC ou état durable n'est modifié.
3. Un `OfflineCasLedger` de laboratoire démontre l'incrément de révision
   et le refus d'un même `tx`, d'une révision périmée ou d'une commande
   répétée **en mémoire et en série seulement**. Ce modèle ne prouve pas
   l'atomicité entre tâches, l'anti-rejeu au redémarrage, l'unicité des boots,
   l'émission/gestion de nonce ni la persistance.
4. `M3CBearSslCrypto.h` utilise réellement les primitives
   **BearSSL SHA-256 et HMAC-SHA-256** du cœur ESP8266 épinglé.
   `test_crypto_ingress.cpp` emploie un second fournisseur cryptographique
   **OpenSSL réel** sur Linux HOST, ainsi que des valeurs attendues
   calculées indépendamment avec Python stdlib.
5. Un `platformio.ini` isolé compile/lie un **programme ESP8266 inerte**
   contre `espressif8266@4.2.1`,
   `framework-arduinoespressif8266@3.30102.0`, linker
   `eagle.flash.4m2m.ld`. Cette image ne contient aucun serveur,
   lecture de clés privées, commande réseau ou contrôle matériel ;
   **ne jamais la flasher**. Le résultat de taille/stack éventuel décrit
   *ce programme inerte*, PAS une marge mémoire du firmware B5.3/B5.4.

## Profil MAC candidat — non provisionné

En-têtes obligatoires sur `POST /api/v1/display/mode HTTP/1.1` :
`Host`, `Content-Type: application/json`, `Content-Length`,
`Connection: close`, `X-Shino-Device` (16 hex), `X-Shino-Boot`
(32 hex), `X-Shino-Revision` (uint32, sans wrap),
`X-Shino-Mode` (4 valeurs), `X-Shino-Tx` (32 hex),
`X-Shino-Body-Sha256` (64 hex),
`X-Shino-Proof` (HMAC SHA-256, 64 hex). Tous les autres en-têtes,
notamment TE, Expect, Cookie, Basic/Digest normal, encodages ou colonnes
dupliquées sont rejetés dans le prototype.

La preuve pré-corps porte sur la représentation canonique (UTF-8 ASCII,
LF, sans LF final) :

```text
SHINO-M3-CONTROL-1
POST
/api/v1/display/mode
<Host>
<device>
<boot>
<revision decimal>
<mode>
<tx>
<Content-Length decimal>
<Body SHA256 lowercase>
```

La clé HMAC de 32 octets est une **dépendance externe**, qui devra être
dédiée exclusivement aux commandes d'affichage. Les tests utilisent
uniquement le vecteur public `01 02 ... 20`. **Aucun secret utilisateur
n'a été consulté, ajouté ou provisionné**. L'HMAC de démonstration
n'est pas une identité appareil en production, ni la protection du réseau
LAN contre les captations de messages.

Les limites de prototype : en-têtes ≤1024 octets, ligne ≤320,
corps ≤240 ; modèle d'horloge injectée 1000 ms (en-têtes) et
2000 ms (corps). **Ce ne sont pas des garanties de planification/WDT
sur appareil**, et le lecteur de socket qui empêcherait la
prélecture reste à implémenter/qualifier.

## Architecture critique encore manquante — HOLD

**Ne pas enregistrer** `/api/v1/display/mode` via `server.on()`
du WebServer épinglé : le corps serait bufferisé avant authentification
du handler. Notre C++ `headerByte()` accepte l'injection d'un octet à la
fois, mais n'est relié à **aucun WiFiClient/WiFiServer**, ne possède
pas le port 80, ne sait pas transférer la connexion au serveur existant et
ne gère pas le graphe natif B5.3/B5.4.

Il reste obligatoirement à prouver :
- Un seul propriétaire du listener TCP (pas de second `WiFiServer`).
  Coexistence fidèle des GET de dashboard/status/secours, des quatre
  mesures LINK, du clock publisher, Digest et des chemins OTA.
- Une clé de contrôle réellement provisionnée en sécurité, séparée
  des privilèges de flash/OTA, rotation/révocation et protection contre
  l'exfiltration, sans importer une clé privée dans le dépôt.
- Génération et conservation sûres d'identité de boot et de nonce/tx,
  unicité après coupure, CAS atomique, anti-rejeu même après redémarrage.
- Connexion interrompue, TCP FIN et octets retardataires, fermeture
  forcée, slowloris, saturation, renvoi des erreurs, planification,
  absences réseau et timing réel sur ESP8266.
- Liaison d'un mode effectivement appliqué à un ACK et un GET distinct,
  sans confondre le mode demandé/confirmé, et scènes natives 240×240.
- Compilation réelle B5.3/B5.4, pile native, high-water heap/largest
  block, flash layout, AP/LAN, watchdog et récupération. Les gates
  `verified/sdkStackCovered/sharedPoolsCovered/schedulerCovered`
  de la météo B5.4 restent séparés et fermés tant que Codex
  ne les prouve pas.

**CRITÈRE DE M3-C PROTOTYPE :** compilations/exécutions HOST sur vrais
algorithmes, cross-compilation Xtensa du composant inerte et tests
négatifs sur le SHA exact de la PR. **Pas de PASS pour M3 en production**,
pas de GO OTA ni de build candidat à installer.

Le parcours sécurisé suivant est d'intégrer l'adaptateur dans un
serveur unique **hors ligne sur image native de qualification**,
préserver les chemins existants, mesurer les ressources et coordonner
l'évolution avec Codex B5.4. Consentement propriétaire distinct,
candidat exact et preuve de récupération avant tout essai physique.
