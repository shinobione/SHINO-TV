# SHINO // LINK — M3-M : première extraction native du traitement métriques B5.3

**18 octobre 2026 — GO propriétaire pour développement et tests logiciels uniquement.**
Base : PR #67 M3-L, SHA `986e6a59d4f7035dff203ac0185df792b216658b`,
**16/16 workflows SUCCESS** vérifiés avant branchement.

## Source du problème

Le vrai `firmware/src/boot/FirstBootBridge.cpp` (blob Git
`705028430a854537924ef30a83a1761d0670387e`) construit
`ESP8266WebServer server(80)`, puis enregistre ses handlers par
`server.on(...)` et appelle `server.handleClient()`.
`HomeLan.cpp` fournit sa politique AP/STA, Digest, le provisionnement
Wi-Fi et les voies de récupération.

Le POST métriques B5.3 :
- passe `requireAuth()` et les vérifications de routage HomeLAN ;
- récupère la chaîne bornée depuis `server.arg("plain")` ;
- utilise **le vrai `FslessMetrics::apply`** pour refuser les
  champs incomplets, invalides ou non finis sans écraser
  l'ancien échantillon ;
- répond `200` avec `RAM_SAMPLE_ACCEPTED` ou `422`.

Le GET :
- exige une session de lecture validée (cookie lié au peer)
  ou le parcours Digest qui délivre celle-ci ;
- utilise **`FslessMetrics::describe`** et la TTL de 6 secondes.

Ces handlers ne peuvent pas simplement être déplacés dans
`M3FSinglePortPump` : le serveur ESP8266 historique possède les sockets
en privé et ses méthodes d'authentification/cookies sont liées à cet
objet. Brancher un `server.on` M3 serait trop tard pour garantir
l'authentification HMAC **avant tout octet du corps**.

## Code réellement créé

`experiments/link_m3m_native/M3MActualMetricsHandler.h`
fournit une **brique de traitement métier compilable
avec ArduinoJson 7.4.3 et le vrai code métriques B5.3**, non
un deuxième serveur :

- méthodes GET et POST sur **exactement**
  `/api/v1/bridge/metrics` et politiques de route HomeLan existantes ;
- autorité `verifier.permit(verb,network,path)` **obligatoire**
  avant lecture des octets de corps ou allocation de `JsonDocument`.
  Il n'existe pas de vérificateur de production dans cette tranche :
  l'implémentation native de laboratoire utilise une fixture
  `fakePermit=false` jamais activée ;
- corps POST explicitement borné 16–384 octets, JSON
  `application/json`, longueur exacte, refus de
  `Transfer-Encoding` et de l'absence de fin de corps ;
- parsing avec **vrai ArduinoJson** puis appel de
  **`FslessMetrics::apply` inchangé**. GET avec
  **`FslessMetrics::describe` inchangé**, réponse bornée
  dans un **buffer fourni par l'appelant** (896 octets ici) :
  pas de tableau de 896 octets sur la CONT de la fonction ;
- résultats HTTP `200`, `400`, `403`, `404`,
  `422` et `500`, sans transmission réseau implicite,
  état LCD, writer OTA ou LittleFS ;
- les refus conservent l'ancien échantillon, le TTL reste
  celui de `FslessMetrics.cpp`. Le vrai
  `telemetryNeedsRedraw` appartient à FirstBootBridge
  et n'est **pas** implémenté par cet adaptateur isolé.

## Qualification

Le nouveau workflow M3-M compile le **source original** B5.3
avec ArduinoJson réel dans un exécutable HOST. Il exerce
les droits de lecture/écriture séparés, GET sans données,
POST authentifié, échantillon mauvais puis dernier bon conservé,
JSON malformé, trames invalides, Content-Length, TE,
mauvaise route, cap de réponse et TTL.

