# SHINO // LINK — M3-N : vrai noyau d'authentification Digest, route métriques

**19 octobre 2026.** Autorisation propriétaire : poursuivre le logiciel
SHINO // LINK **hors appareil**. Base #68 M3-M, HEAD
`a73eca178fd04ac805a09f8dd19389535c45c232`,
**16/16 workflows PASS** vérifiés au fork. Ne pas toucher aux
branches Codex B5.4/OTA ni au SmallTV.

## Problème avéré dans les sources

`FirstBootBridge.cpp` construit `ESP8266WebServer server(80)`.
La bibliothèque ESP8266 Arduino **3.1.2** utilise son
`_server.accept()`, conserve le nonce, l'opaque et le realm
Digest dans son objet privé, et calcule MD5 de
`user:realm:password`, `method:uri`, puis
`H1:nonce:nc:cnonce:auth:H2`. Le challenge est
`Digest realm="SHINO-FirstBoot", qop="auth", nonce="…", opaque="…"`.
Le code B5.3 conserve en outre deux sessions navigateur GET
temporaires et des exigences `HomeLan` sur local/peer/Origin.
Ces preuves proviennent du code de la bibliothèque épinglée
et des véritables blobs B5.3, **pas d'un navigateur simulé**.

## Travail réel en laboratoire

