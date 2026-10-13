# B3 — coordination HTTP Windows, 11 octobre 2026

**READY FOR OWNER REVIEW (logiciel hors ligne). Qualification physique HOLD.**
Branche existante `feature/shino-tv-b3-telemetry-scratch-experiment`, Draft
PR [#47](https://github.com/shinobione/SHINO-TV/pull/47), départ local/GitHub
`26e1ace98dcd4713c4a227c3847bc4b5cf74dee5`. Aucun firmware modifié ou compilé
localement ; aucune opération SmallTV, serial, flash, OTA, reboot ou Wi-Fi.

Le propriétaire confirme B3 installé : boot/quatre cartes PASS, LINK dynamique,
capture203 s stack min2288/heap27696/bloc27120 B, fragmentation max10 %. La
qualification30 cycles a tenu jusqu'au HOLD cycle22 `LINK_METRICS_NOT_FRESH` ;
LINK seul a ensuite accepté122/122 tentatives. Ces faits restent des observations
propriétaire. Aucun ancien reçu, backup, image privée ou marqueur n'est corrigé.

## Audit du cycle de vie

- `digest_exchange` crée/conserve un fichier par IPv4 RFC1918 dans
  `%LOCALAPPDATA%\SHINO-TV`, puis verrouille son premier octet avec
  `msvcrt.LK_NBLCK`. Le fichier n'est jamais supprimé. Le verrou OS est libéré
  explicitement dans `finally`, puis le handle est fermé ; la mort du processus
  libère aussi le verrou OS. Aucun FIFO Windows n'est promis.
- L'attente de contention reste **1,5 s**, polling au plus25 ms. Préparation
  locale du fichier et attente sont mesurées ensemble dans `lock_wait_ms`.
  L'échec local interdit tout envoi hors verrou. Le deadline d'acquisition
  commence après la préparation locale ; ce n'est pas un timeout HTTP.
- LINK prend le verrou après collecte/validation du sample, appelle le même
  sender/Digest opener, puis conserve le verrou jusqu'à la lecture/validation
  bornée du corps et sa fermeture. Timeout POST inchangé **3 s**.
- Le lecteur conserve le verrou pendant le GET, le challenge Digest éventuel,
  le corps4096 octets maximum, le décodage JSON et la fermeture. Les erreurs
  HTTP sont fermées avant la libération. Timeout GET inchangé **5 s**.
  Ces valeurs urllib sont des timeouts d'I/O, **pas** des bornes totales de
  l'échange logique : challenge/auth et lectures lentes peuvent allonger la
  détention. Le rejeu d'authentification401 existant reste celui d'urllib ; aucun
  retry supplémentaire du GET après résultat ambigu n'est ajouté.
- LINK attend **2 s après la fin** d'un succès. Après échec :2/4/8/16/30/30… s,
  toujours après la fin de la tentative. Les conditions de reconstruction de
  l'opener et son cache Digest restent inchangées. `query_nvidia` a déjà un
  timeout1,5 s ; cela ne borne pas à lui seul toute la collecte/ordonnanceur.
- Le qualificateur historique fait trois GET puis attend2 s entre cycles.
  La capture mémoire historique fait deux GET d'identité encadrant le GET normal,
  puis attend20 s. Tous deux restent gelés octet pour octet.
- `FslessMetrics::apply()` date l'application du sample côté firmware.
  `stale()` vaut vrai sans sample reçu ou si l'âge uint32 dépasse **6000 ms**
  (strictement `>`, pas `>=`). Le qualificateur refuse toujours
  `metrics_fresh` différent de `true`, sans GET de secours.

## Correctif et instrumentation

`shino_coordinated_qualify.py --b3-paced` conserve les mêmes endpoints et
contrôles, mais laisse **2,25 s hors verrou entre deux GET**. Les2 s historiques
entre cycles comptent dans cette fenêtre ; aucun délai n'est passé sous verrou.
La marge250 ms et la fenêtre supérieure à la cadence LINK évitent la
réacquisition immédiate du qualificateur. Un GET complet sous verrou **>1000 ms**
donne désormais un HOLD `B3_HTTP_DURATION_OUT_OF_BOUNDS` dans ce mode seulement,
après libération, sans retry ni augmentation du timeout. Sans nouveau drapeau,
le burst B2 et ses2 s intercycles restent identiques.

L'enveloppe testée suppose deux clients coopérants, même utilisateur/répertoire
de verrou, GET et POST sous verrou <=1 s, collecte LINK <=1,5 s, exécution du
processus prêt avec <=250 ms de retard. La borne conditionnelle d'intervalle
entre ACK LINK est2+1,5+1+1+0,25 = **5,75 s**. Ce sont des conditions de
qualification Windows, pas des mesures du SmallTV. Une machine suspendue,
un troisième client, un HTTP hors enveloppe ou un échec/backoff peuvent dépasser
6 s. Le mode vérifie sa borne GET ; les bornes POST/collecte nécessitent les
diagnostics LINK. Un PASS des contrôles de lecture ne prouve pas ces bornes ni
une cause physique. Aucun plancher mémoire/TTL/contrôle OTA n'est changé.

Opt-in `--http-diagnostics` du wrapper : au plus64 échanges, compteurs cumulés,
noms d'opération fixes, `lock_wait_ms`, `http_under_lock_ms`, `yield_ms`, code
HTTP terminal et fin monotonic. Les délais sous verrou incluent validation et
fermeture locale. Un401 de challenge normalement résolu reste dans la durée
globale ; `http_401` désigne le401 terminal. Timeout, indisponibilité réseau,
coordination occupée/indisponible et erreur JSON sont séparés. Les timings sont
conservés aussi dans le nouveau reçu d'échec ; aucune donnée HTTP brute.

LINK active les timings avec son `--diagnostics-file` existant. Au plus64
tentatives et64 échanges, compteurs acceptés, `collection_ms`, intervalle/âge
depuis le précédent ACK et nombre d'épisodes strictement >6000 ms. L'ACK client
est une **inférence de risque de fraîcheur**, pas l'horloge firmware ni une
lecture de `metrics_fresh`. Avant le premier ACK, l'âge est inconnu. Un épisode
est compté une seule fois, y compris à la récupération ; les snapshots sont
écrits après tentative, sans nouveau timer HTTP. Chaque lancement diagnostiqué
exige un **fichier neuf** et ne peut remplacer un ancien reçu/backup/marqueur.
Ne pas lancer un deuxième LINK en parallèle d'une instance propriétaire active.

Aucun identifiant, IP, chemin privé, mot de passe, Authorization, nonce, corps
ou texte d'exception n'est enregistré. Les secrets et handlers Digest restent
dans les mêmes objets privés ; les diagnostics ne capturent que des valeurs
typées et des classifications fixes.

## Validation hors ligne

Windows/Python3.12.10 : **121 tests,0 échec,0 erreur,0 skip**, dont19 nouveaux.
Fixtures HTTP en mémoire ; gardes socket/DNS/HTTPConnection/serial avec assertion
de zéro appel, également dans le processus concurrent. Aucun accès physique,
aucun serveur loopback lancé pendant cette validation Windows.

Le vrai test Windows utilise un second processus LINK avec son moteur réel,
six GET simulés de0,9 s et POST simulés de0,9 s : **6 POST acceptés/0 échec**,
aucun chevauchement des sections HTTP, intervalle ACK maximal **3172 ms**,
attente POST maximale **906 ms** sur cette exécution. Un autre processus tient
le verrou jusqu'à l'échec explicite au deadline1,5 s, puis sa libération permet
une acquisition immédiate. GET lent/timeout, fermeture d'erreur401 et absence
de retry sont vérifiés. Les durées sont des mesures du banc Windows.

Le modèle d'événements fait90 GET/30 cycles, six combinaisons de phases et
durées, y compris GET/POST1 s et collecte1,5 s : pas de famine des POST dans
l'enveloppe. Il donne systématiquement la réacquisition immédiate au GET ; les
POST ne passent que dans la fenêtre. Il ne simule pas les pertes RF/lwIP ou
l'ordonnanceur Windows arbitrairement retardé. Tests séparés : backoff/reprise,
frontière TTL stricte, métriques périmées HOLD immédiat, bornes GET HOLD,
ambiguïté sans retry, Digest des deux realms autorisés/cache et expurgation.

Suites conservées : LINK28, sender19, updater/qualifier29, verrou7, wrapper3,
capture9, observation B2 7. Les contrôles de gel signed/StageA vérifient les113
sources firmware et les identités historiques ; seuls quatre blobs Windows
exacts sont repinnés pour ce mandat, sans exemption globale. Ces deux gates et
les13 tests de scope CI passent localement. La CI Windows
exécute aussi les nouveaux tests. Vérifier les checks de la PR sur le **SHA final**
après push ; leurs résultats ne valent pas une qualification physique.

Les logs/compteurs locaux sont sous
`research-local/b3-windows-http-coordination-20261011/` (ignoré par Git).
L'inventaire de63123 fichiers protégés est réalisé par taille/mtime, sans lecture
de leurs contenus privés :63122 restent identiques. Seul le diagnostic LINK
préexistant `B3-LINK-DIAG.json` change de taille/mtime pendant la passe ; aucun
test/code exécuté ici n'utilise sa destination. Son contenu n'est pas lu et
aucune restauration ni interruption de LINK n'est réalisée. Tous les reçus
physiques, images, backups et marqueurs inventoriés gardent leurs métadonnées.
Ce contrôle ne prétend pas être une nouvelle vérification cryptographique des
contenus privés.

## Diagnostic et prochaine qualification

**Prouvé :** les clients se sérialisent ; une contention de1,5 s produit un
échec local et peut entraîner du backoff ; les I/O n'ont pas de borne totale
égale au timeout. La cadence explicite laisse passer LINK dans les fixtures et
le qualificateur conserve le HOLD sur `metrics_fresh=false`.
**Plausible :** contention, HTTP longs et/ou backoff ont pu allonger le délai
entre samples lors de la qualification mixte ; le LINK seul122/122 est cohérent
avec cette hypothèse. **Non démontré :** la cause physique du cycle22, le
partage entre ces mécanismes et RF/lwIP/collecte, et la disparition du HOLD
avec ce correctif. Il faut une nouvelle observation conjointe autorisée.

Commande propriétaire prête à copier **uniquement après nouvelle autorisation
explicite de cette lecture**. Elle n'est pas exécutée par l'agent. Le paquet
local mentionné existe ; son identité doit correspondre au B3 installé, faute
de quoi les contrôles existants échouent. Aucun choix automatique de nouveau BIN,
aucune compilation ni installation :

```powershell
Set-Location 'C:\Users\jerry\SHINO-TV-V06-AUDIT'
$b3Packet = 'research-local\m9-owner\b3-owner-20261011-120209\B3'
$b3Report = 'research-local\m9-owner\B3-readonly-coordinated-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N') + '.json'
py -3 companion\shino_coordinated_qualify.py `
  --bin "$b3Packet\.pio\build\esp12e_m9_4m2m_normal_qualification\firmware.bin" `
  --manifest "$b3Packet\release.json" `
  --identity 'research-local\m9-owner\owner-credentials.json' `
  --receipt $b3Report --b3-paced --http-diagnostics --authorize-read
```

Au plus90 GET logiques (plus les échanges401 Digest conservés),30 cycles,
durée minimale environ200 s plus HTTP/attente. Pas de POST du qualificateur,
pas d'OTA, de reboot ou de modification Wi-Fi. Arrêt au premier HOLD ; ne pas
relancer automatiquement un GET ambigu ni effacer un marqueur historique.
