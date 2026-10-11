# B5.1 — Home LAN Recovery & Permanent Fix, 12 octobre 2026

**READY FOR OWNER REVIEW — qualification physique HOLD / NOT_RUN.**
Branche `feature/shino-tv-b3-telemetry-scratch-experiment`, PR #47 Draft.
Aucune nouvelle opération SmallTV, réseau domestique, SDK, RTC, flash,
provisionnement, reboot ou merge n'est exécutée par cette mission.

## État conservé et préparation

Le dépôt était propre sur la branche demandée. Le pull fast-forward a avancé
`67a94c1` vers `6697b5b007b9e1358882cbb461a27e402f0552d8`, identique à GitHub ;
les CI concernées étaient SUCCESS. Le correctif STA candidat est donc inclus
dans l'enquête, sans être considéré comme une preuve de la cause physique.

Le propriétaire confirme B5 installé via B4→B5, boot/quatre cartes/LINK/
identité/LittleFS/AP PASS, GET LAN status/intent HTTP200, POST HTTP409
`PROVISION_HOLD`, puis `NO_SAVED_WIFI` après coupure. Ce sont des observations
propriétaire. La lecture locale autorisée du paquet
`research-local/m9-owner/b5-home-lan-safe-20261011-212256/B5/` vérifie le BIN
contre `release.json` et `report.json`, source
`8de4d4556f26d47b62b1f19a6b03216a12f7e718`, **412848 octets**.
La valeur 412488 dans le message était différente des octets et du manifeste.
Le reçu OTA conserve `POSTBOOT_ACCEPTANCE_UNCONFIRMED` ; sa confirmation
physique ultérieure est fournie séparément par le propriétaire. Aucun reçu,
ancien paquet, backup ou `.attempt` n'est modifié.

## Diagnostic démontré

Le Core3.1.2 utilise par défaut `NONOSDK22x_190703`.
`tools/shino_b51_sdk_audit.py` épingle le SHA de son `libmain.a` et examine le
désassemblage réel. Le getter `wifi_station_get_config_default` délègue au
bloc `0x2284..0x2351` : copies SSID32, clé64, drapeau/adresse BSSID ; **aucune
copie du threshold RSSI/authmode**. Il alloue temporairement `0x49c=1180` B.
Il ne teste pas l'opmode STA. Le setter vérifie STA et possède son chemin
persistant ; `WiFi.persistent(false)` ne désactive pas un appel SDK direct.

Dans le B5 installé, `B5Lan::Sdk::read` initialise `station_config` à zéro,
puis interprète `saved.threshold.authmode`. Ce champ reste zéro avec ce SDK.
`HomeLan::Store::change` peut donc écrire les bons octets, les relire exactement,
puis refuser la confirmation à cause de `sdk.wpa2()==false`. `B5Lan::begin`
rejette ensuite les mêmes identifiants et expose `NO_SAVED_WIFI`, sans tentative
STA. **Ce statut historique ne prouve pas que les secteurs SDK étaient vides.**

La source exacte `8de4d455` est exécutée avec le getter SDK fidèlement simulé :
une écriture réussie, résultat refusé, puis identifiants ignorés au démarrage.
Le correctif candidat d'ordre STA ne traite pas ce défaut : l'ancien setter
activait déjà STA avant l'écriture ; le getter par défaut n'exige pas STA.
B5.1 conserve l'activation explicite avant les opérations de provisionnement.

Cette reproduction explique de manière défendable l'ensemble des symptômes,
mais l'ancien `PROVISION_HOLD` regroupait plusieurs étapes. Sans capture de
ces étapes ni nouvelle lecture physique, on ne peut attribuer **chaque** ancien
POST à ce défaut ou affirmer lesquels ont réellement écrit. Une mauvaise clé
Freebox n'est pas déduite de ce HTTP409.

## Correctif et comportement

- `ota/lan/B5Lan.cpp` vérifie les octets SSID/clé issus du getter persistant.
  Avant chaque connexion, il réapplique explicitement WPA2, RSSI-127 et le scan
  sans BSSID imposé dans `wifi_station_set_config_current`. L'état de DHCP est
  contrôlé ; une association échouée ne supprime jamais les identifiants.
