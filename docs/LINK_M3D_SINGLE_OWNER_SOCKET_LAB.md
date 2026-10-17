# SHINO // LINK — M3-D : laboratoire TCP avec un seul listener (17 octobre 2026)

**MANDAT : GO logiciel pour l'étape suivante après M3-C.**
**HOLD intégration produit, appareil, firmware, OTA, clés de production et B5.4 Codex.**

## Objectif et choix

Le blocage M3-C était un deadlock potentiel :
- Le récepteur exige un FIN TCP avant la confirmation d'un corps strictement cadré.
- Un client HTTP classique peut attendre la réponse avant de fermer.

**Choix de laboratoire M3-D :** après avoir transmis exactement le corps
authentifié, le **client dédié ferme uniquement son canal d'écriture**
via `shutdown(SHUT_WR)`. Le canal de lecture reste ouvert pour obtenir
une réponse HTTP ordinaire. Le serveur lit jusqu'au FIN, refuse les
octets supplémentaires et ne répond qu'ensuite. Ce contrat exige
**un client LINK spécifique**, non un client HTTP générique non qualifié.

Le client classique qui attend la réponse sans half-close reçoit un
**408 après timeout borné** dans ce labo. Ce choix n'est pas une API
compatible avec les navigateurs ou `urllib` par défaut.

## Implémentation réellement exécutée

`experiments/link_m3d_socket_lab/single_owner_loopback.cpp` fournit
un serveur POSIX **strictement 127.0.0.1 et port dynamique**, avec
**un seul socket d'écoute**, une file d'attente système et des connexions
traitées en série. Il emploie réellement OpenSSL, le **véritable
`M3CAuthenticatedIngress.h` de M3-C**, et le ledger CAS de labo.

- La première ligne HTTP est plafonnée à 128 octets et lue octet par octet
  (sans lecture du corps).
- La lecture des headers M3 passe octet par octet au Gate avec HMAC
  vérifié **avant tout octet de corps**. Aucune mémoire de corps pré-allouée
  par `ESP8266WebServer::server.on`.
- Après authentification, chaque octet de corps est transmis au Gate ;
  le SHA256 réel, la syntaxe canonique et l'identité sont contrôlés.
- Après Content-Length, tout octet supplémentaire avant FIN est rejeté.
  Le serveur attend FIN avec une échéance absolue, puis seulement
  `finishAfterExactFraming(true,0,...)`.
- Le ledger en mémoire refuse la même transaction ou une révision périmée
  dans **le même processus sériel**.
- Le retour de validation est **HTTP 202** avec
  `{"lab":"CRYPTO_VERIFIED_BUT_NOT_APPLIED","applied":false}`.
  Il n'y a **aucune commande LCD, aucun ACK firmware, aucun GET status**.
- Refus avec 403/408/404 selon cas. Un test du *vrai réseau loopback*
  garantit que l'absence de half-close n'entraîne pas d'attente infinie.

**Avertissement majeur : la parité héritée n'est PAS implémentée.**
Ce serveur renvoie volontairement **503
`LEGACY_PARITY_NOT_IMPLEMENTED`** pour les routes GET status,
resources, metrics et POST metrics qui ont été inspectées dans
`M9NormalStageA.cpp`. Ainsi le laboratoire prouve seulement
la **non-confusion de routes et le refus sans effets de bord** :
il ne prétend pas préserver le dashboard, les télémétries, l'OTA,
la météo ou le LINK dans une image native.
Le port 80 du SmallTV ne change **absolument pas**.

Les 12 échanges réels de `test_loopback_contract.py` utilisent une
connexion TCP POSIX par scénario et testent : demi-fermeture réussie,
timeout HTTP classique sans FIN, replay, transaction suivante,
MAC erroné avec zéro corps, intégrité altérée, octets supplémentaires,
FIN prématuré, Content-Length dupliqué, anciennes routes
métriques/status explicitement NON IMPLÉMENTÉES, chemin fermé et
fragmentation côté émetteur.

**Seule adresse réellement contactée en CI : 127.0.0.1, sur le runner.**
`192.168.1.46` est un identifiant virtuel dans les champs HMAC des
fixtures, jamais une destination réseau. Aucun SmallTV ni Wi-Fi domestique.

## Limites à ne pas masquer

- C++ POSIX sur Linux HOST **n'est pas** `WiFiClient` ni lwIP.
- Le composant ESP8266 Xtensa/BearSSL de M3-C a déjà été compilé
  comme *application inerte*, mais **ce nouveau serveur POSIX M3-D**
  ne peut pas être compilé tel quel pour Xtensa : il inclut
  `poll`, `sys/socket`, `unistd`. Un adaptateur WiFiClient
  au véritable unique port 80 reste absent.
- Le listener sériel peut bloquer les métriques pendant les délais
  d'une commande : deadline appliquée au HOST seulement, charge mixte,
  CPU, WDT, heap, lwIP, temporisation de connexion et mécanisme
  de priorité télémétrie **NON QUALIFIÉS**.
- Les clés utilisées sont **publiques et destinées aux tests seulement** ;
  pas de provisioning, de rotation, ni révocation.
- L'unicité du boot/token après reboot, le contrôle des sessions et
  le CAS **atomique concurrent** ne sont pas prouvés.
- Les réponses 202 de laboratoire **ne sont jamais une preuve de
  changement de mode ou d'affichage**, ni une autorisation OTA.
- Les routes historiques Digest authentifiées devront être reprises
  **bit pour bit au comportement requis** dans un seul propriétaire
  de socket, et le routeur devra préserver les protections OTA et
  les limites applicables aux anciennes routes.
- Le vrai statut (GET confirmation, scène rendue et retour LCD) n'est
  pas implémenté ; M3-A reste l'exigence de confirmation indépendante.

## Matrice de portes

| Porte | Résultat |
| --- | --- |
| M3-C HMAC/SHA256 exact, aucun corps avant auth | À confirmer CI M3-D |
| Vrais sockets loopback et half-close client | À confirmer CI M3-D |
| Absence de FIN / octets supplémentaires / timeout | À confirmer CI M3-D |
| Sémantique du seul listener host et route fermée | À confirmer CI M3-D |
| Parité routes B5.3/M9NormalStageA | **HOLD — renvoient 503 dans labo** |
| Un vrai propriétaire port 80 ESP8266 sans second serveur | **HOLD** |
| `WiFiClient`/SDK/lwIP, heap/stack/scheduler/WDT | **HOLD** |
| Protocole LINK Windows production / clés secrètes | **NON IMPLÉMENTÉ** |
| Boot/replay inter-redémarrage/ACK natif/LCD | **HOLD** |
| Flash/OTA/LittleFS/SmallTV installé | **NON TOUCHÉS** |

**Prochaine étape conseillée :** M3-E, conception d'un propriétaire natif
du port 80 avec **parité des routes héritées et équité des métriques**,
puis qualification sur la vraie build B5.3/B5.4 en image de test et
budgets mémoire ; ne jamais activer le contrôle sans autorisation
explicite et identité du candidat.
