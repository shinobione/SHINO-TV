# SHINO // LINK — M3-L : HMAC incrémental sans message signé en RAM

**18 octobre 2026 — GO propriétaire logiciel/CI uniquement.**
Branche isolée empilée sur Draft PR #66 M3-K au HEAD
`d299cf262e90bc2cf8f7fd40c50fa2519175c620` avec
**15/15 workflows PASS** au fork. Ne pas modifier `firmware/`,
`companion/`, Codex B5.4, ni le SmallTV ou son Wi-Fi.

## Hypothèse

M3-J : frame compilateur Xtensa
`Gate::authenticateHeader<BearSslCrypto>` **992 o**.
M3-K : déplacer le buffer canonique de 350 octets
dans chaque objet `Gate` ramène la frame à **640 o**,
mais fait monter la `.bss` de **352 o** dans son laboratoire.

M3-L tente de gagner de la pile **sans augmenter la RAM statique**,
en éliminant complètement le tampon de message canonique.

## Implémentation expérimentale bornée

Le chemin existant reste **désactivé par défaut**. La compilation
`SHINO_M3C_INCREMENTAL_HMAC=1` active seulement dans
`experiments/link_m3c_crypto/M3CAuthenticatedIngress.h` :

1. Conversion bornée de la révision 32 bits et de la longueur
   du corps en décimal canonique, exactement comme l'ancien
   `snprintf` ;
2. Segments dans **l'ordre strict** du contrat original :
   `SHINO-M3-CONTROL-1\nPOST\n`, route, IP attendue,
   device, boot, révision, mode, transaction, longueur,
   SHA-256 hexadécimal déclaré, avec séparateurs `\n`
   identiques ;
3. Vérification **stricte de la longueur concaténée
   < 350 octets** (borne de l'ancien `snprintf`) avant
   toute authentification, sans concaténation effective ;
4. Calcul HMAC-SHA256 réellement incrémental :
   `EVP_MAC_update` sous OpenSSL 3 HOST et
   `br_hmac_update` sous BearSSL ESP8266. Chaque
   fragment met à jour **le même contexte HMAC** ;
   jamais un HMAC par morceau. Comparaison en temps
   constant, effacement des intermédiaires et des
   contextes BearSSL ;
5. Le protocole M3-C pré-corps, le digest du corps,
   la canonicalisation JSON, les délais, le FIN TCP,
   le CAS et les décisions de rejet restent inchangés.

La combinaison M3-L + tampon membre M3-K est **interdite
à la compilation**. Le chemin par défaut et M3-K demeurent
comme témoins de référence ; **aucune clé propriétaire**
dans ce laboratoire.

## Validation et critères non négociables

- Trois exécutions avec les mêmes tests **OpenSSL réels**
  M3-C, M3-F : original, scratch membre M3-K et
  fragments M3-L, y compris les vecteurs d'authentification
  et les en-têtes/corps falsifiés, FIN, délais, replay.
  Les sorties doivent être identiques ; l'ancien
  limiteur canonique de 350 octets doit être conservé.
- Trois builds **inertes Xtensa** au même Core ESP8266
  3.1.2, PlatformIO espressif8266 4.2.1,
  ArduinoJson 7.4.3 et layout linker 4m2m.
  Source originale `FslessMetrics.cpp` compilée dans
  chaque variante ; `WiFiServer` seulement construit,
  jamais démarré. Pas de firmware de produit généré.
- Comparaison calculée depuis ELF/BIN réels :
  tailles BIN et SHA256, `.text`, `.data`, `.bss`,
  frame `authenticateHeader<BearSslCrypto>`, frame
  `bodyByte` et éventuelles frames spécifiques à
  l'implémentation streaming. **FAIL** si frame signature
  pas réduite par rapport au M3-C original, si BSS
  dépasse l'original ou si frame body augmente.
- **Ne pas** inférer une borne totale de pile ou une
  marge CONT du vrai ESP8266 depuis les annotations
  de fonctions compilateur : appels imbriqués, code
  inliné, interruptions, SDK et exécution ne sont
  pas couverts. Même un PASS de ces tests n'autorise
  aucune intégration sur B5.3.

## HOLD durable

M3-L ne crée pas de propriétaire HTTP `WiFiServer(80)`
réel, n'implémente pas les handlers `FirstBootBridge`
et `HomeLan` avec Digest, n'active pas les commandes
de mode côté Windows ou LCD et n'améliore **pas de façon
mesurée** les ressources physiques de B5.3.

Dernier préflight physique communiqué : CONT minimale
**2 128 o**, seuil **2 048 o**, marge seulement **80 o**,
avec journal non lu et fin de campagne STOP/HOLD.
On ne soustrait pas des frames de laboratoire à cet
instantané. Tous les contrôles mémoire runtime et
OTA/LittleFS/media/recouvrement restent **HOLD**.

Le résultat sera documenté avec la CI au **HEAD exact**.
Aucun flash, OTA, redémarrage, écriture Wi-Fi/RTC,
Freebox, mot de passe réel, merge ni push concurrent
sur une branche Codex n'est autorisé par ce GO.