Un second job compile de vrais ELF Xtensa Core ESP8266 3.1.2,
identiques sauf présence de l'adaptateur source-réel.
La seule branche native dispose d'un serveur
`WiFiServer(80)` **construit mais jamais démarré** et d'une
sonde volatile normalement désactivée. Comparaison ELF
text/data/bss, BIN et SHA calculés depuis les fichiers
produits par CI, frames de pile `-fstack-usage`.
**Aucun nombre inventé avant résultat au SHA exact.**

## Mesure initiale native : véritable sortie CI, mais build inerte

[Workflow M3-M #39134324424](https://github.com/shinobione/SHINO-TV/actions/runs/39134324424)
au commit `fd19152b4eb9a12ecf6edad7fea62978e9920fad` :
**2/2 jobs SUCCESS**, avec tests B5.3 source-exécutés
et deux builds Xtensa liés.

| Sortie de laboratoire Xtensa | A : code M3-L existant + FslessMetrics | B : même graphe avec adaptateur M3-M | Différence |
|---|---:|---:|---:|
| Taille du BIN **inerte** | 276 784 o | 281 120 o | **+4 336 o** |
| ELF `.text` | 271 131 o | 275 475 o | **+4 344 o** |
| ELF `.bss` | 27 392 o | 28 288 o | **+896 o** |
| ELF `.data` | 1 556 o | 1 556 o | **0 o** |

Les **896 octets supplémentaires de BSS** proviennent
du tampon `replyStorage` de la fixture native,
fourni par l'appelant ; il évite une allocation
de réponse massive sur la pile de l'adaptateur,
mais **consomme tout de même de la RAM statique**.
Ce tampon n'est PAS identifié comme existant ou
réutilisable dans le firmware B5.3 complet :
réemploi sans preuve serait dangereux. Le coût
est celui de la combinaison compilée, pas une
prévision du budget libre sur appareil.

Le chiffre BIN de cette fixture n'est ni le BIN B5.3
physique de 426 752 octets, ni un candidat OTA.
Les deux processus HOST utilisés comme témoins
authentifient avec des politiques de **laboratoire**,
non le Digest réel du SmallTV.

Les 2 jobs devront être **rejoués sur le HEAD final**
après ces notes ; aucun PASS global n'est présumé.

## BLOQUAGES ET RISQUES

**M3-M n'est pas une migration complète de FirstBootBridge.**
Il manque le réel vérificateur Digest/cookie, la politique
d'autorité réseau liée au client natif, l'authentification avant
corps de toutes les routes concernées, le transport HTTP de
réponse, la gestion des écritures courtes, les callbacks de
redessin LCD, les handlers Wi-Fi, OTA/OEM, diagnostics,
musique et MEDIA. Aucune preuve de parité complète B5.3.

L'objet `Request` est déjà en mémoire à l'appel :
l'ordre interne des vérifications **ne prouve pas** que le
transport a authentifié un client AVANT une lecture TCP.
Pour M3 les garanties HMAC pré-corps restent celles de
M3-C/M3-I, pas de cet adaptateur legacy.

Les montants de RAM et pile d'une application **inerte**
ne certifient ni heap/CONT, ni pics WDT, ni boot réel.
Le préflight physique B5.3 communiqué antérieurement
reste STOP/HOLD avec une marge CONT observée de 80 octets.
**Aucune OTA autorisée par M3-M**.

Ni `firmware/`, ni `companion/`, ni LINK Windows installé,
ni SmallTV, ni Freebox/météo, ni B5.4 Codex ne changent.
Pas d'enregistrement de route, pas de `WiFiServer.begin()`,
pas de secrets propriétaires, flash, OTA, EEPROM, Wi-Fi,
RTC, reboot, merge ou suppression de reçus.

## Suite rationnelle

Il faut avant toute activation un adaptateur **d'autorisation
source-réel** qui possède le client accepté, le nonce et
les sessions Digest et les contrôles d'interface AP/STA,
puis un **unique** graphe de handler HTTP complet vérifié
route par route, avec retour de réponse et contraintes de
mémoire/stack mesurées sur une véritable image qualifiée.
Ne pas déduire un GO physique d'une démonstration de compilation.
