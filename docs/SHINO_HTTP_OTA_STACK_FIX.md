# SHINO // TV — correction stack du 10 octobre 2026

Reprise du [dossier officiel du matin](SHINO_2026-10-10_MORNING_HANDOFF.md),
sur `feature/shino-tv-m9-flash-layout-liberation`, Draft PR42.
**A fonctionne sur le SmallTV selon les preuves propriétaire ; qualification
HOLD, stack1632 <2048. Cette correction n'a pas été installée.** Aucun contact
SmallTV, COM8, flash, OTA ou reboot dans ce travail. B original reste NOT_RUN.

## Ce qui est démontré

Core3.1.2 `ESP.getFreeContStack()` scanne les mots de garde de la continuation
4096 octets : c'est le minimum historique libre depuis le dernier repaint,
pas le SP instantané. L'observateur ne repeint pas dans `poll()` après setup.
Les 1632 restent donc sous le seuil dans le runtime A courant, même après
l'arrêt de LINK. Les contrôles Windows et firmware refusent l'OTA. Aucun seuil
ni repaint n'a été modifié pour faire disparaître cet échec.

Les `.su` du compilateur et le désassemblage de l'ELF de A démontrent le coût
des buffers locaux JSON et HMAC. Ils ne permettent pas d'attribuer le premier
pic physique1632 à un GET précis : **ce chemin historique reste inconnu**.
Le HMAC n'est pas appelé par ces GET ; son coût ne constitue pas l'explication
de cette observation propriétaire.

| Frame Xtensa, octets | A installé | Correction |
| --- | ---: | ---: |
| identity, buffer local768 | 912 | 160 |
| metrics, buffer local768 | 880 | 112 |
| proof HMAC | 720 | 128 |
| Transfer.begin / upload | 128 /128 | 128 /128 |
| stagedImage / segments / finish | 416 /352 /144 | 416 /352 /144 |
| Core end(false) | 192 | 192 |

Le chemin HMAC SHA256 résolu par source/vtable et code machine cumule :
loop_wrapper16 + loop48 + handleClient64 + parser224 + beforeBody64 + upload128
+ Transfer.begin128 + proof720 + br_hmac_key_init304 + process_key304
+ br_sha224_update48 + br_sha2small_round384 = **2432 octets** sur l'ancien A.
Les trampolines fonctionnels sont des tailcalls sans frame supplémentaire.
La ronde SHA écrit dès la base de sa frame. Ce chemin valide d'admission est
déjà incompatible avec la réserve2048, même après un nouveau boot de l'ancien A,
et le contrôle après HMAC/Updater.begin refuserait avant toute écriture flash.
Avec la correction : **1840 octets**, gain592. C'est un chemin compilé connu,
pas une borne exhaustive SDK/IRQ/libc, ni une mesure native.

`getSketchSize()` a une frame48 et cache sa taille ; ce n'est pas une preuve
d'un gros buffer dans identity. BearSSL conserve ses propres frames304/304/384
et hmac_out320, sha2small_out128. Le staging relit par blocs128 avec hash/CRC,
puis valide les segments ; le contrôle frais précède le seul `end(false)`.
Le profil n'installe ni vérificateur RSA global ni MD5 cible dans cet Updater.
`end(false)` conserve sa frame192 ; les pics SDK/flash natifs restent à mesurer.

## Correction bornée

Un buffer JSON statique768 partagé par les deux handlers remplace leurs deux
buffers locaux. Un lease conserve sa propriété jusqu'au retour de send, y
compris pendant un yield ; un accès réentrant retourne503 avant mutation.
Les tailles de réponse et contrats HTTP restent identiques.

Les contextes HMAC appartiennent au Transfer déjà construit dans le stockage
statique. Le lease HMAC refuse aussi un accès réentrant. Les champs signés sont
streamés dans le même ordre et avec les mêmes séparateurs ; le message local240
et les appels printf de proof/tag disparaissent. Aucun nouvel allocator,
transport, endpoint ou protocole ; Core garde le buffer4096 et l'abandon sans
commit. Le builder impose des caps pour les neuf frames du tableau à chaque
compilation, en plus du linker4m2m et noinit56.

Build public inerte corrigé : **407312 octets BIN, RAM statique43336,
flash liée403167, noinit56**. Contre le build public original406880/42112/402735 :
+432 BIN, **+1224 RAM statique**, +432 flash liée. Ce coût fixe remplace de la
stack ; la marge heap native simultanée n'est pas déduite des chiffres de build.
Les futurs BIN privés restent dans un nouveau paquet local ignoré, construit
depuis le source commité propre ; les originaux ne sont pas remplacés.

`shino_qualify.py` conserve le mode PRINT_ONLY et les trois GET Digest bornés.
Un échec donne cycle, route, code HTTP/timeout/JSON/identité ou valeurs/seuils.
Le cas propriétaire donne `RESOURCE_FLOOR_FAILED`, `stack observed1632,
minimum2048`, dès le premier cycle. Le reçu conserve le diagnostic, le code
processus est2 et les nouveaux lanceurs CMD le conservent après pause.
Aucun texte d'exception, body, header, URL privée ou secret n'est divulgué.

## Vérification effectivement exécutée hors ligne

- Firmware public compilé avec Core3.1.2, platform4.2.1, GCC10.3.0 ; neuf caps
  passent. Un retour expérimental de identity à912 est rejeté par le builder.
- 227 cas natifs avec le vrai Core/BearSSL et flash/RTC en RAM, dont197
  interruptions ; HMAC Windows exact à six tailles, propriété du workspace,
  rejet stack1632 et seuil franchi après HMAC, aucun commit sur échec.
- 25 tests qualificateur/updater Windows ; diagnostics, reçu, consentement,
  boot/identité exacts et absence de fuite de secrets.
- 47 régressions LINK/Digest (28 LINK +19 sender) ; deux tests du writer sur
  image publique inerte, aucun objet série.
- Banc loopback : 150 POST/GET authentifiés avec le vrai Normal.cpp/parser/
  Digest/Updater, deux refus de scratch réentrant sans corruption, TTL et
  récupération après transferts rejetés, un staging/reboot simulé.
- 113 sources firmware historiques, 68 pins Core signés +8 pins StageA
  inchangés ; seuls les deux nouveaux blobs Windows corrigés sont repinnés.
- Les182 BIN/ELF/identifiants/manifests/reçus privés inventoriés avant travail
  ont tous conservé leur hash. A/B et les PRE/POST4MiB originaux sont préservés.

Les ressources60k/50k/stack3248 du banc sont **MOCKED**. Le natif simultané,
radio/LCD/watchdog et une OTA physique réussie ne sont pas prouvés. La CI doit
être lue au HEAD exact sur PR42 ; aucune CI ne vaut autorisation physique.

## Une prochaine manipulation proposée

Le A courant est fermé par le high-water, et son ancien HMAC excède la réserve
même sur un boot neuf. Une mise à jour du PC ne corrige pas le code installé.
La seule manipulation proposée est donc **une installation UART unique d'un
nouveau A corrigé**, avec son hash exact, PRE/POST neufs, readback et qualification
du nouveau boot avec LINK. Elle exige un nouvel accord propriétaire. Aucune
commande n'est lancée et aucune OTA B n'est incluse dans cet accord proposé.
L'OTA B et la fermeture du boîtier restent HOLD jusqu'aux preuves natives.
Pas de rollback automatique ; la copie eboot reste sensible à une coupure.

Sources primaires : [continuation Core3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/cont_util.cpp),
[Updater Core3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp).