- Une configuration identique n'est pas réécrite. Une écriture n'est annoncée
  réussie qu'après égalité de la relecture persistante. Les retours SDK faux,
  relectures impossibles ou différentes deviennent **UNKNOWN**, jamais EMPTY.
- L'AP protégée démarre indépendamment de STA. Les retries de connexion sont
  ceux du contrôleur existant : timeout20 s, reprise60 s, retrait AP après15 s
  de stabilité sans utilisateur AP/intent ; AP rétablie à la perte du LAN.
  Le serveur HTTP persistant demeure celui du firmware normal.
- Erreurs fixes sans SSID/clé/token : STA_ENABLE_FAILED, SDK_READ_FAILED,
  SDK_WRITE_FAILED_UNKNOWN, READBACK_FAILED_UNKNOWN, READBACK_MISMATCH_UNKNOWN,
  MEMORY_HOLD, LAYOUT_UNSAFE, AP_STATE, INTENT_INVALID, PAYLOAD_INVALID et erreurs
  BODY_INCOMPLETE/BODY_EXTRA, préfixées `PROVISION_` selon l'API.
- Le parser exact collecte l'intent sur le nouveau socket ; le dispatch
  s'exécute après son unwind. Aucun corps Core `String`, borne99 B et délai
  total en-têtes+corps2 s. Corps interrompu/excédentaire : zéro écriture SDK,
  buffer et intent effacés. Requêtes imbriquées refusées avant mutation.
- Host/Origin numériques, interface locale et sous-réseau sont contrôlés.
  Digest reste nécessaire aux API normales ; intent/provisionnement restent
  réservés à l'AP. L'OTA LAN conserve le protocole HMAC et ses contrôles existants.

Le client `tools/shino_b5_provision.py` exige SHA/build exécutés exacts et un
statut B5.1 explicite. Il refuse l'ancien statut B5 ambigu et UNKNOWN. Si les
identifiants sont déjà relus, il ne demande aucun mot de passe et ne POSTe pas.
Sinon : une saisie masquée, verrou Digest commun Windows, un intent et un POST.
Un `.attempt` exclusif est fsyncé avant le POST, conservé en cas d'échec/réponse
perdue. Une401 du POST n'entraîne **jamais** une deuxième émission, même via
le handler urllib. Diagnostics limités à une liste fixe de codes connus.
Les SSID ASCII imprimables de1..32 octets et clés WPA2 de8..63 caractères ou
64 hex sont le contrat conservé ; aucune saisie réelle pendant les tests.

## Validation et ressources

Toutes les identités Wi-Fi des tests sont fictives. Les interfaces radio,
DHCP, SDK, flash et RTC des laboratoires sont simulées en RAM ; leurs seuls
sockets sont sur `127.0.0.1`. Le code des handlers, parser/Digest, dashboard,
métriques et Core Updater est réel. Ce périmètre ne mesure aucun matériel.

| Validation | Résultat hors ligne |
| --- | --- |
| SDK réellement utilisé | Getter incomplet démontré par désassemblage épinglé |
| Source B5 installée vs B5.1 | Ancienne régression reproduite ; 32 cas / 122 contrôles B5.1 |
| HTTP réel et injections | 24 scénarios : corps fractionné/incomplet/interrompu/excédentaire, jetons, SDK, réponse perdue, concurrence Digest, LAN/Origin/sous-réseau |
| Clients Windows | 16 tests : identité, statuts inconnus, masque des erreurs, zéro retry POST401, marqueur durable |
| Composition et paquet | 9 compositions + 6 tests de paquet avec vrais BIN synthétiques/CRC/identités ; anciens fichiers conservés |
| OTA Core existante | 227 cas / 197 interruptions, sans rollback simulé inventé |
| OTA LAN exacte | BIN publics B5→B5.1 dans parser/HMAC/Core/RTC RAM ; mauvais HMAC sans écriture, staging/FS/SDK préservés |
| Dashboard / LINK | Quatre cartes et métriques fraîches dans le graphe natif ; TTL6 s et sources LINK inchangées |
| Physique / Freebox | NOT_RUN / HOLD |

Core ESP82663.1.2, PlatformIO6.1.18 / espressif82664.2.1, GCC10.3.0,
ArduinoJson7.4.3 et dépendances du dépôt conservés. Comparaison locale :

