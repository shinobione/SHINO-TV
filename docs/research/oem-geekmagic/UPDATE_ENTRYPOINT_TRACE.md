# Piste OTA OEM `/update` — recherche de point d'entrée (16 octobre 2026)

**Statut : PARTIAL / HOLD pour l'attribution du handler.** Cette note ne décrit ni une OTA réussie ni un test sur le SmallTV. C'est une continuation **statique** de l'audit canonique [README](README.md) et de la [matrice des preuves](EVIDENCE_MATRIX.md).

## Objet et méthode

Éviter la confusion précédente entre `/doUpload` (route probablement liée aux fichiers) et `/update` (formulaire constructeur de chargement firmware). Reprendre les **octets publics épinglés** de la version OEM V9.0.44, résoudre les segments ESP8266, rechercher la chaîne terminée par NUL et ses références exactes 32 bits, examiner la table voisine, puis préparer un petit désassemblage Capstone 6 de ses adresses candidates. Aucun accès au propriétaire, aucun contact firmware/flash/Wi-Fi de l'appareil, aucune écriture en dehors des rapports Git.

## Preuves binaires revérifiées directement

| Observation | Valeur | Niveau |
|---|---|---|
| Source OEM | `GeekMagicClock/smalltv-ultra`, commit `55d7877fcba8b1cb7a66a0830d35d5b374bc8540` | PROUVÉ |
| BIN | `FW-Smalltv-Ultra-V9.0.44.bin`, **494 144 octets**, SHA-256 `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` | PROUVÉ historiquement et réinspecté |
| Texte exact `/update` | **offset fichier `0x7821C`** (apparition unique) | PROUVÉ |
| Segment | segment DRAM interne, début fichier `0x778FF` → début mémoire `0x3FFE8790` | PROUVÉ |
| Adresse mémoire calculée pour `/update` | `0x3FFE90AD` | PROUVÉ |
| Référence alignée à cette adresse | **offset fichier `0x11440`**, mot LE `0x3FFE90AD` | PROUVÉ |
| Mots voisins | `0x11444 → 0x3FFEF840`; `0x11448 → 0x3FFEF884`; `0x1144C → 0x40220968` | PROUVÉ |
| Octets au candidat `0x40220968` | début `32 12 02 91 FE FF A0 09 00` (offset fichier `0x20968`) | PROUVÉ |

**Attention :** le texte `/update` est ici en **DRAM**, tandis que `/doUpload` est présent dans la zone IROM des chaînes. Le pointeur `0x40220968` est **voisin** de la référence au texte `/update` ; ce seul voisinage ne démontre **pas** que cette adresse soit un gestionnaire HTTP, un callback d'upload ou une fonction OTA.

D'autres pointeurs IROM apparaissent dans la région voisine : `0x40214D2C`, `0x40215CE0`, `0x40211F68`. Les tables peuvent mélanger chaînes, états et callbacks ; **ne pas considérer chaque mot comme du code appelé**.

## Lecture du code : périmètre et verrou

Le kit Capstone V3 fourni par le propriétaire a décodé quatre fenêtres antérieures (dont la candidate `/doUpload`). Il **n'a pas décodé la région `0x40220968` ni établi un chemin d'appel `/update → auth → Updater → eboot`**. Le résultat actuel se limite donc à des octets et des pointeurs.

Un utilitaire privé d'analyse statique ciblée **V4**, conçu ici et testé sur 8 cas synthétiques, est disponible hors dépôt. Il vérifie le ZIP/BIN OEM de manière cryptographique, résout la chaîne DRAM, consigne ses xrefs et demande à Capstone ESP8266 des listings bornés de `0x40220968` et de quelques voisins. **L'exécution de ce V4 sur le vrai firmware reste NOT_RUN** jusqu'à réception de son rapport Windows `update_trace.json`. Les huit tests synthétiques ne valent pas une preuve de désassemblage réel V4.

## Confrontation aux sources publiques Arduino (sans attribution OEM)

Le composant **ESP8266HTTPUpdateServer** d'Arduino Core 3.1.2 possède une procédure connue : formulaire GET, réception POST, authentification selon paramètres, `Update.begin`, `Update.write`, `Update.end`, redémarrage ; le Core Updater peut déposer une commande eboot. Des chaînes OEM correspondent à ce composant public. **Il n'est pas prouvé** que GeekMagic utilise cette version exacte, la même configuration d'authentification ni ces chemins d'exécution.

Références : [serveur HTTP](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) ; [Updater](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp).

## Verdict et prochaine preuve à rechercher

- **ÉTAT :** chaîne `/update`, segment RAM, référence à `0x11440`, mots voisins et octets `0x40220968` **PROUVÉS**.
- **BLOCAGE :** aucune attribution de callback `/update` vérifiée, donc aucun jugement valable sur l'authentification ou la validation constructeur.
- **RISQUE :** confondre `/doUpload` avec le firmware OTA ou baptiser la routine voisine `0x40220968` « handler OTA ».
- **PROCHAINE ACTION :** analyser le reçu Capstone V4 réel, résoudre les littéraux et les appels éventuels, puis seulement créer un graphe de contrôle. En cas d'échec ou d'ambiguïté : HOLD, ne pas prétendre connaître la chaîne d'activation.
- **Impact SHINO :** **aucun changement firmware recommandé** sur la base de ces seules références. L'évolution B5.3, l'OTA, le layout 4m2m et les garde-fous restent indépendants.

**Provenance et restrictions :** aucune image OEM/MASTER, aucun secret, aucune capture réseau privée ni sortie binaire désassemblée complète n'est ajoutée au dépôt. Les notes historiques sont préservées. Le travail se fait sur cette branche documentaire de la PR Draft #50, sans merge ni modification Codex/B5.3.
