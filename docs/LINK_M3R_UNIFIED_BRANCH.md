# SHINO // LINK — M3-R, branche unique de consolidation (19 octobre 2026)

## Jalon de vérité physique — issue #81 (à lire avant le reste)

**POSTBOOT_IDENTITY_B54_CONFIRMED**, observé par Codex local le 19 octobre :
[rapport authentifié](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6275185762).
Le firmware réellement exécuté est **P0+Updater512+B5.4 privé** (431 920 o),
confirmé après reboot par GET Digest 401→200 et correspondance complète
aux BIN/manifeste/reçu privés. Le propriétaire a également observé
quatre cartes de mesures, date et heure. Le GET indiquait
`fs_ok=true`, `metrics_fresh=true`, `ota_enabled=true`, `last_update=NONE`,
heap 28 168, bloc 26 080, CONT 2 180 octets et fragmentation 8 %.
**L'identité de B5.4 est confirmée par le rapport physique, pas par la CI M3-R.**
Le délai de lecture postboot précédent et `STOP_UNKNOWN_NO_RETRY` restent
dans l'historique ; aucune réservation/attempt n'est effacée.

**Chantier unifié :** poursuivre les sources et tests HOST uniquement sur
PR #85. Les PR #72/#73/#76 constituent le graphe public B5.4/rendu/modes
à rapprocher **sans les merger** ; les artefacts privés sont distincts.
La CI du code M3-R au HEAD `feb8443fc095c9198228a056eb96361e03c9ccc2`
comportait **47 SUCCESS, 24 SKIPPED, 0 FAILURE** lors de la relecture.
Ce bilan est limité au SHA cité ; requalifier tout HEAD documentaire ultérieur.
Voir le [plan de réunification](SHINO_TV_LINK_UNIFICATION.md).


## Décision propriétaire / méthode

« Combine tout ça avec ce que tu faisais avant. Une seule branche en direction de M3-R. »

Nouvelle branche GitHub isolée :
`feature/link-m3r-unified-integration-20261019`.
Elle part de PR #82 (M3-Q, HEAD vérifié initial
`7adb17e37c580f7e37d27d6cb02e79dc1ea7045c`), donc contient
l'ascendance expérimentale M3-A…Q. Elle réintègre au niveau **des Git blobs
identiques**, sans merge, les 12 chemins de PR #84 (issue #83,
HEAD initial `47044b61107f55f7bf4c21d7fa947d6d46b75006`).

L'ancêtre commun des deux chaînes est M2 #54 :
`88f2163c512429e804e96aabbc8b60b71602936b`.
Le commit de recopie `b318c01dc7f223110cbf763f34ce96f6d0ccf30c`
préserve les octets des 12 fichiers source, UI, tests, CI, documentation et
guards ; il ne fusionne PAS #82/#84, ne clôt aucune PR et ne synchronise
ni la copie Windows locale ni le firmware installé. Les autres PR Draft sont
des dépendances historiques, **pas des branches à continuer en parallèle**.
Le chantier M3-R utilise seulement cette nouvelle branche.

## Périmètres rassemblés

**Windows (M2 + #83) :** quatre choix du menu (AUTO,
Horloge/Météo, Monitoring PC, Musique) demeurent aperçu HOST.
Une action manuelle distincte « Vérifier le firmware du SmallTV… » lit
`GET /api/v1/update/status` par Digest depuis l'adresse déjà configurée,
avec verrou interprocessus, sans retry, réponse bornée et affichage expurgé.
Le nom de version n'apparaît que si un véritable BIN/manifeste du catalogue
privé vérifié correspondent à l'identité lue ; sinon « Version inconnue ».
**Ce n'est PAS un bouton OTA et pas une commande M3 de mode.**

**Firmware expérimental (M3-A…Q) :** contrat mode HMAC pré-body
M3-C, réutilisation unique du serveur Core via M3-O, ligne de requête
strictement bornée par M3-P, garde M3-Q pour en-têtes limitée mais
**non authentifiante**. Ces éléments restent séparés du vrai firmware.
Tout test de linker Xtensa est INERTE, aucune preuve de boot/CONT.

