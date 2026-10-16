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

Un utilitaire privé d'analyse statique ciblée **V4**, conçu ici et testé sur 8 cas synthétiques, est disponible hors dépôt. Il vérifie le ZIP/BIN OEM de manière cryptographique, résout la chaîne DRAM, consigne ses xrefs et demande à Capstone ESP8266 des listings bornés de `0x40220968` et de quelques voisins. **Supplanté par le reçu V4 ci-dessous :** le kit a désormais été exécuté sous Windows sur V9.0.44, avec huit listings; ses huit tests synthétiques restent distincts de la réussite de l'extraction réelle.

## Résultat du vrai désassemblage V4 — reçu propriétaire du 16 octobre 2026

**Analyse du ZIP transmis dans cette conversation** `SHINO-OEM-UPDATE-20261016-212208.zip`. Le fichier reçu contient **6 282 octets**, SHA-256 calculé sur le ZIP **`c8c2bf6bf7cd3a4832592e11adb2ee53c8e709b56ea88efa111de921d3f2adc7`**, test intégrité ZIP **PASS**. Il comprend `update_trace.json` et huit listings texte. **Ne pas commiter le ZIP, le firmware ni les listings bruts dans le dépôt.**

Le reçu V4 annonce `CANDIDATE_CODE_WINDOWS_ONLY`, firmware V9.0.44, Git `55d7877fcba8b1cb7a66a0830d35d5b374bc8540`, ZIP SHA-256 `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f`, BIN SHA-256 `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`, BIN **494 144 octets** : valeurs concordantes avec la preuve OEM précédente.

