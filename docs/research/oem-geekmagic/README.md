# Audit OEM GeekMagic SmallTV-Ultra — synthèse canonique

**Date de consolidation : 16 octobre 2026** · **Périmètre :** firmware constructeur GeekMagic SmallTV-Ultra / ESP8266 Xtensa LX106 · **Nature :** rétro-ingénierie **en lecture seule**, indépendante du développement SHINO B5.3.

> **ÉTAT : PARTIEL, MAIS AVANCÉ.** Deux véritables paquets OEM ont été inspectés, leur format interne et leurs checksums vérifiés, et quatre zones **candidates** du code Xtensa OEM V9.0.44 ont été désassemblées avec Capstone 6 sur Windows. **Aucune fonction OEM d'OTA n'est encore attribuée avec certitude, aucune décompilation C/C++ complète n'a été réalisée.**
>
> **Ne pas utiliser ce dossier comme autorisation de flash, OTA, reconfiguration Wi-Fi, accès réseau au SmallTV, redémarrage ou remplacement du mécanisme SHINO.** Les preuves sont hors ligne ; le projet B5.3 et son travail Codex restent indépendants.

Ce dossier centralise les découvertes des phases 1 à 4, puis l'essai Windows Xtensa V1/V2/V3. Les détails vérifiables, tables d'adresses et empreintes figurent dans **[EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md)**. Les rapports datés antérieurs restent historiques ; les affirmations qu'ils contiennent sur « aucun désassemblage disponible » sont **dépassées par l'essai Capstone V3**, pas effacées.

## 1. Pourquoi cet audit ?

Comprendre la technologie constructeur pour savoir **si elle apporte un avantage concret à SHINO // TV** :

- démarrage et contrôle d'intégrité des images ESP8266 ;
- réception et activation des mises à jour OTA, y compris échecs/interruption ;
- persistance et reconnexion Wi-Fi, AP/STA de secours ;
- écran 240×240, horloge/NTP, météo et stockage.

**Critère d'utilité :** une découverte ne devient une proposition de changement SHINO que si son fonctionnement OEM est confirmé et si son intérêt/risque pour notre code actuel est démontré. Pas de changement « parce que GeekMagic le fait ».

## 2. Ce qui est effectivement établi

