# SHINO // LINK M3-Q — Headers bornés après handoff M3-O

**19 octobre 2026 — recherche HOST et Xtensa inerte seulement.**

## Référence et cause

Base : PR #80 M3-P, HEAD 025c62400b21d981dea9baa24627e9c319aa75c6 (Draft).
Le Parsing-impl.h du Core Arduino ESP8266 3.1.2 lit encore les en-têtes
historiques via readStringUntil CR puis LF après la correction M3-P de la
première ligne. M3-O extrait seulement POST /api/v1/display/mode par
addHook + CLIENT_IS_GIVEN AVANT les en-têtes et le corps. Les routes
B5.3 continuent d'employer le Core original : elles ne sont PAS
protégées par le présent validateur M3-Q.

## Modification M3-Q

- M3QBoundedHeaders.h : **pas de String ni heap proportionnel à l'entrée**.
  Ligne de 320 caractères maximum, 960 octets maximum d'en-têtes,
  11 champs exacts, 1 000 ms absolues depuis la prise en charge.
  Un seul octet par read ; arrêt exact à CRLF CRLF ; le corps reste non lu.
- 11 champs autorisés : Host, Content-Type, Content-Length, Connection,
  X-Shino-Device, X-Shino-Boot, X-Shino-Revision, X-Shino-Mode,
  X-Shino-Tx, X-Shino-Body-Sha256, X-Shino-Proof.
  Champs inconnus ou dupliqués refusés ; aucun Transfer-Encoding,
  Expect, Origin, ligne repliée ni Content-Length multiple.
- Profil fidèle aux règles syntaxiques M3-C : longueur strictement
  décimale 1..240, connection close, application/json ; Host seulement
  syntaxique. **Origin reste interdit par le profil M3-C actuel**,
  politique navigateur et Host exact encore à résoudre.
- ReadyForAuth ne signifie **jamais AUTHENTIFIÉ** : aucune identité/boot,
  aucune clé/HMAC, aucune révision réelle ou digest du corps contrôlé,
  aucune commande d'écran, aucun ACK, aucune permission de lire le corps.
  L'instance stocke une seule ligne et des indicateurs, PAS toutes
  les valeurs des champs : la future intégration à M3-C reste à concevoir
  avec mesure mémoire et sans double-parsing risqué.
- Deux variantes Xtensa **INERTES** : M3-P seule et M3-P + lecteur
  M3-Q. Core ESP8266 3.1.2 cloné et épinglé avec le script M3-P inchangé ;
  vrai handleClient compilé, aucun listener démarré et aucun client connecté.
  Rapports calculés à partir des BIN/ELF de CI, pas du firmware produit.

## Observations, incidents et limites

- Tests C++ HOST vérifiés dans la CI GitHub du 19 octobre 2026 :
  PASS. Exécution indépendante ASan/UBSan locale : **NON VÉRIFIÉE**.
  Scénarios : fragmentation, slowloris et millis wrap, erreur EOF,
  NUL, CR/LF, headers dupliqués, valeurs/content length ambiguës,
  320 accepté / 321 refusé, body strictement non consommé.
- Incident initial du laboratoire : le validateur bloquait par erreur CR/LF
  dans la vérification de caractères avant traitement du terminateur.
  Correction : exception explicite CR/LF dans le contrôle des octets,
  puis tests recompilés. Premier essai des tests a aussi eu une erreur
  de compilation HOST : argument de tick non exploité ; corrigé.
- **CI vérifiée le 19 octobre 2026**, commit de code `56f0fb671d891c3bf18808fbd05950c75006030e`, [run #39279419973](https://github.com/shinobione/SHINO-TV/actions/runs/39279419973) : **2/2 jobs ciblés SUCCESS** (HOST + Xtensa inert).
  Le journal de job Xtensa affiche ces mesures directement dérivées des images **INERTES** :

  | Mesure | M3-P inerte | M3-P + M3-Q inerte | Différence |
  |---|---:|---:|---:|
  | BIN | 287 376 B | 288 816 B | **+1 440 B** |
  | ELF .text | 281 727 B | 283 163 B | **+1 436 B** |
  | ELF .data | 1 552 B | 1 552 B | **0 B** |
  | ELF .bss | 25 984 B | 26 320 B | **+336 B** |

  BIN inerte de référence SHA-256 : `4fdeddee5596669b6afef906afe6f2580df7763a2e9cdac543812f33c202c59f` ;
  BIN inerte M3-Q SHA-256 : `225cbeb00d2550b2516d2e265175ec80e4c43f7e1ba252c041d9c9f35a0fd9b3`.
  Ce ne sont **pas** les empreintes du firmware installé ni un candidat OTA.
  Le symbole du lecteur est retenu dans l'ELF modifié, absent du témoin.
  Codegen GCC : lecteur 48 B de frame, `validLine` 64 B, `decimal` 64 B ;
  ces frames ne sont PAS des mesures de la marge CONT physique ou du callgraph complet.
  Au même SHA, l'ensemble GitHub affiche **30 SUCCESS, 32 SKIPPED et 4 CANCELLED** parmi 66 checks :
  ne pas réduire ce résultat à « toutes les CI PASS ».
- **Conséquence de conception :** le garde M3-Q ne conserve pas les valeurs d'en-têtes ; M3-C dispose déjà d'un `Gate::headerByte` borné, qui conserve et authentifie le message avant le corps.
  Hypothèse M3-R à TESTER : ne garder qu'un chemin de parsing réellement utilisé (en réintroduisant dans M3-C la ligne exacte déjà validée par M3-P), au lieu de cumuler une instance M3-Q + le buffer de M3-C. Nécessite preuve de framing, identité, HMAC, zéro lecture de body pré-auth, EOF/reconnexion, mémoire de l'application entière et parité legacy. **Pas encore implémenté.**
- Le profil normal 4m2m, Digest B5.3, LittleFS, OTA, Wi-Fi Freebox, LCD
  et SHINO LINK Windows restent intacts. Aucun build laboratoire n'est
  autorisé pour installation.
- La parité des routes legacy est un contrôle de **source**, pas un test
  réseau. Heap, fragmentation, CONT, WDT, lwIP, concurrence et boot
  réels : **NON VÉRIFIÉS**.
- Dernier préflight propriétaire B5.3 : minimum CONT 2128 octets pour
  seuil 2048, **80 octets de marge**. Aucun GO physique.

## Décision

M3-Q recherche et CI uniquement ; HMAC et commande de mode **HOLD**,
mise en production, flash, Wi-Fi/Freebox et OTA **HOLD**.
Étape suivante après preuve CI : intégration unique au M3-C existant
sans duplication de buffers, ressources du graphe B5.3 complet, et
tests différentiels des routes Digest / telemetry / OTA.
