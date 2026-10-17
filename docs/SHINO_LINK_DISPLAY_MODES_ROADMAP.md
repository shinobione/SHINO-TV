# SHINO // LINK — Centre de contrôle Windows et modes d'affichage
**Décision produit proposée le 17 octobre 2026 — ROADMAP / DESIGN UNIQUEMENT.**
**État : PLANIFIÉ / NON IMPLÉMENTÉ / DEVICE NON TESTÉ.**

## Besoin propriétaire
Faire évoluer l'actuel SHINO // LINK en une application Windows légère, avec
icône tray, menu rapide et fenêtre de paramètres, permettant de sélectionner
immédiatement un mode d'affichage du SmallTV-Ultra. Un choix manuel prime sur
les changements de contexte (Spotify, jeu, télémétrie) jusqu'au retour explicite
à Automatique. La page web existante reste un accès secondaire aux diagnostics
et au secours ; elle n'est pas remplacée ni désactivée par cette étude.

Ne pas confondre cette cible avec l'état installé. Au checkpoint physique B5.1
du 13 octobre, le propriétaire a rapporté un boot/LAN/Freebox, LittleFS, les
quatre mesures via LINK sur PC Ethernet. B5.2 horloge et publisher sont des
travaux offline dans les PR #48/#49, non qualifiés sur le SmallTV. Le rendu
musical natif et les pochettes relèvent d'une intégration future ; l'horloge
et la météo autonomes PC éteint demandent un fournisseur indépendant du PC,
une synchronisation de l'heure et des essais physiques distincts.

## Décision d'architecture à instruire
**Préférence : faire évoluer LINK, ne pas créer un second agent concurrent.**
Conserver un processus unique avec acquisition CPU/GPU/RAM/GPU temp, transport
Digest et TTL 6 s inchangés, surveillance des sessions média, reconnexion et
démarrage Windows actuel. Ajouter des modules séparés : politique des modes,
état confirmé du SmallTV, menu tray, fenêtre optionnelle de configuration et
persistance locale opt-in. Un exécutable Windows sans console pourra emballer
ce même cœur **après** revue des dépendances/distribution ; ne pas dupliquer
le worker ni mettre un serveur supplémentaire sur le SmallTV.

L'interface web reste complémentaire : diagnostics, provisionnement et secours
lorsque LINK est absent. Si une commande web de mode est ajoutée plus tard,
elle devra partager la même autorité et les mêmes règles de priorité, sans
dualité de pilotes ou changement implicite de propriétaire.

### Quatre choix visibles
| Choix utilisateur | Décision de rendu attendue |
| --- | --- |
| **Automatique** (défaut) | Musique active et valide : PLAYING ; sinon PC avec métriques fraîches : IDLE hybride (CPU, GPU, RAM, GPU temp + horloge/météo seulement si valides) ; sinon CLOCK_WEATHER autonome si ses sources sont valides, ou état OFFLINE honnête. Politique PAUSED à préciser avec le propriétaire. |
| **Horloge / Météo** (manuel) | Scène CLOCK_WEATHER **sans cartes PC**, même si musique en cours ou télémétrie reçue. Si heure ou météo indisponibles, afficher explicitement leur état et leur ancienneté ; ne pas inventer de valeurs. |
| **Monitoring PC** (manuel) | Conserver ensemble les quatre cartes, libellées exactement `CPU`, `GPU`, `RAM`, `GPU temp`, avec barres et fraîcheur indépendantes ; aucune transition automatique vers PLAYING. En absence de télémétrie fraîche, ne jamais présenter d'anciennes mesures comme live. |
| **Musique** (manuel) | Afficher titre, artiste, pochette carrée si disponible, timeline/lecture/paused selon données valides ; pas de cartes PC. Si aucune session active ou image absente, afficher un écran de repli explicite, sans ancienne pochette ni bascule automatique vers Monitoring. |

Le mode **CLOCK_WEATHER seul** est distinct de l'actuel IDLE hybride
(horloge + quatre cartes) : ne pas cacher les cartes de la scène IDLE par
simple effet CSS/masquage improvisé. Chaque écran doit tenir réellement en
240 × 240, avec contraste et typographie validés sur l'écran physique.

### Invariants de priorité et de vérité
1. Un seul propriétaire de sélection à la fois : un choix manuel confirmé
   prend priorité sur toute règle automatique ; seul un nouvel ordre explicite
   (ou une réinitialisation volontaire documentée) le remplace.
2. Séparer `mode_demandé` (Windows), `mode_confirmé` (retour authentifié du
   firmware) et `scène_effective` (peut afficher une dégradation/fallback).
   L'interface indique `EN ATTENTE` ou `INCONNU` plutôt qu'un faux succès.
