# B5.4 / M3-R — incrément 4 natif inerte, 20 octobre 2026

## État et périmètre

Qualification de compilation/édition de liens Xtensa uniquement, depuis
`83a21d0f8f767e0d6d388c8a539a32add5fa6461`, branche #85 réservée et propre au
départ. Le résultat final dépend de la CI du nouveau SHA, consignée dans #85.
Le firmware installé et les travaux sources privés restent intacts.

Le [laboratoire natif](../experiments/link_m3r_b54_native_inert/README.md)
réutilise le graphe public #72 `91969aceb45e0c43d44f93a702a3997b57e8f89e`,
son inventaire fermé et l'overlay exact de l'incrément 3. Aucun import du
firmware privé, aucun patch M3-P du Core brut. Les headers de liaison INERT
ont des clés synthétiques ; le refus 503 M3-R reste intégral. Entrées
`setup/loop` vides vérifiées dans le désassemblage. Le BIN est rendu non
amorçable automatiquement, aucun candidat installable n'est livré.

## Mesures natives Windows — vrais fichiers produits

| Mesure (octets) | StageA B5.4 inerte | Avec handoff M3-R inerte | Delta |
| --- | ---: | ---: | ---: |
| BIN avant invalidation du premier octet (taille conservée) | 429616 | 435728 | +6112 |
| `.irom0.text` | 380904 | 386356 | +5452 |
| RAM statique, `.noinit` inclus | 47808 | 49924 | +2116 |
| IRAM `.text` + `.text1` | 27751 | 27787 | +36 |
| Capacité DRAM non occupée statiquement | 34112 | 31996 | -2116 |

La dernière ligne n'est **pas** du heap disponible mesuré : allocations
dynamiques, SDK, Wi-Fi et pile restent à soustraire/mesurer. La Gate native
statique est de 1448 o ; elle n'est pas une allocation de pile de cette taille.
IRAM sous 32768 o, flash de code sous 1044464 o ; aucune limite relevée.
RAM native complète : `.data`, `.rodata`, `.bss`, `.noinit` ; le résumé
PlatformIO exclut 56 o de `.noinit` (49868 o au lieu de 49924 o).

Frames GCC Xtensa réelles : `loop` 80, `serviceRequest` 32, `handleClient` 64,
`_parseRequest` 224, `beforeBody` 64, `upload` 128 o, identiques avant/après.
Nouveau chemin : `m3Service` 64, `readAuthenticatedHeaders` 48,
`Gate::authenticateHeader` 704, `verifyFrameWithoutSideEffect` 352 o.
Le sous-chemin connu loop→service→headers→auth totalise 896 o ; ce total
partiel exclut callees crypto/Core, callbacks, interruptions et overhead ABI.
Il **ne prouve ni le pire cas de pile, ni CONT restant ≥2048**, ni WDT.
Les `.su` de bibliothèques archivées mais non liées ne sont pas des chemins
actifs : Updater512 est identifié dans l'ELF, Updater stock absent.

4m2m réel : flash 0x400000, FS [0x200000,0x3FA000), EEPROM 0x3FB000,
RFcal 0x3FC000, SDK [0x3FD000,0x400000). Image handoff arrondie à 438272 o
(107 secteurs) ; staging théorique pour image de même taille commence
à 1658880 (0x195000), bien après l'application. C'est une vérification
géométrique : **aucune validation/installation OTA d'un BIN inerte**.
Seuils runtime préservés : heap 20480, bloc 16384, CONT 2048 o, frag 25 %.

## Validations et limites

- Deux builds natifs complets : PASS ; Core 3.1.2 réel, StageA, Digest,
  LINK/horloge/météo signée, HMAC BearSSL, Updater512 et eboot liés.
- Huit tests de gardes INERT : PASS (deux profils, mauvaise cible,
  altération/absence d'entrée, uploader refusé, postaction et header invalide).
- Mesures ELF/BIN, entrée vide, une Gate/un `httpBusy`, frontières : PASS.
- Régressions runtime : preuve HOST déjà acquise à 83a21d0, **réutilisée**
  (32 tests + 4 intégrité, CI exacte 39461908041) ; aucune nouvelle exécution
  native HTTP, Digest, OTA, HMAC ou interruption n'est revendiquée.
- Heap/bloc/fragmentation/CONT/WDT physiques : NON VÉRIFIÉ, HOLD matériel.
- Deux préparations conservées : erreur de liste d'environnements, puis
  assertion pool JSON 8 et sélection du header Updater corrigées dans le
  builder de laboratoire. Aucune garde applicative n'a été désactivée.

## Blocages, risques et prochaine action

Le surcoût statique de 2116 o doit être pris en compte avant tout chemin
productif. La qualification native inerte ne règle ni l'activation de mode,
ni la marge dynamique réelle, ni l'identité d'une future release privée.
La météo automatique existante n'a été ni rediagnostiquée ni contactée.

Prochaine action unique : revue propriétaire des ressources et limites de
cet incrément avant de décider du raccordement fonctionnel suivant.
Aucun contact matériel/VM, flash, OTA, reboot, commande écran ou déploiement.