| Sujet | Résultat | Niveau |
|---|---|---|
| Sources constructeur | Archives officielles V9.0.44 (commit historique épinglé) et V9.0.50 acquises par le connecteur GitHub ; ZIP DEFLATE décodés, CRC des membres et SHA-256 calculés | **PROUVÉ sur octets publics** |
| Nature des fichiers | BIN applicatifs OTA de **494 144** et **505 200** octets, **pas** deux sauvegardes complètes de flash 4 MiB | **PROUVÉ** |
| Format ESP8266 | En-tête initial à 0, seconde image à 0x1000, segments IRAM/DRAM/IROM ; images de type ESP8266 reconnues | **PROUVÉ par analyse statique** |
| Taille / CRC OEM | Champs de taille et CRC interne à 0x1010–0x1017 ; CRC non réfléchi 0x04C11DB7 avec ces huit octets neutralisés ; correspondent aux deux BIN | **PROUVÉ sur octets publics** |
| Checksum segment interne | XOR des segments avec neutralisation du même champ ; correspond aux valeurs 0x67 (V44) et 0x3E (V50) | **PROUVÉ sur octets publics** |
| Références réseau et OTA | Textes et pointeurs relatifs à \`/update\`, \`/doUpload\`, \`/wifisave\`, \`/wifi.json\`, \`/ntp.json\`, etc. retrouvés | **PROUVÉ comme octets / pointeurs**, rôle des gestionnaires **HYPOTHÈSE** |
| Code machine | Quatre zones candidates V9.0.44 désassemblées par Capstone 6 (mode ESP8266) ; 12 tests synthétiques du kit V3 PASS d'après exécution Windows | **OBSERVÉ sur rapport utilisateur**, attribution fonctionnelle **NON VÉRIFIÉE** |
| Bibliothèque OTA | Textes OEM très spécifiques concordant avec le \`ESP8266HTTPUpdateServer\` public ; source Arduino Core 3.1.2 lue | **Correspondance PROUVÉE**, version OEM et appels exacts **NON VÉRIFIÉS** |

Ces contrôles internes attestent un **format d'intégrité**, pas une signature cryptographique ni l'exécution effective d'un contrôle à l'upload. **Un transfert OTA réussi ne démontre pas le démarrage de l'image.**

## 3. Découverte utile : deux composants à ne pas confondre

### 3.1. \`/update\` : piste OTA prioritaire

Le BIN OEM contient \`/update\`, une page de transfert de fichier \`firmware\`, ainsi que des messages \`Update Success! Rebooting...\`, \`Unauthenticated Update\`, \`Not Enough Space\` et \`Update was aborted\`. Ces chaînes concordent avec le code source public \`ESP8266HTTPUpdateServer\`, mais le HTML OEM comporte aussi des personnalisations.

**Hypothèse :** bibliothèque standard Arduino ou dérivé constructeur. **Non prouvé :** identité de la version OEM, contrôle d'accès exact, signature/MD5 exigés, ordre des vérifications et comportement de son eboot. Les messages d'erreur *présents* ne sont pas des erreurs *observées sur l'appareil*.

### 3.2. \`/doUpload\` : une autre route, non équivalente à OTA

Un pointeur adjacent à la chaîne \`/doUpload\` conduit à l'adresse IROM candidate \`0x40211F68\`. Capstone décode notamment des instructions \`l32r\`, \`movi\` (valeur \`0xc8\`, soit 200) et un \`jx\` indirect. La valeur cible lue à l'adresse littérale \`0x40211F64\` est \`0x40211F2C\`.

**PROUVÉ :** octets, valeur de pointeur, décodage de la fenêtre. **HYPOTHÈSE :** petit relais de traitement HTTP. **NON VÉRIFIÉ :** qu'il soit exécuté pour \`/doUpload\`, ce qu'il traite, et qu'il ait le moindre lien avec l'OTA firmware. Il pourrait concerner un upload de fichiers médias. **Ne pas poursuivre la logique OTA en supposant \`/doUpload == /update\`.**

## 4. Comparaison utile avec SHINO

| Domaine | GeekMagic OEM | SHINO (source consultée sur la branche M9) | Décision |
|---|---|---|---|
| Intégrité BIN | Taille, CRC interne, XOR segments démontrés | \`ota/firmware/ShinoHttpOta.h\` valide également taille/CRC/segments et SHA-256 | **Conserver**, ne pas remplacer par CRC seul |
| Authentification OTA | **NON VÉRIFIÉE** ; la bibliothèque *publique* permet une authentification optionnelle selon configuration | HMAC de l'opération, identité, nonce, SHA-256 et validation avant \`core_.end(false)\` présents dans le code consulté | Ne pas rétrograder le protocole SHINO |
| Staging et boot | Comportement OEM non désassemblé ; Arduino Core utilise un staging dépendant du linker puis commande eboot | Cible SHINO \`4m2m\`, Core Updater/eboot et contrôles mémoire | Maintenir les garde-fous et la qualification physique/postboot |
| Wi-Fi | Routes et journal de versions constructeur : reconnexion annoncée | B5.1 LAN et travail B5.3 séparés, détails sur branche spécifique | Comparaison d'algorithmes **plus tard**, sans perturber Codex |
| Horloge / météo | Versions OEM annoncent correctifs DST/fuseau, secours horaire via météo | B5.3 SNTP/météo en cours sur une **autre branche** | Source d'idées, pas d'intégration automatique |
| LCD 240×240 | Le matériel et des pistes documentaires sont connus ; routine constructeur non identifiée | Rendu natif SHINO, quatre métriques | Désassemblage LCD non fait ; aucun changement |

**Attention au temps :** cette comparaison repose sur le code SHINO effectivement consulté en octobre 2026, **pas** sur une nouvelle lecture du firmware physiquement installé. La roadmap opérationnelle, l'état de B5.1/B5.2/B5.3 et les autorisations d'installation appartiennent à [\`docs/ROADMAP.md\`](../../ROADMAP.md) et [\`docs/AGENT_HANDOFF.md\`](../../AGENT_HANDOFF.md), non à ce dossier de recherche.

## 5. Outils : ce qui a marché, ce qui ne l'a pas fait

- **REA (morluto/rea)** : sa documentation confirme l'inspection par Binwalk et l'extraction par Unblob sur Linux x64, mais **aucune session REA sur les BIN OEM n'a été exécutée**. REA ne fournit pas de décompilation Xtensa brute garantie.
- **Xtensa GNU objdump**, outil PlatformIO Windows : \`--version\` et \`-i\` réussis, mais diagnostic sur trois octets bruts = plantage Windows \`0xC0000005\`. Cause interne non établie. Ne pas qualifier le firmware de corrompu.
- **Capstone 6** dans un environnement Python Windows isolé : kit V3, **12/12 tests synthétiques PASS**, quatre fenêtres de candidats désassemblées, statut \`CANDIDATE_DISASSEMBLY_OBTAINED\` dans le rapport transmis.
- **Ghidra / pseudocode / graphe d'appels OEM complet** : **NON EXÉCUTÉS**.

Les kits de diagnostic et ZIP Windows restent **hors du dépôt**. Aucun BIN propriétaire, sauvegarde flash MASTER, secret, trace Wi-Fi privée ou fichier de configuration personnel n'est commité.

## 6. Conclusions et prochaines actions classées

1. **OTA constructeur /update (priorité technique)** : trouver sa table de routes et sa cible de callback **par preuves de références/calls**, puis suivre les contrôles de firmware, d'authentification et de commit eboot. **HOLD** tant que le graphe n'est pas confirmé.
2. **Comparer uniquement des mécanismes démontrés** aux sources SHINO exactes, sans baisser HMAC, SHA-256, mémoire ou contrôle postboot. Aucune correction de firmware proposée par ce dossier.
3. **Wi-Fi, horloge, LCD** : examiner ensuite si une pratique OEM améliore la résilience de SHINO, sans interrompre Codex/B5.3.

**Critère d'arrêt :** si REA/Ghidra n'apportent pas de preuve exploitable dans un budget borné, conserver ce dossier de recherche sans lancer une nouvelle mission ouverte ni créer de complexité OTA.

## 7. Sources et traçabilité

- [Matrice des preuves, SHA-256, adresses et interprétation prudente](EVIDENCE_MATRIX.md).
- [Audit SHINO historique fabricant](../../FIRMWARE_AUDIT_01.md) et [layout comparatif](../../COMPARATIVE_FLASH_LAYOUT_AUDIT.md).
- [Manifeste OEM V9.0.44 historiquement épinglé](../../../recovery/factory_ota_v9_0_44.json).
- [Firmware officiel GeekMagic V9.0.44, commit épinglé](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip).
- [Firmware OEM V9.0.50 et changelog](https://github.com/GeekMagicClock/smalltv-ultra/tree/f7c887403a6ee1278efdb97bf4bbd3d7a791e9bd/Ultra-V9.0.50).
- [REA : limites de l'analyse firmware](https://github.com/morluto/rea/blob/main/docs/firmware-analysis.md).
- [ESP8266 Arduino Core 3.1.2 — serveur HTTP OTA](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h), [Updater/eboot](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp) et [getFreeSketchSpace](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Esp.cpp).
- [Branche SHINO de référence M9](https://github.com/shinobione/SHINO-TV/tree/feature/shino-tv-m9-flash-layout-liberation) et [branche B5.3 distincte](https://github.com/shinobione/SHINO-TV/tree/feature/shino-tv-b53-autonomous-host).

**Règle de preuve :** \`PROUVÉ\` = calcul/code/bytes examinés ; \`OBSERVÉ\` = reçu Windows/retour propriétaire ; \`SIMULÉ\` = simulation ou test synthétique ; \`HYPOTHÈSE\` = interprétation plausible ; \`HOLD/NON VÉRIFIÉ\` = conclusion interdite à ce stade.