- `M3NLegacyDigest.h` : parseur de champs Digest
  **max. 768 octets**, aucune duplication/clé inconnue/échappement ;
  realm, nonce, opaque, qop, nc et URI contrôlés ;
  calcul MD5 **incrémental** via le fournisseur injecté,
  comparaison constante des 32 chiffres hex ;
  challenge composé des mêmes champs que Core 3.1.2 ;
  nonce lié à remote/local IP, TTL borné et compteur nc
  strictement croissant après preuve valide (protection replay
  supplémentaire, susceptible d'affecter des clients anciens).
  Entropie **obligatoirement fournie de l'extérieur** ; la
  fixture Xtensa possède uniquement un vecteur **public
  et inerte**, jamais une vraie clé ou un vrai nonce produit.
- `BrowserReadSessions` : deux tokens GET en RAM,
  peer+local IP liés, durée 2 heures, refus des cookies
  dupliqués, expirés ou provenant d'un autre pair ; invalidation
  possible au changement AP/STA. Un cookie ne donne **jamais**
  l'autorité POST.
- `M3NMetricsAuthority.h` : applique les **véritables**
  fonctions source `HomeLan::peerOnSubnet`,
  `HomeLan::authority`, `HomeLan::endpoint`.
  Elle n'autorise **que** `/api/v1/bridge/metrics`
  puis délègue au vrai handler M3-M, qui appelle le vrai
  `FslessMetrics.cpp`. Les informations `Peer`,
  interface, IP locale, Origin et Host sont **injectées**
  par le laboratoire et devraient provenir d'un futur
  propriétaire du socket natif vérifié ; aucune confiance
  accordée aux IP fournies par HTTP lui-même.
- `M3NBearMd5.h` : adaptateur au véritable
  `br_md5_context` BearSSL Core 3.1.2, utilisé
  **uniquement pour le Digest préexistant**.
  **M3-C HMAC-SHA256** reste obligatoire pour les commandes
  de modes `/api/v1/display/mode`.
- `test_real_digest_and_metrics.cpp` : envoie des preuves
  MD5 produites indépendamment par OpenSSL, teste GET/POST,
  replay, contrôle du peer, Origin, Host, qop, challenge,
  cookies GET-only, expiration et échantillon invalide
  sur les sources C++ `FslessMetrics` inchangées.
  Les credentials du test sont publics et inventés.
- Deux builds Xtensa Core 3.1.2 comparables sont **inertes** :
  A = M3-M + M3-L, B = A plus Digest BearSSL conservé au linker.
  Taille/empreintes BIN, ELF text/data/bss et `-fstack-usage`
  calculés des fichiers CI effectifs. Aucun budget produit
  inféré, aucun seuil abaissé.

## Première preuve CI source et Xtensa (binaire INERTE)

[Workflow ciblé M3-N #39254265939](https://github.com/shinobione/SHINO-TV/actions/runs/39254265939)
au commit pré-documentaire
`fb3d6e466fb4e2b2eef90e8eefeb977fa1ff4bc2` :
**2/2 jobs SUCCESS**. Le test HOST a réellement exécuté
OpenSSL MD5 Digest contre le code C++ original
`FslessMetrics.cpp`, avec les fonctions de politique
`HomeLan`. Il n'a pas utilisé le vrai mot de passe
propriétaire ni le réseau SmallTV.

| Grandeur calculée depuis ELF/BIN inertes | A : M3-M + M3-L | B : A + noyau Digest/BearSSL M3-N | B − A |
|---|---:|---:|---:|
| BIN | 274 400 o | 293 280 o | **+18 880 o** |
| ELF `.text` | 268 751 o | 287 623 o | **+18 872 o** |
| ELF `.bss` | 28 256 o | 28 480 o | **+224 o** |
| ELF `.data` | 1 552 o | 1 556 o | **+4 o** |

**Coût élevé.** Il ne faut pas cumuler ce chiffre
directement avec les deltas d'autres bancs : leurs
graphes et options ne sont pas tous identiques.
Il ne s'agit pas non plus d'une mesure du firmware
physiquement installé, de sa marge libre, d'un dump
ou d'un BIN à flasher. Le rapport JSON CI contient
les SHA-256 calculés sur les **deux inertes**.

Une nouvelle CI **sur le HEAD final documentaire**
est nécessaire avant de déclarer l'ensemble M3-N
qualifié au dernier commit. Même avec CI PASS,
la parité de comportement de vrais clients Digest,
leur politique de compteur `nc` et les cookies
émis par le serveur natif unique restent HOLD.

**Décision technique :** ne pas intégrer ce noyau tel
quel à B5.3 pour l'instant ; rechercher la
réutilisation du chemin Digest existant dans la
migration du propriétaire HTTP, et mesurer le
graphe firmware complet au lieu d'accumuler
des objets d'authentification expérimentaux.

## Correction architecturale : le Core 3.1.2 permet un handoff ciblé

Une seconde inspection **du véritable code source ESP8266
Arduino Core 3.1.2 épinglé** montre un chemin important
que nos audits M3-B/M3-M avaient traité trop pessimiste :

1. `Parsing-impl.h::_parseRequest()` lit la ligne
   HTTP puis **invoque `_hook(methodStr,url,&client,...)`
   AVANT la boucle de lecture des en-têtes et du POST body** ;
2. Le hook peut retourner
   `ESP8266WebServer::CLIENT_IS_GIVEN`, et
   `ESP8266WebServer-impl.h::handleClient()` ne
   ferme alors pas volontairement ce client, avant de
   libérer sa propre référence ;
3. La bibliothèque expose `addHook` et un
   `WiFiClient*` permettant **en principe** à un
   composant dédié de prendre une copie conservée
   de la connexion et de lire lui-même les en-têtes
   et le corps HMAC, pendant que **toutes les autres
   routes conservent l'ancien serveur et son Digest**.

**Ce n'est PAS encore une preuve de handoff opérationnel.**
La copie/référence `WiFiClient`, les interruptions,
l'ordre des deux hooks (HomeLan refuserait M3 LAN
avant reprise s'il s'exécutait en premier), les
réponses TCP partielles et la non-réentrance restent
à tester en natif et en HOST. Le parseur Core alloue
en outre **une ligne HTTP dans un `String` non
plafonné avant le hook** : risque mémoire réel,
inacceptable sans garde supplémentaire ou preuve
de borne amont. Le fait que les en-têtes et le corps
ne soient pas encore lus ne suffit pas à garantir
l'absence de DoS mémoire sur ligne longue.

**Décision pour M3-O :** tester d'abord **ce handoff
ciblé sur le serveur d'origine** plutôt que
poursuivre le remplacement complet de Digest et
des routes B5.3. Ce mécanisme préserverait
potentiellement le vrai serveur et réduirait le
coût énorme (+18 880 octets BIN inerte) du
noyau M3-N. Si une de ces hypothèses échoue,
le mécanisme reste HOLD. Ne rien installer.

La CI M3-N vérifie maintenant l'ordre des appels
directement dans les fichiers de bibliothèque
installés par **le Core 3.1.2 épinglé**, affiche
leur empreinte calculée et **n'assimile pas**
l'inspection statique à un test de handoff TCP.

## Limites obligatoires : pas de changement de statut physique

Ce composant **ne prend pas possession de la vraie connexion TCP**,
n'implémente ni transport, ni émission de réponse HTTP robuste, ni
nonce RNG matériel de production, ni totalité des handlers.
L'identité de pair, la topologie AP/STA et l'authentification
avant lecture du corps doivent encore être reliées au même
propriétaire de socket et testées en condition native.

Le code historique pouvait accepter certaines variantes de
Digest (RFC2069 sans qop, `nc` non suivi, AP Basic)
que le noyau M3-N **refuse délibérément**. Il faut vérifier
la compatibilité du LINK Windows **réel** et du navigateur
avant de prétendre préserver toutes les interactions B5.3.
En l'état, **PARITÉ COMPLÈTE NON DÉMONTRÉE**.

Le préflight physique B5.3 communiqué reste **STOP/HOLD**,
marge CONT minimale seulement **80 octets** au seuil.
Les budgets mémoire, WDT, OTA/LittleFS, média et rendu sont
**NON VÉRIFIÉS** sur appareil. Ni la Freebox, ni Codex B5.4,
ni le LINK Windows installé ne sont modifiés. Aucun flash,
aucune OTA, écriture Wi-Fi/RTC, reboot, merge ou permission
persistante ne résulte de cette étude.

**Prochain jalon après preuve CI :** un vrai adaptateur
unique `WiFiServer/WiFiClient` capable d'appliquer ce
contrôle aux véritables octets avant le corps, et de
conserver toutes les anciennes routes et réponses ; vérifier
délais, write court, Digest nonce et collisions multi-client,
heap et CONT du **graphe produit complet** avant tout GO matériel.