| Graphe | BIN | RAM statique, noinit inclus |
| --- | ---: | ---: |
| B5 installé, paquet privé retenu | 412848 B | 44132 B |
| B5 public, source installée8de4d455 | 412784 B | 44084 B |
| B5.1 public | 414112 B | 44904 B |
| Delta public à paramètres identiques | +1328 B | +820 B |
| B5.1 propriétaire local préparé | 414176 B | 44968 B |
| Delta privé contre le B5 réellement installé | +1328 B | +836 B |

Le SDK scratch112 B est statique et effacé après chaque opération. Frames
GCC et prologues Xtensa concordent : handler144, provision256, lecture SDK48,
écriture SDK16, connexion144, chargement128, status96, intent128 B. Chemin
application de provisionnement mesuré **576 B**, auquel s'ajoutent les
fonctions internes SDK/ROM/allocateur/interruptions. Chemin OTA compilé connu
maximum **1616 B**, sous la réserve inchangée2048 ; aucune borne native globale
n'est revendiquée. Les observer/watermarks ne sont pas repeints.

Avant SDK : heap>=21696, bloc>=17600, stack>=2048 B, fragmentation<=25 %,
incluant1216 B de réserve pour l'allocation connue du SDK. Recontrôle après
activation STA et avant écriture/relecture. La mémoire transitoire complète
radio/DHCP/persistance/ROM reste **HOLD_NATIVE_MEASUREMENT**. L'OTA conserve
admission heap>=25600, puis floors20480/16384/2048 B et frag<=25 %.

Linker réel : FS `0x200000..0x3FA000`, EEPROM `0x3FB000`, RF `0x3FC000`,
SDK `0x3FD000..0x400000`. No-init56 B inchangé. BIN<=`0xFEFF0`, staging U_FLASH
avant FS, garde>=4096 B au-dessus de l'application courante. Aucune route
U_FS, raw SDK writer, autoformat ou commande RTC supplémentaire ajoutée.
Les tests de RAM ne prouvent pas la tenue des secteurs lors d'une coupure
physique au milieu d'une écriture SDK ni une connexion WPA2 réellement négociée.

La CI B5 exige ces tests, désassemblage, builds publics avant/après et OTA
exacte ; les workflows OTA/Core/StageA concernés restent exécutés. La CI du
HEAD final, son SHA et ses liens sont consignés dans la PR47 et le reçu local
`research-local/b51-final-delivery.json` après achèvement, sans assimiler des
jobs ignorés à des tests réussis.

## Paquet propriétaire local

`tools/shino_b51_owner_packet.py` vérifie BIN/manifeste/rapport B5, SHA/build/
source indépendamment fournis, CRC, descriptor, identité propriétaire,
layout4m2m, branche propre et source B4 du receiver inchangée. Il crée un
nouveau dossier direct sous `research-local/m9-owner/`, construit B5.1 avec
l'identité déjà conservée et vérifie une image distincte, les ressources et
la garde OTA. Aucun ancien paquet n'est réutilisé comme sortie. Rien de privé
n'est envoyé à GitHub ; préparer un paquet ne donne aucune autorisation physique.

```powershell
$prior = 'research-local/m9-owner/b5-home-lan-safe-20261011-212256/B5'
$installed = Get-Content "$prior/release.json" -Raw | ConvertFrom-Json
python tools/shino_b51_owner_packet.py `
  --output research-local/m9-owner/b51-home-lan-owner-20261012 `
  --installed-bin "$prior/.pio/build/esp12e_m9_4m2m_normal_qualification/firmware.bin" `
  --installed-manifest "$prior/release.json" --installed-report "$prior/report.json" `
  --expected-current-sha256 $installed.sha256 --expected-current-build-id $installed.build_id `
  --expected-current-source 8de4d4556f26d47b62b1f19a6b03216a12f7e718
