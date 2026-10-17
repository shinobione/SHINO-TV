# SHINO // LINK — M3-H : télémétrie prioritaire et politique des modes en HOST

**17 octobre 2026 — GO propriétaire M3-H, logiciel uniquement.**
Base PR Draft #62 M3-G, HEAD `a1875beac5ffebdb154ebced85c2df4163c9530a`, **CI 10/10 SUCCESS** vérifiée avant branchement. Aucun propriétaire du port 80 natif B5.3 n'est modifié.

## Résultat logiciel concret

`experiments/link_m3h_host/owner_priority.py` connecte **sans modifier**
trois couches déjà existantes :

1. **Le vrai `companion/shino_link.py::LinkEngine`** et ses échéances de télémétrie après chaque POST. Le banc injecte un **émetteur en mémoire**, sans connexion IP, mot de passe ni processus Windows lancé.
2. **Le vrai `companion/link_display_modes.py::decide`** avec les quatre modes `AUTO`, `CLOCK_WEATHER`, `MONITORING`, `MUSIC` et l'observation locale de fraîcheur de `link_mode_tray.py`. Les signaux musique/heure/météo sont **explicitement fournis** par la fixture, jamais inventés à partir du seul ACK métriques. Sur B5.3 LEAN, météo valide reste fausse, sauf simulation annoncée.
3. **Le vrai contrat de transactions M3-A** `experiments/link_m3_control_contract/control_contract.py`, **strictement `FakeDevice` + `LabTransport` en mémoire**. Un clic utilisateur, une transaction unique et une fenêtre sûre après télémétrie peuvent déclencher **au plus un POST simulé**. M3-A confirme séparément un ACK et une lecture de statut **simulés** ; son champ de scène `OFFLINE` rappelle explicitement qu'aucun pixel ne change.

L'état local `Snapshot` sépare la sélection demandée et l'aperçu PC, la fraîcheur et le rythme des métriques, la transaction en attente, le HOLD et la confirmation **simulée**. Ce résultat n'est jamais présenté comme l'état du SmallTV.

## Ordonnancement et erreurs — périmètre HOST

- À chaque `tick(now)`, **un envoi télémétrique échu précède toute simulation de commande**. On réemploie le vrai `LinkEngine.step`, y compris intervalle habituel 2s, backoff et conservation des dernières données après erreur.
- Une commande ne passe pas si la télémétrie est périmée, non connectée, ou si le prochain envoi est dans une **garde de 1s**. La garde est un paramètre de laboratoire **NON qualifié dans le scheduler ESP8266 ni dans un vrai verrou Digest**.
- La première opportunité sûre suivante peut traiter l'intention encore en attente **sans créer de nouveau clic ou transaction**. Le test n'exerce aucun vrai HTTP.
- Après un POST simulé dont l'ACK/readback est perdu ou incohérent : **HOLD irréversible dans cette instance** ; un clic ultérieur est refusé, aucun retry, les métriques continuent. Une réconciliation `GET` **simulée** ne lève pas le HOLD.
- Les changements de lecture audio peuvent changer l'**aperçu AUTO**, mais **ne génèrent pas de POST**. Revenir d'un mode manuel à AUTO requiert un **clic explicite** et une nouvelle transaction.
- Les signaux perdus affichent des scènes de repli honnêtes ; en MUSIQUE jamais de cartes métriques superposées. Les quatre mesures continuent à être collectées dans le banc même quand leur affichage est caché.

`test_owner_priority.py` couvre 9 scénarios : AUTO et TTL, manuel/retour AUTO, priorité à l'envoi échu, panne + backoff, perte d'ACK, anti-rejeu et clics rapprochés, nouveau boot, entrées invalides, clics concurrents.

## Ce que M3-H n'intègre PAS

**IMPORTANT : ce n'est pas encore « un même serveur ESP8266 »**. M3-G
établit séparément la parité HOST de `FslessMetrics.cpp` + ArduinoJson
7.4.3 dans de vrais sockets TCP. M3-H vérifie la **cohérence côté PC**
entre la machine `LinkEngine`, la politique M1 et le contrat M3-A
**simulé**. Les deux suites fonctionnent dans des laboratoires
distincts : ni M3-G ni M3-H n'ont été fusionnés dans un listener réel.

Ne pas prétendre que M3-H possède : sockets M3-C/BearSSL à côté du
Digest legacy dans un `WiFiServer` unique, autorité de boot et
clé HMAC réelle, CAS atomique de firmware, vrai verrou Digest Windows,
source GSMTC connectée, publisher météo, distribution EXE, rendu
240×240, status/ACK matériel, ou budget heap/stack/WDT natif.

Les sources historiques restent inchangées : `firmware/`,
`companion/`, SHINO LINK installé, B5.3, B5.4-LAN Codex,
les chemins Wi-Fi AP/STA, OTA, LittleFS, RTC, secrets et Freebox.
Aucun accès ni test appareil, et aucune opération physique autorisée.

## Prochain jalon : M3-I

Pour franchir la frontière, il faudra un **adaptateur natif exécutable**
avec un seul propriétaire HTTP conservant les vraies routes
`FirstBootBridge` / `HomeLan`, le prebody HMAC M3-C,
la télémétrie legacy/Digest et les protections OTA, puis mesurer
le budget mémoire/stack et le rendement LINK. L'activation de
commande appareil attend un nouveau GO propriétaire ciblant un BIN
identifié et sa récupération démontrée.

**Acceptation de M3-H :** tests HOST exact-HEAD et régressions M1/M2/M3-A
PASS, sans action physique. Toute CI en attente est signalée.
