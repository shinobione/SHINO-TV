# SHINO // TV — Operation Break the Loop, 10 octobre 2026

Livraison : [firmware et updater uniques](../ota/README.md), même branche et
Draft PR42. **Preuves hors ligne ; aucune opération appareil exécutée.**

Le 404 `STAGE_A_PREBODY` du BIN installé `9de1ffe3…b9764d` reste une observation
propriétaire, **cause racine non établie**. L'allowlist générée inclut les routes,
et les replays précédents ne reproduisent pas le défaut matériel. Ni les
temporaires String, ni une corruption heap, ni un problème Digest/ABI ne peuvent
être présentés comme diagnostic confirmé. Le nouveau firmware remplace cette
politique générée et les durées de vie dynamiques par un routage direct avant
authentification, une seule instance HTTP et un header imposé à tous les C++.
Cela contourne le mécanisme suspect ; ce n'est pas la preuve de sa cause.

| Mécanisme | Décision et implementation livrée |
| --- | --- |
| Digest + HMAC maintenance | SIMPLIFIER : Digest normal conservé pour LINK/GET ; HMAC seul sur l'upload, liant le hash et le nonce. |
| challenge/ARM/PROBE/INSTALL | SUPPRIMER du nouveau firmware : sélection et confirmation de l'image sur Windows, un POST authentifié. |
| HTTP détruit/reconstruit | REMPLACER par un serveur persistant ; aucune invalidation des handlers ni bascule d'objet. |
| TCP propriétaire 8266 | SUPPRIMER ; transfert HTTP port80. |
| Core Updater/eboot | CONSERVER : code de programmation natif et tampon4096 ; seul ajout inline d'abandon sans commit. |
| Qualification cumulative | SIMPLIFIER : tests automatiques puis une séquence physique A stable → OTA B → boot/mesures/FS. |
| Multiples builds/scripts opérateur | SIMPLIFIER : un builder, un paquet A/B, un updater Windows ; archives inchangées. |

ArduinoOTA demanderait une invitation UDP et une connexion retour vers Windows ;
HTTPUpdateServer stock ajoute multipart et U_FS, sans l'identité exacte souhaitée ;
ESPhttpUpdate implique un serveur PC et un téléchargement initié par l'appareil.
La voie retenue conserve leur substrat **Updater/eboot**, mais un petit callback
avant body fournit l'upload borné application-only et l'authentification de la
release. Voir les sources Core3.1.2 dans le README ; pas de nouveau bootloader.

Tests locaux déjà exécutés : 218 cas avec vrai Core en RAM, dont197 interruptions
jusqu'après réception complète (aucun boot command sur échec, FS/tail protégés) ;
11 tests Windows incluant consentement exact, rejet du mauvais BIN et confirmation
du nouveau boot ; 150 requêtes POST/GET authentifiées sur sockets PC avec le
**vrai nouveau Normal.cpp, parser, Digest et Updater**, suivies d'un upload avec
staging et reboot simulés. 47 régressions LINK/Digest conservées passent.
Le graphe réseau récupère aussi après une déconnexion partielle, une image
complète dont le hash est incorrect et un framing Transfer-Encoding interdit.
Les métriques heap/stack des mocks ne sont jamais des mesures appareil.

Le build public complet a montré 406880 octets / 42112 octets de RAM statique /
56 octets noinit. Les cadres Xtensa propres au contrôle HTTP/upload sont64/128
octets, HMAC720, begin128, staging416, segments352, finish144, parser224, loop48,
handleClient64. Ce sont des cadres compilateur ; crypto précompilée/SDK/IRQ/libc
et high-water simultané restent inconnus. Les données finales privées et la CI
du commit exact seront ajoutées après construction du paquet.

Limites conservées : aucun rollback automatique, panne possible pendant copie
eboot ; pas de preuve radio/LCD/heap natif à ce stade ; appareil installé et
backups privés inchangés. A et B gardent l'AP et les identifiants existants,
LittleFS read-only et les quatre valeurs ; les fonctions média/LAN non actives
du StageA ne sont pas présentées comme restaurées.

Prochaine action : **soumettre les hashes exacts A/B**, puis seulement avec accord
explicite installer A via COM8, vérifier les lectures répétées et LINK, effectuer
une unique OTA A→B, vérifier SHA réel/build/boot distinct/FS/mesures/récepteur OTA.
Arrêt sur reset, corruption, seuil mémoire, incohérence ou résultat inconnu.
Pas de fermeture définitive ni merge avant cette démonstration.