```

Le dossier doit être nouveau. Ne jamais effacer un `.attempt` ou un reçu pour
relancer une opération. Le contrôle local est une preuve de fichiers ; la
vérification de l'identité **exécutée** appartient au futur protocole autorisé.

**Paquet effectivement préparé, hors ligne uniquement :**
`research-local/m9-owner/b51-home-lan-owner-20261012/`, firmware dans `B5.1/`,
source propre `50b732e084079b58e21e33f22ac2f5f4611047c1`. Son manifeste local
et `B51-OFFLINE-REVIEW.json` donnent le SHA/build exacts calculés sur le BIN.
Garde OTA contre le B5 retenu : **1265664 B**, staging `0x19A000..0x200000`.
`EXACT-IMAGE-QUALIFICATION.json` conserve139 cas /124 frontières d'interruption
Core/eboot sur ce BIN ; `LAN-CORE-LOOPBACK-QUALIFICATION.json` conserve les24 scénarios
et l'OTA des octets exacts B5→B5.1 en RAM. Tous les identifiants d'authentification
et Wi-Fi employés par les simulateurs sont fictifs. Ces reçus restent locaux.
Le dernier commit documentaire/métadonnées ne reconstruit pas cette image ;
ses trois entrées firmware LAN restent identiques au commit de compilation.
**CANDIDATE_NOT_INSTALLED / HOLD_NATIVE_MEMORY** : ne pas relancer la commande
de préparation sur ce dossier existant et ne pas utiliser le BIN public inerte
comme image d'installation. L'unique prochaine intervention est la séance
physique exacte décrite ci-dessous, après accord portant sur ce paquet.

## Unique prochaine séance propriétaire, après autorisations exactes

1. Examiner le paquet B5.1 et autoriser explicitement **une** OTA du BIN/hash
   exact depuis le B5 confirmé, puis la qualification réseau proposée. Cette
   séance inclut des lectures, un éventuel premier POST Wi-Fi, une coupure
   électrique et une interruption du routeur : chaque opération doit être
   comprise dans l'accord. Aucun droit physique n'est déduit de ce document.
2. Sur AP protégée, vérifier SHA/build/taille B5 exécutés contre le manifeste,
   FS exact, aucune tentative antérieure/pending update, LINK/fraîcheur et
   floors. Pause LINK seulement pour le transfert comme dans le protocole OTA
   existant ; préserver configuration et autostart. Un plancher manquant/refusé
   ou récupération inaccessible impose STOP.
3. Un seul `companion/shino_update.py --install` avec BIN/manifeste privés,
   `--confirm-sha256`, `--expected-current-sha256`, nouveaux `--attempt-marker`
   et `--receipt`. Conserver ces fichiers, y compris UNKNOWN ; aucun renvoi.
   Vérifier nouveau SHA/build/boot, LittleFS et quatre cartes avant de continuer.
4. GET B5.1 LAN status : **VERIFIED signifie réutiliser les identifiants déjà
   persistés**, pas les ressaisir. EMPTY seul permet le premier POST autorisé,
   via client interactif avec SHA/build B5.1 exacts, nouveaux marqueur/reçu et
   `--change`. Clé demandée localement une fois, masquée, jamais dans chat/CLI/log.
   UNKNOWN/INVALID/erreur ou réponse perdue : STOP, conserver le marqueur.
5. Vérifier association2,4 GHz/WPA2 et adresse DHCP dans le statut et le routeur.
   Mettre Windows sur Ethernet du même LAN, cible numérique DHCP dans LINK
   sans modifier les credentials Digest ; vérifier CPU/GPU/RAM/GPU TEMP et
   `metrics_fresh`, TTL6 s, FS et ressources. En exploitation normale, Windows
   n'a plus besoin de rejoindre l'AP SHINO.
6. Seulement dans la séance autorisée : une coupure/redémarrage puis retour
   STA/DHCP/LINK avec les mêmes identifiants ; une indisponibilité temporaire
   Freebox, AP de récupération protégée joignable avec son serveur, puis retour
   du routeur et reconnexion automatique. Aucune réécriture des identifiants.
7. Sur Ethernet/LAN, GET authentifié des statuts OTA et LAN, ressources et
   identité exacte ; prouver l'accès OTA LAN sans lancer une autre OTA.
   L'OTA suivante est une opération distincte à autoriser séparément.

La séance reste HOLD jusqu'à accord. En cas de reset, corruption, seuil unsafe,
identité non confirmée ou perte de récupération : STOP sans retry, autre image
ou procédure UART improvisée. L'eboot ESP8266 ne fournit pas de rollback
automatique. Le succès physique est exclusivement l'observation de STA/DHCP,
Ethernet/LINK/quatre cartes, reconnexion et récupération AP/OTA LAN réelles.