## Premier jalon M3-R : UN parseur authentifiant pour les nouveaux modes

`experiments/link_m3r_single_parser/M3RSingleParser.h` démontre
un chemin HOST de lecture après M3-O/M3-P :

1. **Précondition à prouver sur le Core épinglé en intégration finale** :
   M3-P a lu strictement la première ligne exacte
   `POST /api/v1/display/mode HTTP/1.1\r\n`, et M3-O cède le
   socket avant les en-têtes.
2. L'adaptateur réintroduit cette ligne exacte dans **l'unique**
   `ShinoM3C::Gate` existant, avant de recevoir un seul octet de réseau.
3. Chaque octet d'en-tête arrive directement dans
   `Gate::headerByte` : authentification réelle HMAC-SHA256 par
   le profil M3-C, limite 960 octets réseau, deadline 1 seconde,
   aucun buffer `HeaderGuard` M3-Q supplémentaire.
4. **Zéro octet de corps consommé avant `AuthenticatedHeader`.**
   `bodyByte` et `finishAfterExactFraming` sont exercés sur un
   client HOST simulé : SHA du corps, entrée canonique, FIN et
   absence d'octets résiduels. **Aucun writer d'écran / ACK M3 appliqué.**
5. La compilation Xtensa doit utiliser le Core ESP8266 3.1.2 cloné,
   M3-P appliqué dans le clone et BearSSL réel, toujours sans listener
   actif, et publier uniquement les mesures du BIN inerte.

**Crucial :** le vieux code M3-Q reste comme preuve comparative, mais
n'est ni instancié ni lié dans la nouvelle voie M3-R.
Il faut encore prouver la liaison effective du slot Core M3-O à ce
parseur, la récupération du démarrage de deadline et du `WiFiClient`
réel, puis les transports fractionnés, concurrence, fermeture/timeout,
reconnexion, révision anti-rejeu et budget mémoire des laboratoires B5.3,
puis leur parité dans le vrai graphe source B5.4, avant toute action matérielle.

## HOLD / sécurité

- Aucun flash, OTA, UART, LittleFS, Wi-Fi, reboot, changement de
  firmware B5.4 effectivement installé, installation du SHINO LINK Windows ni publication VM.
- Le verrou Digest du menu Windows et le vrai marqueur `.attempt`
  du client OTA #81 ne sont PAS encore tous deux rattachés à une
  même source d'état prouvée. Le menu #83 est **HOLD pour installation**.
- La mémoire B5.4 postboot est uniquement une mesure ponctuelle rapportée
  dans #81. L'identité B5.4 a été confirmée **physiquement par Codex**,
  et **PAS** par la CI de cette branche. La marge mémoire du futur M3-R
  intégré reste NON VÉRIFIÉE.
- La parité legacy B5.3 Digest, télémétrie, clock, OTA et LCD sur vrai
  SmallTV reste à démontrer ; pas de claim de boot ni d'activation M3.
- Aucun vieux GO physique ne s'applique au nouveau code.

## Tests / suite unique

La CI #84 précédente avait 18 SUCCESS / 24 SKIPPED sur le HEAD de son
chantier PC. Le HEAD M3-Q avait 35 SUCCESS / 31 SKIPPED.
**Ces résultats ne qualifient PAS automatiquement le HEAD consolidé.**
Relire les CI exactes de la nouvelle PR avant toute mention de PASS.

Prochaine étape technique **unique** : sur cette branche M3-R, prouver
la connexion M3-O/M3-P → M3-C Gate unique dans le même graphe
ESP8266 inert que les véritables handlers legacy, tout en mesurant
`.text`, `.bss`, heap estimée/stack statique et en refusant un
dépassement sans affaiblir de seuil. Ensuite seulement la coordination
Windows/OTA et une revue du GO matériel éventuel.
