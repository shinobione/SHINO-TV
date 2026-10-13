# B5 — Partial OTA transport guard, 13 octobre 2026

Outil distinct : `companion/shino_b5_partial_preflight.py`. Le transport normal
`companion/shino_update.py`, les fichiers du diagnostic GET, le firmware et les
paquets propriétaires préexistants restent inchangés. L'outil réutilise
`inspect()` (SHA, CRC, segments, descriptor), `load_identity()` et `signature()`
du client existant ; son lecteur réutilise la séquence Digest bornée et le
coordinateur Windows du diagnostic B5. Cette dépendance locale doit accompagner
l'outil lors de la revue. Aucun système OTA ou endpoint firmware supplémentaire.

## Contrat local et séparation des opérations

- Mode par défaut : inspection locale uniquement, sans lecture de secrets,
  transport, socket ou marqueur. Tous les chemins BIN/manifeste/rapport sont
  fournis explicitement. Aucune identité, SHA, build ou chemin propriétaire
  n'est incorporé dans le code. L'hôte autorisé est exclusivement l'AP
  `192.168.4.1`, constante importée du transport normal ; toute autre valeur
  est refusée dans les trois modes, avant ouverture réseau. La taille 414176 et le plafond
  8192 sont fixes ; identité et HMAC restent dérivés des entrées vérifiées.
- Deux BIN sont inspectés : candidat B5.1 et image B5 retenue. Rapports bornés,
  provenance source, identités, layout 4m2m et garde de staging sont confrontés.
  Un BIN inerte synthétique est réservé aux tests, jamais une image à installer.
- Une future opération partielle exige le périmètre propriétaire exact,
  confirmation du SHA candidat, chemins explicitement fournis et un nouveau
  marqueur. Une lecture Digest préalable vérifie B5 exécuté, boot, nonce,
  LittleFS, télémétrie fraîche, état NONE et floors 25600/16384/2048/25.
- Avant tout POST, une réservation exclusive dans le répertoire partagé du
  coordinateur Windows, sous `b5-partial-attempts/<device>-<SHA>.attempt`, puis
  le marqueur demandé sont écrits et fsyncés. La clé vient des artefacts vérifiés,
  indépendamment des chemins BIN/marqueur, du boot et de l'image B5 exécutée.
  Une réservation existante, même vide ou corrompue, bloque avant tout GET ;
  un répertoire ambigu/inaccessible/redirigé impose HOLD. La création exclusive
  départage deux instances concurrentes avant tout POST. Les records conservent les
  identités et le boot préalable, sans nonce, preuve HMAC ou credential. Il
  n'est jamais supprimé, réutilisé ou remplacé après une erreur incertaine.
- Un socket, un POST, Content-Length de l'image complète. Seul le préfixe de
  8192 octets peut atteindre `socket.send()`. Les écritures courtes continuent
  uniquement leur portion non transmise, sur le même socket. Une exception
  après écriture partielle est UNKNOWN : aucun renvoi du morceau incertain.
- Plafond atteint : arrêt d'émission puis fermeture immédiate, sans attente
  d'une réponse POST, flush, complément, reprise, polling ou appel à install().
  Les compteurs distinguent octets confirmés côté socket et borne supérieure
  en cas de résultat inconnu. Ils ne prouvent pas une réception par B5.
- Verrou HTTP partagé, refus immédiat de concurrence pour le POST et budget
  total de 6 s avec watchdog incluant l'attente, en-têtes, corps et fermeture.
  Une instance utilisée ou une réservation existante interdit un second POST,
  même avec un nouveau chemin de marqueur. Un échec de fsync ou du marqueur
  conserve la réservation et bloque une nouvelle tentative.
- La collecte ultérieure est un mode séparé, qui nécessite sa propre
  autorisation de lecture et le contexte de ce marqueur. Une seule opération
  GET statut, un challenge valide + un GET authentifié maximum ; second401,
  timeout, corps invalide ou réponse absente imposent STOP sans nouvelle lecture.
  Aucun GET après le POST n'est déclenché automatiquement.

## Preuve conservée, jamais succès OTA

Le lecteur spécialisé accepte le statut exact après FAILED_NO_COMMIT, sans
affaiblir le diagnostic B5 normal. Il conserve last_update, les quatre minima
OTA, identité exécutée/boot, heap/bloc/stack/fragmentation courants et LittleFS.
Nonce, en-têtes Authorization, HMAC, mots de passe et champs serveur inconnus
sont exclus des résultats et reçus. Les erreurs sont des codes fixes.

Un reset, une autre identité, une anomalie LittleFS, STAGED/RECEIVING/REFUSED,
un minimum absent/unsafe ou une réponse incertaine restent HOLD/UNKNOWN. Les
mesures structurellement valides restent dans le reçu même si elles échouent
aux floors. Un relevé attendu donne PARTIAL_OBSERVATIONS_RECORDED_HOLD :
ota_success=false, physical_acceptance=false, native_high_water_qualified=false.
Les nombres d'octets réellement reçus et de secteurs réellement écrits restent
inconnus : l'API existante ne les expose pas après un abandon.

## Risques et limites du récepteur B5 exact

SOURCE : paquet B5 conservé, source 8de4d455, `src/boot/M9NormalStageA.cpp`
upload() lignes222–260 et identity() lignes317–333 ; `include/ShinoHttpOta.h`
begin()/finish()/abort() lignes57–93 ; Core conservé `.pio/ota-core-abort/Updater.cpp`
begin() ligne68, _writeBuffer() ligne375, write() ligne436, _reset() ligne47.
Les tailles et adresses suivantes proviennent de ce 4m2m et des artefacts
existants, pas d'une nouvelle qualification physique.

