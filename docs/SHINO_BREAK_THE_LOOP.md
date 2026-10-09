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

Les deux images privées ont été construites depuis le commit propre
`4e51a9fd3c886ec90974cd9cc28da0b38af49ce7`, puis revérifiées indépendamment avec
l'installateur hors ligne, les checksums/CRC et les symboles de leur ELF :

| Image | Octets | SHA-256 exact |
| --- | ---: | --- |
| A, installation initiale UART | 407008 | `faee8f927ca468978f5ec4bd133e899b6898bfc6c01e1afe471f392026e70a6b` |
| B, unique OTA depuis A | 407008 | `78fdfbeb2b0b71c2649bcd2033d7d2b3eb8cb19a9cc30b393ad4b75e89336bea` |

Chaque image : **42196 octets de RAM statique, dont56 noinit ; 402851 octets de
flash liée**. Par rapport au rapport de l'image installée : +136 statiques,
−4208 BIN, −4220 flash liée, noinit inchangé. C'est une comparaison de builds,
pas une mesure native simultanée. Le build public précédent donnait406880/42112.
Les cadres Xtensa privés propres au contrôle HTTP/upload sont64/128 octets,
HMAC720, begin128, staging416, segments352, finish144, identité912, parser224,
loop48, handleClient64. Crypto précompilée/SDK/IRQ/libc et high-water simultané
restent inconnus. Les seuils sont contrôlés en fonctionnement et ne sont pas
abaissés pour obtenir une installation.

Paquet local ignoré : `research-local/m9-owner/http-ota-20261010-ab/`.
`QUALIFY-A.cmd`, `UPDATE-B.cmd`, `QUALIFY-B.cmd` enregistrent des résultats locaux
neufs. `uart-commands.json` prépare PRE/POST4MiB et une copie du writer existant
liée uniquement à A : un Begin, **100 DATA uniques**, un Finish sans reboot,
un MD5. Étendue UART `[0,0x64000)`, staging de B `[0x19C000,0x200000)`.
Le mode AUDIT réel de cette copie a passé sans ouverture de port ; deux tests
avec image publique inerte vérifient la séquence et103 points d'échec terminaux.
Le writer historique et le BIN installé restent inchangés. Aucun fichier du
dossier `SHINO-TV-BACKUP` n'a été lu, écrit ou partagé dans cette livraison.

La CI du HEAD final est demandée sur la même Draft PR42 ; son état est à lire
sur GitHub, sans reprendre les PASS des anciens commits. Les ajouts ultérieurs
au commit de construction concernent le paquet UART, ses tests, les quatre pins
des nouveaux fichiers Windows dans les contrôles historiques et ce reçu ;
aucun source firmware de A/B n'est modifié.

Limites conservées : aucun rollback automatique, panne possible pendant copie
eboot ; pas de preuve radio/LCD/heap natif à ce stade ; appareil installé et
backups privés inchangés. A et B gardent l'AP et les identifiants existants,
LittleFS read-only et les quatre valeurs ; les fonctions média/LAN non actives
du StageA ne sont pas présentées comme restaurées.

Prochaine action : **accord explicite pour les hashes exacts A/B**, puis
explicite installer A via COM8, vérifier les lectures répétées et LINK, effectuer
une unique OTA A→B, vérifier SHA réel/build/boot distinct/FS/mesures/récepteur OTA.
Arrêt sur reset, corruption, seuil mémoire, incohérence ou résultat inconnu.
Pas de fermeture définitive ni merge avant cette démonstration.
