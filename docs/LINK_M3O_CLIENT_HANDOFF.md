# SHINO // LINK — M3-O : garder le serveur SmallTV actuel, tester le passage d'une connexion

**19 octobre 2026 — autorisation propriétaire : développement et CI hors appareil.**
Point de départ : PR #77 M3-N au HEAD
`82bb3ce3fc476cec361d707695e41f1ec5fefd24`.
**16/17 workflows PASS** observés au fork ; l'audit hors ligne était
encore en cours. Aucun échec déclaré, mais pas de 17/17 inventé.

## Explication produit

L'application Windows devra envoyer « Affiche horloge/météo » au
SmallTV, sans perturber les quatre mesures CPU, GPU, RAM et GPU temp.

Au lieu de réécrire le serveur du SmallTV (très coûteux et risqué),
le véritable **ESP8266WebServer 3.1.2** dispose d'un mécanisme
`CLIENT_IS_GIVEN` : il peut céder une connexion entrante à un
autre gestionnaire **avant de lire les en-têtes ou le corps**.
Les anciennes demandes continueraient à utiliser le serveur
historique, son Digest, son tableau de bord et son OTA/OEM.

**Cette étape ne fait que vérifier la reprise de connexion.
Aucun véritable changement d'écran n'est implémenté.**

## Ce que M3-O compile et teste

- `experiments/link_m3o_core/M3OClientSlot.h` : un seul
  client copié/conservé, refus de prise concurrente, fermeture
  unique ou expiration. Aucune lecture du corps ou émission
  de commande : même un POST d'affichage recevrait un refus.
- `experiments/link_m3o_core/M3OCoreHook.h` : utilise la
  vraie signature `ESP8266WebServer::addHook` sur Core 3.1.2,
  **uniquement** pour `POST /api/v1/display/mode`.
  Vérifie les adresses du vrai `WiFiClient` pour exiger
  STA domestique connectée et peer du sous-réseau ;
  AP/STA inconnu, mauvais verbe ou déjà occupé : refus.
  La route de télémétrie continue vers les anciens handlers.
- Host : simulation déterministe de copie de client avec
  référence partagée, libération de la référence d'origine,
  un seul `stop()`, refus de deux connexions, fermeture
  après expiration et absence totale de lecture des octets.
  Ce test **ne simule pas la pile lwIP véritable**.
- Xtensa : vrai code `ESP8266WebServer`, `WiFiClient`,
  `HomeLan::peerOnSubnet` compilé sur Core 3.1.2.
  Deux ELF **inertes** permettent de calculer les
  tailles réelles des deux BINs de laboratoire, la RAM
  statique et les annotations compilateur de pile.
  Les fonctions M3 ne sont jamais appelées normalement,
  aucun listener n'est démarré.
- Code source épinglé de `Parsing-impl.h`,
  `ESP8266WebServer-impl.h` et `ESP8266WebServer.h` :
  vérification par CI que le hook se situe après la première
  ligne, avant les en-têtes, et que le serveur relâche
  sa propre référence lorsque le hook retourne
  `CLIENT_IS_GIVEN`. La CI contrôle également l'ordre
  des hooks successifs : **le premier peut refuser et
  empêcher le second de s'exécuter**.

## Deux blocages non négociables

1. **Ligne de requête sans longueur maximale dans le Core
   d'origine** : avant tout hook, `readStringUntil('\r')`
   construit un `String` dynamique non borné. Même un
   hook d'authentification correct ne protège pas la mémoire
   de cette première allocation. **Interdit d'activer sur
   appareil** sans remédiation/qualification de cette lecture.
2. **Le changement réel d'affichage n'est pas prêt.** Le
   nouveau chemin ne lit ni les vrais en-têtes `Host` et
   `Origin`, ni le HMAC/JSON M3. De plus, le hook
   reçoit la méthode et l'URL, **pas les octets bruts de
   la ligne HTTP**, alors que M3-C signe et vérifie
   un format strict. Il faudra démontrer que cette
   conversion ne permet aucun contournement de version
   ou de canonicalisation, et vérifier les connexions
   lwIP, la sortie HTTP après erreur, la mémoire/CONT,
   les refus et le maintien du débit des métriques.

Ce banc **ne modifie pas** `FirstBootBridge.cpp`, ni
`HomeLan.cpp`, ni `firmware/`, ni `companion/`.
Le hook inerte n'est PAS attaché à l'instance réelle du
SmallTV et ne démontre PAS les conditions physiques.
Il faudrait le positionner **avant** le hook B5.3
`HomeLan::endpoint`, qui refuse actuellement cette
nouvelle route sur STA, tout en conservant des contrôles
LAN équivalents avant toute reprise.

Le SmallTV, SHINO // LINK Windows installé, Codex B5.4,
Freebox, météo, LittleFS, Wi-Fi, les secrets, l'OTA
et les voies de récupération restent **inchangés**.
Pas de merge, flash ni redémarrage.

## Décision

**M3-O est un jalon de faisabilité de reprise de
connexion, pas un produit utilisable.** Même si la
CI réussit, conserver M3 physique en HOLD. Le prochain
jalon devra résoudre la longueur de ligne HTTP,
l'authentification et le cycle de vie du client dans
un véritable chemin exécutable, puis chiffrer mémoire
et régressions sans altérer les routes historiques.

La marge CONT de 80 octets rapportée lors du
préflight B5.3 ne constitue aucune réserve garantie.