**Fenêtres demandées :** 10 adresses ; **8 décodages Capstone produisent des listings**, **2 HOLD (« Capstone decoded zero instructions »)**, à `0x4026E980` et `0x4026E98C`. Ces deux dernières adresses correspondent à une zone de chaînes / données, **et leur échec n'est pas un échec du code fonctionnel OEM**. Les `window_length=256` représentent les **256 octets offerts au décodeur** et ne garantissent pas 256 octets d'instructions identifiées (les listings s'arrêtent parfois après quelques instructions et `ill`).

### Nouvelle piste : stub à 0x40220968

Extrait du listing propriétaire `00_xtensa_40220968.txt` :

```asm
40220968  321202   l16ui a3, a2, 4
4022096B  91feff   l32r  a9, . 0x40220964
4022096E  a00900   jx    a9
40220971  000000   ill
```

Le rapport lit au littéral `0x40220964` le mot `0x40220958` (offset BIN `0x20958`) : **cible d'un saut indirect probable**, car `jx a9` utilise le registre chargé par `l32r`.

**PROUVÉ/OBSERVÉ :** ces instructions sont présentes dans le reçu V4, et le mot cible est consigné par l'outil. **HYPOTHÈSE :** fonction relais/thunk. **NON VÉRIFIÉ :** le type exact de l'objet pointé par `a2`, la fonction vers `0x40220958` et surtout que `/update` atteigne ce code à l'exécution. Un saut lié à une table de méthodes ne peut être baptisé « handler OTA » par simple proximité.

### Les autres zones

| Début de fenêtre IROM | Listing | Constats stricts |
|---|---|---|
| `0x40211F2C` | `01_xtensa_40211F2C.txt` | Prologue/pile, branche, appels et saut indirect ; cible antérieure de `/doUpload` hypothétique |
| `0x40215CE0` | `02_xtensa_40215CE0.txt` | Prologue avec pile `0x50`, appels et branche ; identité fonctionnelle inconnue |
| `0x40214D2C` | `03_xtensa_40214D2C.txt` | Prologue avec pile `0x80`, plusieurs appels/boucles/conditions ; identité inconnue |
| `0x40211F68` | `04_xtensa_40211F68.txt` | `movi a3, 0xc8` et saut via `0x40211F64 → 0x40211F2C` ; lien HTTP non démontré |
| `0x40212754` | `05_xtensa_40212754.txt` | Prologue, appels ; identité inconnue |
| `0x4021516C` | `06_xtensa_4021516C.txt` | Prologue pile `0x70`, appels/branches ; identité inconnue |
| `0x4023021C` | `07_xtensa_4023021C.txt` | Petites branches et retours ; identité inconnue |

**Verdict V4 :** preuve nouvelle du **décodage réel de fenêtres Xtensa** et du relais `0x40220968 → 0x40220958` **au niveau des octets et du flot local** ; **pas encore** de chemin prouvé `/update → callback POST/authentification/Updater/eboot`. La piste suivante est donc `0x40220958` puis la recherche des **références *vers* le littéral `0x40211440`** dans le code, afin de retrouver la fonction qui consomme effectivement la chaîne `/update`. Ne pas déduire l'appel depuis les seuls mots contigus.

**Important :** le compte-rendu et les listings V4 sont une **preuve reçue de Windows**, pas une exécution de Capstone dans le conteneur GitHub ; aucune opération appareil.

## Recherche indépendante des utilisateurs de littéraux IROM

Pour dépasser la seule proximité des pointeurs, le ZIP OEM officiel V9.0.44 a été **redécodé en mémoire depuis la source GitHub épinglée**. Une recherche des motifs d'instruction Xtensa `l32r` pouvant charger les quatre mots adjacents du pool à `0x40211440`–`0x4021144C` a été effectuée sur la zone IROM.

**Limite méthodologique :** détection brute d'opcodes `l32r` possibles, **pas encore un désassemblage continu Capstone** ni une preuve de frontière de fonction. Une correspondance hors code peut être un faux positif. La formule appliquée à chaque candidat est : `literal = ((PC + 3) & ~3) + (int16_le(opcode[1:3]) * 4)`, conformément aux instructions `l32r` déjà rendues dans les listings Capstone V3/V4.

| Adresse IROM candidate de l'instruction | Octets | Adresse du littéral résolue | Valeur enregistrée dans le pool |
|---|---|---|---|
| `0x40211648` | `31 7E FF` | `0x40211440` | `0x3FFE90AD` → **texte `/update`** |
| `0x40211653` | `21 7C FF` | `0x40211444` | `0x3FFEF840` — objet RAM non nommé |
| `0x40211664` | `D1 79 FF` | `0x40211448` | `0x3FFEF884` — objet RAM non nommé |
| `0x40211689` | `91 70 FF` | `0x4021144C` | `0x40220968` — **routine relais décodée en V4** |

La recherche brute a trouvé **une signature** correspondant à `0x40211440` et **une** à `0x4021144C`. Plusieurs signatures correspondaient aux deux mots RAM voisins, mais celles affichées sont concentrées entre `0x40211648` et `0x40211689`. Le contexte à `0x40211689` contient les octets `91 70 FF A0 09 00` : selon les décodages Capstone antérieurs, le second triplet `A0 09 00` pourrait correspondre à `jx a9`. **Revalidation Capstone requise.**

**Piste de flot local, non démontrée :**

```text
/ update en DRAM @ 0x3FFE90AD
    ^
    | mot-littéral IROM @ 0x40211440
    |        |
    |        +-- l32r candidat @ 0x40211648 (utilisateur de la chaîne)
    |
Pool IROM @ 0x4021144C = 0x40220968
                  ^
                  +-- l32r candidat @ 0x40211689
                           |
                           +-- motif jx a9 @ 0x4021168C ?
                                     |
                                     v
                              0x40220968 (stub V4)
                                     |
                                     v
                              0x40220958 (cible du stub V4)
```

Ce schéma **n'est pas** un graphe de flux/route OTA confirmé : l'identité des objets RAM, les branches internes et les liaisons de données doivent être établies. La priorité technique passe à **désassembler en continu la fenêtre `0x40211620..0x402116A0`, puis la destination `0x40220958`**. C'est plus utile que de relancer des scans de pointeurs sans voir les appels.

## Reçu XREF V5 — pistes suivies jusqu'à 0x402208BC (16 octobre 2026)

**Source :** `SHINO-OEM-XREF-20261016-232451.zip`, reçu du propriétaire et vérifié dans cette conversation : **3 358 octets**, SHA-256 **`bbbd60458f9dfe86665c6b1213d97033710feb35f6d4d2d2be5e61f5173adf94`**, test d'intégrité ZIP **PASS**. Contenu : `xref_receipt.json` et **5 listings** Capstone Xtensa. Les empreintes constructeur V9.0.44 du reçu correspondent à celles déjà vérifiées dans cet audit.

**Statut fourni par l'outil : `HOLD_INCOMPLETE_XREFS` — ne pas le convertir en PASS**. Les cinq fenêtres sont bien décodées par Capstone, mais seulement **3 des 4 motifs `l32r` attendus** ont été observés à leur adresse exacte dans les listings **V5**. La quatrième instruction (`0x4022096B`) a été décodée dans le **reçu antérieur V4** ; elle n'était pas dans les zones proposées au décodeur V5. Les recoupements V4+V5 confirment les octets et cibles de cette chaîne **locale**, **pas** un flot d'exécution HTTP.

| Instruction observée | Interprétation très limitée | Provenance |
|---|---|---|
| `0x40211648 : l32r a3, 0x40211440` | Le littéral contient `0x3FFE90AD`, début de la chaîne **`/update`** dans la DRAM OEM | V5 |
| `0x40211689 : l32r a9, 0x4021144C` ; `0x4021168C : jx a9` | Le littéral donne `0x40220968`, cible du saut indirect **si ce point est atteint** | V5 |
| `0x4022096B : l32r a9, 0x40220964` ; `0x4022096E : jx a9` | Le littéral donne `0x40220958` | V4, point volontairement distinct du V5 |
| `0x40220958 : movi.n a4, 5` ; `0x4022095D : l32r a9, 0x40220954` ; `0x40220960 : jx a9` | Le littéral donne `0x402208BC` | V5 |
| `0x402208BC : addi a1, a1, -0x10` | Début de routine avec prologue et sauvegardes de registres, opérations `extui`, `call0`, `beqz` | V5 |

**Nuance majeure de flot :** le listing large de `0x40211620` s'arrête à `0x40211672`, puis un autre désassemblage commence directement à `0x40211689`. **Le segment `0x40211674..0x40211688` n'a pas été validé en continu**, et il n'existe pas encore de preuve qu'un chemin de traitement du texte `/update` atteigne l'instruction `jx` à `0x4021168C`. De plus, les octets situés après un `jx` inconditionnel (`0x4021168F` et `0x40220963`) ne doivent **pas** être considérés comme des instructions atteintes par simple continuation linéaire : ils peuvent relever d'un autre bloc ou de données.

**Routine `0x402208BC` :** dans la fenêtre décodée, elle tronque `a4` sur 8 bits, `a3` sur 16 bits, sauvegarde plusieurs registres, exécute des appels, teste `beqz` et écrit dans un objet pointé. **Aucun lien prouvé avec `Update.begin`, `Update.write`, `Update.end`, la signature OTA ou eboot.** Le nom et la portée de cette routine restent inconnus. Le listing est **partiel** ; aucune extrapolation à sa fin.

**Conclusion V5 :** présence démontrée de la chaîne `/update` comme opérande d'un `l32r` et d'une **suite de relais Xtensa localement décodés**, mais **attribution du gestionnaire OTA = HOLD**. La prochaine preuve pertinente est un désassemblage **continu et délimité par fonctions** autour de `0x40211620..0x40211690`, la résolution des `call0` et une comparaison des callbacks HTTP réellement inscrits. Ne pas solliciter d'OTA/flash physique pour combler cette lacune.

**Aucune action firmware / Wi-Fi / SmallTV / Codex / B5.3 réalisée.**

## Confrontation aux sources publiques Arduino (sans attribution OEM)

Le composant **ESP8266HTTPUpdateServer** d'Arduino Core 3.1.2 possède une procédure connue : formulaire GET, réception POST, authentification selon paramètres, `Update.begin`, `Update.write`, `Update.end`, redémarrage ; le Core Updater peut déposer une commande eboot. Des chaînes OEM correspondent à ce composant public. **Il n'est pas prouvé** que GeekMagic utilise cette version exacte, la même configuration d'authentification ni ces chemins d'exécution.

Références : [serveur HTTP](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h) ; [Updater](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp).

## Verdict et prochaine preuve à rechercher

- **ÉTAT :** chaîne `/update`, segment RAM, référence à `0x11440`, mots voisins et octets `0x40220968` **PROUVÉS**.
- **BLOCAGE :** aucune attribution de callback `/update` vérifiée, donc aucun jugement valable sur l'authentification ou la validation constructeur.
- **RISQUE :** confondre `/doUpload` avec le firmware OTA ou baptiser la routine voisine `0x40220968` « handler OTA ».
- **PROCHAINE ACTION :** suivre la cible `0x40220958` et identifier le code qui charge la référence littérale `0x40211440`, puis tracer les callbacks réellement enregistrés. Sans cela, ne pas construire de graphe OTA supposé. En cas d'échec ou d'ambiguïté : HOLD, ne pas prétendre connaître la chaîne d'activation.
- **Impact SHINO :** **aucun changement firmware recommandé** sur la base de ces seules références. L'évolution B5.3, l'OTA, le layout 4m2m et les garde-fous restent indépendants.

**Provenance et restrictions :** aucune image OEM/MASTER, aucun secret, aucune capture réseau privée ni sortie binaire désassemblée complète n'est ajoutée au dépôt. Les notes historiques sont préservées. Le travail se fait sur cette branche documentaire de la PR Draft #50, sans merge ni modification Codex/B5.3.
