# SHINO // LINK — M3-P : protéger la première ligne HTTP avant la commande

**19 octobre 2026 — journal propriétaire (développement hors appareil uniquement).**
On travaille sur **SHINO // LINK → SmallTV**, pas sur la Freebox,
ni sur Codex B5.4. Base constatée : PR #79 M3-O Draft au HEAD
`6bdaeb47f118164130d605d3ad9b27f2b02fd8b0` :
**16/18 workflows PASS au fork**, `SHINO normal HTTP OTA`
et `Offline audit and simulator tests` encore *in_progress*.

## Pourquoi

M3-O a réellement compilé le mécanisme de transfert d'une
connexion `CLIENT_IS_GIVEN`, ce qui pourrait **garder
le serveur B5.3** et toute la télémétrie/Digest anciens.
Mais son cœur ESP8266 3.1.2 fait d'abord
`String req = client.readStringUntil('\r')` :
un client peut lui envoyer une ligne excessivement
longue AVANT toute protection, en consommant de la RAM.

**M3-P tente de supprimer cette allocation non bornée dans une
copie temporaire de la bibliothèque, jamais dans le framework
installé ou le firmware du propriétaire.**

## Modifications effectives, chemins exacts dans GitHub

- `experiments/link_m3p_parser/M3PBoundedLine.h` :
  lecture octet par octet et limites **256 caractères ASCII
  imprimables** et **2000 ms absolues** depuis le début ;
  exige CRLF exact, refuse LF isolé, NUL, caractères de
  contrôle et ligne trop longue sans parcourir le reste ;
  aucune lecture d'en-tête ou de corps.
- `patch_core_parser.py` : vérifie les SHA-256 exacts des
  trois fichiers du Core 3.1.2 conformément à
  `firmware/scripts/m9_normal_webserver.py`, réutilise
  son approche de copie isolée, puis modifie UNIQUEMENT
  `Parsing-impl.h` dans un dossier généré
  `.pio/m3p-venv/ESP8266WebServer/`. Il remplace la
  lecture non bornée de la première ligne et le rejet
  du terminateur LF original ; il impose aussi la ligne
  brute exacte `POST /api/v1/display/mode HTTP/1.1`
  **avant le hook**, notamment face aux variantes de
  version/méthode, ou à une query-string.
- `use_pinned_overlay.py` : prépare cette copie pour
  **un seul** environnement PlatformIO `bounded_core_inert`,
  interdit explicitement les commandes d'upload, de
  programmation, de suppression et de construction FS ;
  le Core partagé de PlatformIO reste intact.
- `test_bounded_line.cpp` : teste la vraie fonction C++
  avec flux fragmenté, 256/257 caractères, fins de
  lignes, lenteur, déconnexion, restes d'en-têtes
  et dépassement de compteur millisecondes.
  **Simulation HOST**, pas de vrai SmallTV.
- `src/main.cpp` : vrai `ESP8266WebServer(80)` et
  M3-O (`WiFiClient`) compilés pour ESP8266 réel ;
  la sonde est sous un booléen volatile toujours faux.
  **Aucun `.begin()`**, aucun écouteur Wi-Fi actif.
- Le workflow compare le serveur Core 3.1.2 **original**
  à la variante patchée en deux ELF/BIN **inertes**.
  Il calcule les octets BIN, les sections RAM statiques,
  les SHA du laboratoire et les annotations de pile.
  Un symbole obligatoire dans l'ELF prouve que
  **le parseur modifié est réellement lié**, pas seulement
  que le nouveau fichier existe.

## Ce que M3-P ne démontre PAS

- Un header HTTP historique très long reste lu par le
  parseur Core **après** le hook. M3-P ne borne que la
  **première ligne** ; les anciennes routes ne sont donc
  pas entièrement protégées. Le chemin HMAC M3 devra
  lire ses propres en-têtes bornés.
- La reprise `CLIENT_IS_GIVEN` n'a pas été exercée par
  un vrai `WiFiClient` connecté à un routeur/SmallTV.
  Les pièges de latence, fermeture TCP, concurrence,
  mémoire réelle, WDT et fragmentation restent non vérifiés.
- Aucun HMAC complet n'est vérifié dans ce jalon,
  aucun changement réel de mode, aucune confirmation LCD,
  aucun déploiement/OTA ou candidat BIN produit.
  M3-O demeure *deny-only*.
- Les chemins POST/OEM/OTA, la récupération Wi-Fi, les
  pages de diagnostic et les médias restent entièrement
  aux sources du firmware historique ; ce test n'est pas
  la preuve que la future compilation du produit complet
  en conservera la parité.
- La CONT physique communiquée lors du préflight B5.3 :
  **2128 octets minimum rapporté** pour **2048** de seuil,
  soit **80 octets de marge seulement**. Une frame locale
  compilateur n'est pas une mesure physique de CONT.

## Règle d'acceptation

**PASS laboratoire limité** seulement si :
1. tests HOST et pins source PASS ;
2. deux ELF ESP8266 réels compilés, et **la copie source
   patchée est effectivement présente au linkage** ;
3. tailles et SHA dérivés des octets de la CI finale ;
4. les précédentes routes B5.3 sont restées intactes.

**M3 en production et OTA physique : HOLD**, y compris si
tous les tests sont verts.

## Reçu et observations

Conserver sur cette PR :
- SHA HEAD final et CI correspondant ;
- premier échec de compilation/test, cause et correction ;
- delta BIN, BSS, pile codegen s'il est mesurable ;
- LIMITES connues et prochaine action d'ingénierie.

**Aucun fichier `firmware/`, `companion/`, aucun
service Windows installé, matériel SmallTV, Freebox,
secret, branche Codex ni reçu/backup propriétaire n'est
modifié.** Pas de merge.
