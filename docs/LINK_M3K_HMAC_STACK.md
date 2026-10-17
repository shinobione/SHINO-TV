# SHINO // LINK — M3-K : coût CONT de l'authentification M3-C

**17 octobre 2026 — GO propriétaire logiciel et recherche hors ligne uniquement.**
Base PR #65 M3-J au HEAD `cfad65363457828d94ec5d15066e6ca18cd0bf2a`,
**13/13 workflows SUCCESS vérifiés avant fork.**

## Hypothèse et modification précise

Le compilateur Xtensa (Core ESP8266 3.1.2 épinglé) a mesuré une
**frame statique de 992 octets** pour
`ShinoM3C::Gate::authenticateHeader<BearSslCrypto>`,
dans une application **inerte**, avec **+1 704 octets de BSS**
et **+16 784 octets de BIN** par rapport au témoin sans M3.
La CONT physique B5.3 communiquée par le propriétaire n'avait
que **80 octets de marge** au seuil rapporté. Ni l'addition
directe ni une déclaration de dépassement certain ne seraient valides.

M3-K essaie une **seule optimisation réversible et opt-in** dans
`experiments/link_m3c_crypto/M3CAuthenticatedIngress.h` :

- Par défaut (`SHINO_M3C_STACK_MEMBER_SCRATCH` absent ou 0),
  la source M3-C utilise exactement son tampon local historique
  `signedFields[350]`.
- Avec la macro **1 uniquement en laboratoire**, ces **350 octets**
  du message signé sont hébergés **dans chaque instance `Gate`**,
  au lieu d'être alloués dans la frame de fonction. L'authentification
  HMAC reçoit toujours les mêmes octets, dans le même ordre,
  puis le tampon est **effacé via écriture volatile**. Ni la clé HMAC
  ni les règles de parsing, SHA256, comparaisons à temps constant,
  délai, body-framing, CAS et rejet ne sont changés.
- La mémoire n'est pas gratuite : l'objet `Gate` grossit.
  Si le pump est global dans le banc inerte, la **BSS augmente**.
  S'il était alloué sur la pile ailleurs, le compromis serait
  inverse ; cela interdit de promettre une amélioration runtime
  généralisée. L'objet et les secrets ne sont jamais partagés
  entre connexions en parallèle.

## Épreuves obligatoires, sans assouplissement des critères

1. Compiler et exécuter **deux fois** les vrais tests M3-C OpenSSL
   (MAC, SHA256, en-têtes falsifiés, JSON exact, FIN, timeout, CAS)
   et M3-F (socket simulée, budget de 32 octets par passage,
   rejet sans lire le corps, replay, concurrence).
   Comparer les résultats **octet pour octet**.
2. Construire **deux ELF Xtensa identiques à l'exception de
   `SHINO_M3C_STACK_MEMBER_SCRATCH=0/1`**, avec la source
   B5.3 `FslessMetrics.cpp` véritable, Core 3.1.2,
   ArduinoJson 7.4.3 et linker 4m2m. Aucun serveur démarré
   ni firmware flashable.
3. Extraire les vraies **frames `-fstack-usage`** de
   `authenticateHeader<BearSslCrypto>` et
   `bodyByte<BearSslCrypto>`, ainsi que les différences ELF
   `.text`, `.data`, `.bss`, BIN et SHA256 des images inertes.
   **Fail fermé** si la frame de signature n'est pas réduite,
   ou si la frame `bodyByte` augmente.
4. Identifier le coût RAM/BSS et expliquer le compromis ;
   si la pile ne diminue pas, ne pas déclarer M3-K réussi.
   Ne jamais fabriquer une nouvelle mesure CONT, heap ou WDT.

Aucune modification de `firmware/`, `companion/`, de
`FirstBootBridge`/`HomeLan`, du firmware physiquement installé,
de SHINO LINK Windows, de Freebox, de Codex B5.4 ou des branches
concurrentes. Pas de clé de production, listener port 80 actif,
reboot, OTA, LittleFS, flash, RTC, accès réseau SmallTV, merge.

## Limites et prochaine décision

Même un résultat **Xtensa frame diminuée** prouve uniquement une
réduction de frame de la fonction compilée **dans ce graphe inerte**.
Le budget CONT de la B5.3 complète, le WDT, les chemins superposés
de fonctions, la mémoire heap, le serveur HTTP unique et la parité
de tous les handlers restent **HOLD**.

M3 produit nécessite encore une implémentation réelle, mesurée et
révisée, préservant Digest, les métriques, média, OTA/OEM,
HomeLAN, Wi-Fi AP secours et la gestion mémoire.

**Reçu :** CI M3-K au dernier SHA + fichier
`m3k_derived_stack_tradeoff.json` calculé depuis les artefacts,
non un nombre inventé.