- Pour 414176 octets annoncés, staging `0x19A000..0x200000` ; le premier secteur
  susceptible d'être effacé/écrit est `0x19A000..0x19B000` (secteur410).
  À exactement8192 octets acceptés, Core conserve le deuxième bloc en RAM :
  un secteur écrit dans le modèle. En cas de coupure/RST/erreur, même ce nombre
  n'est pas une observation matérielle. Un essai partiel écrit bien de la flash.
- Le préfixe ne peut pas satisfaire la réception complète. La branche normale
  d'abandon ne passe pas par end(false), n'arme pas un nouveau boot et ne demande
  pas de reboot. Elle libère le buffer ; elle ne restaure pas le secteur écrit.
- Updater.begin() force le sommeil Wi-Fi à NONE_SLEEP_T ; l'abandon ne restaure
  pas le réglage précédent. Aucun credential ou réseau n'est reconfiguré par
  cet outil, mais cette conséquence radio du Core doit être comprise avant essai.
- Heap/bloc/fragmentation sont échantillonnés : des pics transitoires peuvent
  être manqués. La continuation est un watermark historique, sans repaint.
  Les données OTA sont volatiles et disparaissent au reboot ou au prochain POST.
- Une ancienne commande RTC n'est ni inspectée ni effacée par l'abandon.
  Coupures, exceptions, SDK/ROM/IRQ et comportement réel du boot ne sont pas
  qualifiés. Il n'existe aucun rollback automatique garanti par eboot.
- Aucun transfert complet, vérification finale SHA/CRC/staging, commit,
  démarrage B5.1, STA/DHCP Freebox ou récupération physique n'est qualifié ici.

## STOP et livraison

Après un résultat inconnu : fermer, conserver marqueur/reçu, STOP. Ne pas
envoyer le reste, recréer le marqueur, changer d'image, relancer le POST,
rebooter ou improviser une récupération. Une lecture ultérieure doit être
autorisée séparément ; elle n'autorise jamais une répétition de transfert.
L'accès AP doit être disponible et les autres écrivains doivent rester exclus
pendant la future séance, jusqu'au recueil des preuves. Aucun accord physique
n'est déduit des modes CLI ni des tests HOST.

La réservation durable protège ce profil Windows et son registre conservé.
Un autre PC/profil, une suppression ou une perte du registre ne sont pas couverts
par un verrou côté appareil. Aucun historique externe n'est automatiquement
migré : un ancien essai connu hors registre exige HOLD et revue propriétaire.
Ne jamais déplacer, supprimer ou réinitialiser ce registre pour réarmer un essai.

Les tests ciblés utilisent des BIN non exécutables et un serveur HTTP fictif
en mémoire. socket.socket, socket.create_connection et socket.getaddrinfo sont
interdits par des gardes qui vérifient zéro appel. Aucun port local ou appareil
n'est ouvert.

**READY_FOR_OWNER_REVIEW — HOST uniquement ; PHYSICAL/NATIVE HOLD/NOT_RUN.**
Validation initiale avant la dernière correction :33 nouveaux tests PASS
(60,524 s), couvrant écritures courtes/incertaines, concurrence OS et threads,
watchdog, fermeture, HMAC de la taille complète, Digest refusé, documents
invalides, marqueurs/reçus préservés, reset, minima unsafe et secrets dans des
champs pourtant bien typés.11 régressions existantes PASS (7 coordination,
4 inspection updater) ;44 cas uniques validés au total, sans relancer de
campagne Core/firmware. Un premier lancement des régressions a rencontré le
répertoire temporaire non inscriptible du sandbox Windows ; la relance a utilisé
research-local comme racine temporaire, sans modifier ces tests existants.

Le CLI par défaut a aussi inspecté les BIN B5/B5.1 réels conservés :414176,
plafond8192, staging0x19A000/secteur410 ; sockets/DNS et load_identity interdits,
zéro appel vérifié. Les1185/1186 fichiers privés ont exactement les mêmes
inventaires SHA-256 avant/après. Aucun secret réel n'a été lu, aucun firmware
n'a été reconstruit ou modifié, aucun contact appareil/commit/push effectué.
Les modifications locales antérieures restent conservées.

Dernière correction ciblée du 13 octobre : AP strict et réservation par appareil/
candidat. **8 nouveaux tests PASS (16,020 s) +18 régressions ciblées PASS
(29,350 s), soit26 cas uniques exécutés sur ce correctif.** Couverture nouvelle :
refus d'hôte dans les trois modes et à l'ouverture, chemin/paquet déplacé,
nouveau boot, écriture incertaine, réservation incomplète, erreurs de fsync et
deux instances concurrentes. Les tests de scénarios d'erreur utilisent des
registres synthétiques indépendants pour respecter la nouvelle règle sans retry.
Plafond8192, Content-Length414176/HMAC, POST unique, erreurs/watchdog/fermeture,
Digest borné, collecte indépendante et absence de secrets vérifiés par la
sélection de régressions ; aucune campagne massive relancée. Tous ces tests
interdisent sockets/DNS et les appels au transport OTA normal. Aucun transfert
physique ni qualification matérielle ; physique/native HOLD/NOT_RUN.