3. Une perte de PC/Wi-Fi, de média ou de télémétrie n'efface pas silencieusement
   la préférence. Pour Monitoring indisponible, afficher état STALE/OFFLINE ;
   pour Musique, `Aucun média` ; pour Horloge/Météo, afficher la donnée valide
   et marquer l'indisponible. Fallback de sécurité possible, distinct du choix.
4. La persistance du choix manuel est **optionnelle, désactivée par défaut**,
   dans une configuration privée locale Windows, écriture atomique uniquement
   sur changement utilisateur. Aucune écriture LittleFS à chaque changement.
   Après boot appareil ou redémarrage LINK, réconciliation prudente par lecture
   du mode/identité/compatibilité ; ne pas supposer que le SmallTV se souvient.
   Pour un PC éteint, le mode automatique autonome nécessite alimentation USB
   persistante et fournisseurs de temps/météo côté SmallTV : NON VÉRIFIÉ.
5. Après commande avec résultat réseau ambigu : **UNKNOWN/HOLD, aucun renvoi
   aveugle**. Une nouvelle commande requiert réconciliation sûre et intention
   fraîche ; ne jamais rejouer automatiquement un POST déjà potentiellement
   appliqué. Aucun override d'une cible ou d'un boot différents sans revue.

## Séparation des responsabilités (conception)
```text
Windows — un seul SHINO // LINK
  Sampler métriques  ─┐
  GSMTC / pochette   ─┼─> snapshots bornés / état de fraîcheur
  Heure / météo PC   ─┘
       |
  ModePolicy: AUTO ou MANUEL + priorité + fallback + état demandé
       |
  ControlPlane / coordonnateur Digest (transactions bornées, priorité métriques)
       |
  SmallTV — serveur HTTP existant, admission + authentification + capacités
       |
  Machine d'état des scènes natives (mode confirmé, source et validité)
       |
  Rendu ST7789 240 × 240 ; aucune allocation framebuffer plein écran
```

