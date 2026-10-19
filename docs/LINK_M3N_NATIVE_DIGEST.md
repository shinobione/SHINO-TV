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
