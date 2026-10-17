# SHINO // LINK — M3-G : parité **exécutée** des métriques dans un HTTP de laboratoire

**17 octobre 2026 — décision : GO logiciel HOST uniquement.**
Base exacte PR #61 M3-F `96289f7e6700619d156f7f66703d19b1598e9b10`,
avec 9/9 workflows SUCCESS avant branchement.

## Ce qui change réellement

Les prototypes précédents possédaient :
- un transport M3 contrôlé mais des routes B5.3 historiques toujours 503 ;
- un banc historique de vrais sockets TCP + vérification mathématique
  d'un Digest MD5 de démonstration + cookie d'accès en RAM,
  mais des réponses de télémétrie déterminées par **deux chaînes JSON figées** ;
- un second banc qui compilait le **vrai** `FslessMetrics.cpp` avec
  **ArduinoJson 7.4.3**.

M3-G crée un banc qui relie les deux dernières preuves **dans le même
processus serveur HOST**. Il réutilise l'entrée bornée existante
`NativeOtaSingleIngressShadow`, le contrôleur de session et le banc
Digest réel `tools/native_ota_integrated_auth_loopback.cpp`, puis
remplace le décodeur à deux chaînes par **l'original, non modifié**
`firmware/src/boot/FslessMetrics.cpp` et le véritable ArduinoJson 7.4.3.
`FslessMetrics::apply` modifie **uniquement la mémoire volatile du
processus Linux HOST**, et `FslessMetrics::describe` fournit les
vraies valeurs de ce processus en réponse au GET métriques déjà admis.
Les autres valeurs du endpoint restent marquées `host_fixture_only`.

Ce n'est **ni** le `ESP8266WebServer` installé ni une intégration
au `M3FSinglePortPump`. L'objectif ciblé est la **parité métier
réelle CPU, GPU, RAM, GPU TEMP / validation numérique / lecture
des données dans le même serveur de laboratoire**, avec une
frontière d'authentification distincte.

## Contrat de test de bout en bout

20 connexions HTTP/1.1 réelles à `127.0.0.1`, port éphémère,
une seule socket d'écoute. Les requêtes utilisent le Host
`192.168.4.1` **uniquement comme texte**, aucune connexion à
l'AP SHINO ni au LAN propriétaire :

- `GET /` non authentifié → défi Digest 401.
- `GET /` avec Digest MD5 de démonstration réellement calculé →
  contenu HTML existant + cookie de lecture jetable.
- `GET /api/v1/bridge/metrics` avec cookie jetable →
  valeurs sorties de **`FslessMetrics::describe` original**.
- `POST /api/v1/bridge/metrics` avec seul cookie ou mauvais Digest
  → 401, échantillon RAM inchangé ; avec vrai Digest de démonstration
  → `FslessMetrics::apply` source originale, HTTP 200.
- Valeurs hors plage ou JSON mal formé → 422 et conservation du
  dernier bon échantillon ; dénominateur RAM absent → indisponible
  sans fabriquer 16 GB ; TTL strictement six secondes dans la
  source originale.
- `GET /api/v1/bridge/status` avec seul cookie → pas d'autorité
  privilégiée ; `GET /ui.js` avec cookie valide → vrai JS original.
- Namespace OTA upload, retour OEM non activé, fausse session
  et routes interdites → aucun writer, refus/challenge.

Les mots de passe, nonce, Digest et cookie présents dans les sources
de test sont **fictifs, publics et déterministes**. Aucun secret
propriétaire consulté ou exposé. La comparaison des Git blobs
de `FirstBootBridge.cpp`, `HomeLan.cpp` et `FslessMetrics.cpp`
protège l'identité du graphe métier étudié sans prétendre avoir
identifié le BIN installé.

## HOLD critiques

1. **Pré-corps Digest : HOLD.** Dans ce banc historique, l'entrée
   bornée reçoit le corps ≤384 octets **avant** vérification du Digest.
   L'état RAM n'est muté qu'après authentification, mais cela ne
   satisfait **PAS** le nouveau contrat M3 d'authentification
   avant lecture de la première donnée. Le HMAC M3 reste un chemin
   séparé M3-F ; ne jamais ajouter une route M3 via ce modèle.
2. **Identité de boot / nonce Digest : HOLD.** Le nonce MD5 de
   démonstration est fixe, le nombre d'utilisations est
   **insuffisamment contrôlé** pour en déduire l'anti-rejeu.
   Le vrai Digest du Core 3.1.2 et les sessions navigateur réelles
   doivent être revus lors d'une refonte, pas copiés aveuglément.
3. **Parité serveur produit complète : HOLD.** Le banc ne porte pas
   le vrai `FirstBootBridge.cpp`, `HomeLan.cpp`, les routes Wi-Fi,
   l'authentification d'origine sur les interfaces réelles, la
   récupération OEM, le contrôle d'affichage, les transports média
   ou l'OTA. Aucun callback LCD/RTC/LittleFS.
4. **Ressources/ordonnanceur : HOLD.** Exécution HOST ne mesure pas
   heap/largest-block, pile réelle, Wi-Fi/lwIP, watchdog,
   traitement des clients simultanés ni latence PC 2s/TTL6s.
5. **Activation physique : NON AUTORISÉE.** Ni mise en marche de
   listener SmallTV, ni firmware flashable, ni OTA, ni Wi-Fi,
   ni déploiement de SHINO LINK ou merge. Le firmware installé
   n'a pas été relu pendant cette intervention : **NON VÉRIFIÉ**.

## Critère de sortie

PASS M3-G = les **tests ciblés au dernier SHA** exécutent
de vraies requêtes TCP via la vraie bibliothèque ArduinoJson et le
`FslessMetrics.cpp` **inchangé**, avec Digest réellement
calculé à partir des fixtures et conservation du dernier échantillon.
Ce résultat est un progrès de **parité du métier télémétrie en HOST**,
**pas un PASS du serveur unique sur ESP8266**.

**Prochain jalon recommandé :** brancher un adaptateur de handlers
B5.3 autorisé **dans le vrai graphe natif de qualification**,
tout en conservant un seul propriétaire de port et les routes
de secours. Mesurer le coût heap/stack/WDT réel, puis revoir
le contrôle M3 avec un protocole cryptographique différent du
Digest legacy. Pas de GO appareil sans identité candidate
et procédure de récupération vérifiées.