Contrat futur **à concevoir, pas route HTTP existante** : commande de mode
à schéma fermé/versionné, liste d'énumérations restreinte, taille/délai fixés,
source authentifiée, association au bon appareil/boot, anti-rejeu et statut
de lecture séparé (capacités, mode confirmé, scène effective, raison d'échec).
Garder le serveur/port existant, l'autorité Digest/HMAC revue et le verrou
Windows partagé. Ne jamais utiliser le POST des quatre métriques pour un
contrôle de modes, ni exposer un écrivain JSON arbitraire, une route de flash
ou un nouveau privilège OTA. Le contrôle n'implique aucun changement de
LittleFS, RTC, Wi-Fi ou SDK.

Priorité d'ordonnancement : métriques existantes environ toutes les 2 s et
TTL 6 s en premier ; clock publisher B5.2 optionnel, même verrou/budget ;
commandes de mode sur transitions utilisateur uniquement, pas de polling
rapide ou seconde boucle réseau concurrente. Les commandes de contrôle
authentifiées n'ont pas de priorité absolue au détriment de la télémétrie.
Idempotence, séquencement, réponse/perte réseau et limites temporelles à
faire accepter par des tests HOST puis natifs.

## Windows GUI versus web — recommandation
| Critère | LINK GUI / tray | Page web embarquée |
| --- | --- | --- |
| Accès depuis PC | Menu contextuel immédiat, pas de navigateur | URL et navigation |
| Sources Windows | Déjà dans LINK, sans nouvelle passerelle | Toujours dépendant de LINK |
| CPU/RAM ESP8266 | Protocole de contrôle borné ; UI exécutée sur PC | Pages/assets/logique côté appareil |
| Distribution et maintenance | Une base de code, packaging à maintenir | UI web, auth et compatibilité navigateur à maintenir |
| PC éteint | Contrôle non accessible sans PC | Peut rester accessible sur LAN si l'appareil est alimenté |
| Secours | Ne remplace pas l'AP/outil web | Conservé pour provisioning/diagnostic |

**Décision proposée : LINK GUI principal + Web minimal conservé.**
Un `.exe` empaqueté n'est pas automatiquement plus léger ni plus fiable que
le script actuel : démarrage sans console, dépendances, signature, crash
recovery, auto-start et mise à jour seront vérifiés sur Windows avant livraison.

## Découpage proposé et critères de sortie
| Phase | Portée | Validation et barrière |
| --- | --- | --- |
| **M0 — Inventaire / décision** | Revoir PR actives, HEADs, B5.1 installé, B5.2 et pilotes PR #40 ; relever contrats telemetry/Digest/tray, état des scènes, exigences 240² et accès web | Document de décision sans firmware modifié ; dépendances et risques notés |
| **M1 — Politique pure HOST** | Machine `AUTO / CLOCK_WEATHER / MONITORING / MUSIC`, priorité manuelle et décisions fallback ; tests d'événements et prévisualisation 240×240 | Tests Windows/CI de la table des transitions, sans aucun contact SmallTV |
| **M2 — Tray UX / configuration PC** | Menu radio + Auto, mode demandé/confirmé/inconnu ; fenêtre de configuration optionnelle ; unique moteur, instance lock, état atomique local opt-in ; pas de nouveau sender | Smoke Windows/pystray, sortie sans console lorsque empaqueté ; telemetry/clock inchangées |
| **M3 — Contrat contrôlé avec le firmware** | API d'admission étroite, capacités/version/identité, ACK de commande et lecture de statut, transactions protégées ; scène CLOCK_WEATHER distincte | Tests mauvais format/rejeu/digest concurrent/coupure/Wi-Fi/timeout/redémarrage sur HOST et code natif, revue heap/stack/flash |
| **M4 — Intégration scènes et média** | Brancher les scènes natives existantes avec la politique ; construire l'autonomie NTP/météo séparément ; musique/pochette seulement après validation du transport/rendu | Tests 240×240, données périmées, PAUSED, no-art, reconnection, LAN ; consentement physique sur candidat exact |
| **M5 — Qualification et distribution** | EXE Windows utilisateur léger + autostart sans console, dépannage et documentation ; qualification hardware longue, stabilité et récupération | Essais PC et SmallTV réellement observés, mémoire, LCD, cold boot, AP secours, OTA distincte ; aucune install sans GO exact |

Les étapes M1 et M2 sont possibles sans nouveau firmware, mais le SmallTV
ne peut pas appliquer physiquement les choix tant que M3/M4 n'existent pas.
Ne pas annoncer de date, de build physique, de taille ou de marge mémoire sans
artefact/mesure. Les évolutions B5.2 horloge, B5.3 autonomie, musique et OTA
conservent leurs validations indépendantes. Aucun merge ou déploiement impliqué.

## Matrice minimale à tester avant un GO physique
- AUTO: nouveau morceau, pause, arrêt, changement de source, PC déconnecté
  puis reconnecté ; distinguer résultats REPORTED vs interpolés.
- Horloge/Météo forcé: métriques reçues et Spotify PLAYING simultanés ;
  aucune sortie du choix manuel, même après changement de morceau.
- Monitoring forcé: musique en cours puis arrêtée ; quatre cartes visibles ;
  télémétrie périmée affichée comme telle.
- Musique forcé: aucune session, pochette absente, timeline invalide,
  source remplacée, lecture suspendue, données périmées.
- Windows: deux lancements, démarrage au login, fermeture tray, fermeture GUI,
  mode persistant ON/OFF, fichier de préférences corrompu, ancienne version,
  paquet EXE, absence de fenêtre PowerShell.
- Réseau/sécurité: firmware non compatible, boot/identité changés, 401, replay,
  challenge expiré, ACK perdu, coupure juste après envoi, concurrence métriques/
  horloge/OTA, Wi-Fi absent, AP secours, refus de commande non authentifiée.
- Device: 240×240 RGB565, CPU/RAM/heap/largest block/stack, watchdog et
  non-régression telemetry/Digest/HMAC/OTA/LittleFS/4m2m. Une CI PASS ne
  démontre pas l'acceptation sur l'appareil.

## Questions de politique encore ouvertes (pas des blocages M1)
- En AUTO, durée de la scène **PAUSED** avant de revenir à l'hybride PC :
  maintien / durée configurable / immédiat. Pas de valeur inventée.
- Si une commande Web manuelle est autorisée, quelle autorité tranche entre
  Windows/Web en cas de commandes contradictoires ? Recommandation : dernière
  commande explicite **authentifiée**, avec source visible et lecture confirmée.
- Si une préférence manuelle est enregistrée côté PC, la réappliquer après
  redémarrage de LINK seulement après identification positive du même SmallTV
  et résultat non ambigu ; sinon attendre intervention propriétaire.

## Portée de cette entrée roadmap
Documentation seulement. **Aucun code, firmware, build, API, exécutable,
installation Windows, démarrage autostart, réseau, SmallTV, OTA, UART,
flash, LittleFS, sauvegarde ou marqueur `.attempt` modifié.**
Dépendances actives : [roadmap](ROADMAP.md), [handoff](AGENT_HANDOFF.md),
[LINK B5.2](B52_LINK_CLOCK_PUBLISHER.md), [scènes 240 × 240](design-reference/README.md).
