# SHINO // LINK — M3-I : un unique listener HOST, deux chemins d'authentification réellement exercés

**17 octobre 2026 — GO propriétaire logiciel uniquement, aucune intervention appareil.**
Base : Draft PR #63 M3-H `c87e88267a3ca09e074a9a8419b1cc336eddd4b6`, **11/11 workflows GitHub PASS vérifiés avant branchement**.

## Objectif concret

Les étapes précédentes étaient séparées :
- M3-G : **vrai TCP localhost**, Digest MD5 de **test** calculé avec OpenSSL, modèle de cookie historique, source **originale `FslessMetrics.cpp`** et ArduinoJson 7.4.3 ; pas de M3.
- M3-C/D : **vrai HMAC-SHA256 avant corps**, contrôle strict Content-Length/JSON, FIN du client dédié, mais pas de télémétrie ancienne.
- M3-H : le **vrai ordonnancement PC `LinkEngine`**, scène M1, ACK M3 simulé et véritable code télémétrique C++ via **pipe HOST**, pas de HTTP partagé.

**M3-I les exerce, pour la première fois, dans un seul programme serveur HOST**, `experiments/link_m3i_single_listener/single_listener_real_metrics_and_m3c.cpp`.

Une seule socket `bind(INADDR_LOOPBACK)`, port éphémère choisi par l'OS, `listen` une fois. Avant toute lecture massive, le serveur lit **la première ligne exacte, octet par octet, plafonnée à 128 octets**. Il route **strictement** :

- `POST /api/v1/display/mode HTTP/1.1` : transfert direct de la même connexion au **vrai `M3CAuthenticatedIngress.h::Gate`**, HMAC-SHA256 OpenSSL sur l'en-tête **avant de lire le premier octet de corps**, contrôle du SHA256 réel et des octets canoniques JSON, bornes 1024 en-tête et 240 corps (depuis M3-C), FIN par demi-fermeture d'écriture du client, refus de toute donnée au-delà du corps. Ledger CAS **sériel et en RAM du HOST seulement**. La réponse **202 `applied:false`** dit explicitement qu'aucun affichage n'a changé.
- **Routes historiques** : la première ligne pré-lue est donnée au vrai `NativeOtaSingleIngressShadow` existant, puis la requête suit le chemin éprouvé M3-G : Digest de test vérifié, cookie GET strict, `NativeOtaLegacySessionReview`, `NativeOtaLegacyResponsePreview` ; sur POST metrics admis, appel **effectif à la vraie source non modifiée `firmware/src/boot/FslessMetrics.cpp::apply`** et sur GET metrics, son `describe`. Dashboard HTML/JS identiques aux sources `FslessWebUI.cpp`.
- **Toutes les routes OTA write/retour constructeur** restent refusées. Aucun moteur d'OTA, writer flash/LittleFS ni scène LCD.

La source de données métriques acceptées est la véritable implémentation C++ du firmware, mais elle modifie seulement la **RAM du processus HOST sur le runner**. Aucun POST réseau dirigé vers SmallTV.

## Qualification

Le workflow `link-m3i-single-listener.yml` compile un **seul binaire HOST** avec les sources B5.3 non modifiées, ArduinoJson 7.4.3 épinglé, et le **vrai Gate M3-C HMAC**. Il lance **séparément sur ce même binaire** :

1. **20 requêtes HTTP du banc M3-G d'origine**, afin de détecter immédiatement une régression sur dashboard, cookie de lecture, Digest, télémétrie et voies refusées ;
2. **19 vraies requêtes TCP intercalées** entre métriques héritées et commandes M3 : header falsifié rejeté avant toute donnée de corps, transaction M3 valide, readback télémétrique inchangé, replay/stale header rejeté, nouvelle transaction, SHA de corps corrompu, bytes supplémentaires, client classique sans FIN refusé avant deadline, nouveau POST métrique toujours possible, dernier commit de laboratoire puis refus OTA/OEM et JS du dashboard toujours disponible ;
3. Tests d'identité Git exacts des sources B5.3, régressions cryptographiques M3-C OpenSSL et 26 scénarios M3-A de non-retry.

**Les résultats de CI ne sont acquis qu'après fin des jobs sur le SHA final** ; ne pas reprendre un PASS historique. Le nombre de requêtes est celui des tests de laboratoire, pas une mesure de charge ou de débit ESP8266.

## Sécurité : limites critiques NON levées

**M3-I n'est PAS un serveur ESP8266 compilé pour le SmallTV.**
Son adaptateur de socket utilise **POSIX `poll`/`recv`**, OpenSSL et des tableaux/allocations HOST. Cette démonstration ne possède ni `ESP8266WebServer` ni un `WiFiServer` natif qui partage effectivement le port 80. Le firmware B5.3 installé reste intégralement indépendant.

Le Digest legacy est toujours **vérifié après une lecture bornée du corps POST métriques** (jusqu'à 384 octets), comme dans M3-G ; la garantie « authentification pré-corps » **ne concerne que le chemin M3-HMAC**, pas les routes historiques.

Les clés HMAC, mot de passe Digest, nonce et cookie sont des **fixtures publiques déterministes**, jamais des secrets du propriétaire ou de la Freebox ; le labo ne valide ni provisionnement, ni entropie de boot, ni anti-rejeu inter-reboot.

L'exacte identité firmware installée aujourd'hui, heap, largest block, CONT, stack ESP8266, IRAM, scheduler métriques 2 s / TTL 6 s, conflits Digest réels, délai lwIP, conservation OTA/OEM/HomeLAN/wifi, l'affichage effectif 240×240, ACK réel et statut rendu restent **HOLD / NON VÉRIFIÉS**. Un `202 applied:false` est une preuve de parsing/authentification labo, **pas un ACK SmallTV**. Le passage sur matériel nécessite un nouveau mandat pour un candidat BIN exact avec voie de secours prouvée.

La politique des modes **AUTO, CLOCK_WEATHER, MONITORING, MUSIC** reste celle de M1/HOST ; les effets visuels ne sont pas activés par le serveur M3-I. Les changements de scènes ne viennent jamais automatiquement de ce binaire de test. Aucune commande réseau Windows n'est activée dans SHINO LINK installé.

Aucun fichier sous `firmware/` ou `companion/` modifié ; aucune OTA/flash, RTC, Wi-Fi, Freebox, LittleFS, redémarrage, merge ou installation, aucun conflit avec Codex B5.4.

## Suite technique

**M3-J** : porter et qualifier l'interface de réception/dispatch dans **un vrai graphe Xtensa**, idéalement en preservant `FirstBootBridge`/`HomeLan` sur le port 80 unique. L'adaptateur natif doit conserver Digest/cookies, telemetry, M8/media, constructeur/OTA et les restrictions AP/STA, puis **mesurer mémoire et stack/CPU/WDT** avant toute intention de pilotage réel. Ne pas ajouter un second `WiFiServer(80)` ni brancher M3 sur `server.on` avec body pré-bufferisé.
