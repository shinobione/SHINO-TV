# SHINO // LINK — M3-F, laboratoire coopératif de serveur emprunté

**17 octobre 2026 — GO propriétaire : développement logiciel hors ligne.**
**ÉTAT : implémentation C++ transport emprunté, tests HOST et build Xtensa INERTES, PAS un firmware SHINO.**

Base de M3-F : PR Draft #60 à `e89377e5d080f07dd6fc9929cfff19b57698afb6`,
**8/8 workflows PASS au moment de la création de branche**. Les modifications
sont isolées sous `experiments/link_m3f_native/`, ce document et la roadmap.

## Source réelle, architecture

Le vrai serveur de la branche B5.3 inspectée est `FirstBootBridge.cpp` +
`HomeLan.cpp` : `Webserver` contient un `ESP8266WebServer` qui possède
en privé son `WiFiServer`. Rien dans l'API inspectée ne permet de lui
transférer directement une socket dont la ligne ou les en-têtes auraient
déjà été lus. **L'ajout du contrôle M3 à `server.on` n'est pas acceptable :
le POST normal aurait été bufferisé avant son handler.**

M3-F prend donc **un seul objet Server emprunté**, jamais créé ou démarré
par le composant : `SinglePortPump<Server,Client,Crypto>`.
Il appelle seulement `server.accept()` lorsqu'aucun client n'est
actif et traite **au maximum 32 octets par `poll()`**. L'ordonnanceur
extérieur peut donc continuer entre les tours ; ceci **ne prouve pas**
les délais WDT/metrics sur ESP8266. La première ligne est bornée
à 128 octets, avec deadline d'en-tête modèle de 1000 ms,
corps de 2000 ms ; les horloges sont injectées par les tests.

- **Commande M3** : la véritable grammaire M3-C reçoit l'en-tête
  octet par octet puis vérifie HMAC-SHA256 avec OpenSSL dans le HOST,
  SHA256 sur le corps, JSON canonique, FIN TCP et absence d'excédent.
  Le ledger M3-C refuse CAS périmé/rejeu **en RAM et série seulement**.
  Réponse **202, `applied:false`** ; aucune scène n'est changée,
  et ceci ne constitue jamais un ACK SmallTV.
- **Routes historiques** : `M3ELegacyRouteGate` est utilisé pour
  distinguer celles autorisées dans l'inventaire STA/LAN source B5.3.
  Le prototype renvoie **503 `LEGACY_NOT_PORTED`** pour toutes
  ces routes, **sans lire les corps ni tenter une authentification
  Digest factice**. Les chemins OTA upload/write et toutes routes
  inconnues sont également refusés. Aucune route n'est exécutée.
- **Structure réseau** : les tests HOST emploient un faux
  `WiFiServer/WiFiClient` à file mémoire avec l'API
  `accept/available/connected/read/write/stop` ; ils
  vérifient l'absence de lecture non autorisée du corps, la cadence
  de 32 octets maximum, les clients simultanés sérialisés et le
  timeout borné. **Ce ne sont pas de vrais sockets** pour M3-F ;
  les 12 échanges TCP réels de M3-D restent une preuve distincte.
- **Xtensa** : le programme inerte `src/main.cpp` instancie
  réellement le template avec **WiFiServer, WiFiClient et BearSSL
  du Core ESP8266 3.1.2**, sans appeler `begin()` ni l'API
  `poll()` pendant le fonctionnement inerte. Il compile/lie les
  types/méthodes natifs, mais **ne mesure ni l'usage de la boucle
  réseau réelle, ni le plus grand bloc heap libre, ni le WDT**.
  Toute taille/empreinte CI de ce BIN porte sur l'image **inerte**
  de laboratoire, non sur B5.3/B5.4.

## Ce que M3-F ne prouve PAS

- **La parité historique reste HOLD.** Toutes les routes Legacy
  renvoient volontairement 503 et n'accèdent ni au dashboard,
  ni aux valeurs CPU/GPU/RAM/GPU TEMP, ni au Digest/Cookie,
  ni à la voie constructeur. B5.3 en production continue d'utiliser
  **son serveur actuel inchangé**.
- Il **n'existe pas** de copropriété sûre entre `ESP8266WebServer`
  actuel et ce nouveau serveur : un vrai remplacement nécessiterait
  portage des handlers dans un unique propriétaire du port 80,
  en conservant les protections AP/STA, récupération OEM,
  HomeLAN, M8 media, clock, OTA et LittleFS.
- Aucun budget mémoire total du firmware, mesure mémoire
  high-water, taille BIN candidate, gestion réel de clients ou
  garantie de WDT et de cadence métrique sous charge n'est déduit
  du banc HOST ou du build inerte.
- Le vecteur HMAC utilisé dans le laboratoire est **public** ;
  il n'existe ni stockage propriétaire de clé, ni rotation,
  ni protection secrets, ni CSPRNG/nonce de boot prouvé.
- CAS appliqué uniquement au ledger de labo, aucune scène
  LCD 240×240, ACK natif, statut indépendant ni OTA.
- Aucun terminal UART/USB, aucune commande physique, aucun
  changement Wi-Fi, aucun flash, aucune intervention sur
  le SmallTV installé ou sur le LINK Windows.
- Branches Codex B5.4 et autres PR Draft non modifiées.

## Gates de sortie

| Test | Statut requis |
| --- | --- |
| Source exacte B5.3 et HEAD de M3-E | PASS à vérifier au dernier SHA |
| HMAC réel, lecture après auth, FIN/CAS/timeout et budget par poll | HOST à vérifier |
| Compilation et édition de liens WiFiServer/WiFiClient/BearSSL | Xtensa inerte à vérifier |
| Compatibilité réelle des routes HTTP historiques | **HOLD** |
| Port 80 unique physique, lwIP, watchdog, auth native, équité télémétrie | **HOLD** |
| Boot token/clé secure/cas atomique et écran rendu | **HOLD** |
| Flash/OTA/reboot/provisioning | **AUCUN GO** |

**Étape suivante envisagée :** revoir l'architecture d'un propriétaire
HTTP unique avec portage *exécutable* des handlers historiques. Avant
toute image candidate, qualifier les sources en tenant compte de
l'évolution B5.4 de Codex, vérifier occupation et pointes mémoire,
équité du worker 2 s / TTL 6 s et sécurité de la voie de récupération.
Ne pas fusionner automatiquement les PR empilées.
