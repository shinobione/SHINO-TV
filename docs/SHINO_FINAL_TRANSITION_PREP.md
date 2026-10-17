# SHINO // TV — Préparation de l'ultime transition matérielle
**Décision propriétaire : 9 octobre 2026 — à reprendre ce soir ou ce week-end.**

## OBJECTIF en une phrase

**Une dernière intervention UART si nécessaire, puis une mise à jour SHINO → SHINO réussie en Wi-Fi, vérification de l'état normal et fermeture du boîtier.** Ni cosmétique LCD ni phase OTA alphabétique ne doivent précéder cette sortie matérielle.

## État à la reprise — immuable jusqu'à nouvel accord

- PR [#42](https://github.com/shinobione/SHINO-TV/pull/42), branche `feature/shino-tv-m9-flash-layout-liberation`, base de la présente préparation : `29c4ab7d60fb7b829505619f593e338a0eeaf999`. Cette SHA est un **point de départ**, recontrôler le HEAD exact à la reprise.
- Sur la machine : StageA normal 4m2m **gelé et installé**, 399264 octets, SHA256 `78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c`. Il ne reçoit **pas** de mise à jour Wi-Fi.
- LittleFS 4m2m `[0x200000,0x3FA000)`, 24 fichiers / 181402 octets, lecture seule acceptée. Fin flash ESP8266 réservée (24 KiB). Ne jamais reformater ni écraser ces zones.
- Le petit installateur Wi-Fi et le mode maintenance existent **hors ligne seulement**. Dernier verdict : `NO_GO`, mémoire simultanée native inconnue. Les anciens chiffres +1260 octets RAM statique et +8752 octets BIN / marge illustrative +1016 octets sont **des mesures/scénarios d'un build antérieur**, pas le résultat du candidat complet du nouveau HEAD. La comparaison Xtensa du candidat complet est désormais exigée par la CI.
- Installer Windows `QUALIFIED_LIVE=false`, aucun receiver installé, consentement de maintenance non câblé. Ne pas utiliser `--live` ni chercher à contourner ce verrou.
- Un backup privé 4 MiB et la voie UART ont été exploités précédemment ; leur existence ne constitue **pas** une garantie de récupération après coupure. Ne jamais afficher/committer les images privées, clés, identifiants, données individuelles.

## Construction à préparer HORS LIGNE — UN seul candidat réversible avant flash

Ne pas fabriquer un **firmware de sonde seul** qui imposerait une deuxième intervention UART pour ajouter plus tard le récepteur. Le candidat visé doit combiner :

1. **StageA normal préservé** : AP WPA2 privé, quatre valeurs / LINK, LittleFS lecture seule, restauration du normal si un test est annulé. Profil 4m2m 4 MiB DIO. Aucune activation involontaire d'un autre firmware/profil.
2. **Instrument de mémoire réel et read-only**, léger, pointé sur les appels natifs `ESP.getHeapStats` et `ESP.getFreeContStack` avec marqueurs de période **avant, pendant et après** : état normal stabilisé ; arrêt propre du HTTP ; Wi-Fi/AP maintenu ; écoute TCP ; client réellement connecté ; **réservation réelle de 256 octets de heap en dry-run** (même taille cible que le Core isolé, mais aucune écriture) ; réception à blanc ; libération ; HTTP reconstruit ; retour à LINK. Compter heap libre, plus grand bloc, fragmentation et minimum de continuation stack. Inclure échantillons **aux frontières d'allocation/cryptographie et dans le pump**, pas seulement le poll normal à 1 Hz. Le reset de watermark doit être explicite et traçable par période. Capteurs/relevés bornés, sans allocations d'un gros tableau ni logs secrets.
3. **DRY-RUN réseau**, sur l'AP privé et avec vraie pile TCP, utilisant l'identité/consentement privé et le protocole de SHINO // INSTALL, mais **avec aucune instruction de programmation flash de l'application : aucun `Update.write`, `Update.end`, eboot, RTC, reboot, FS-write ni formatage dans le mode test**. Une allocation réelle de 256 octets ne prouve PAS le coût simultané de l'Updater complet ni de TCP/lwIP ; distinguer l'allocation effectivement mesurée de tout coût extrapolé. Le scénario de test doit être annulable et restaurer le StageA. La vérification d'authentification, commandes U_FLASH uniquement et bornes applicatives reste nécessaire.
4. **Récepteur OTA dormant + activation séparément autorisée**, intégré au même candidat pour éviter de devoir ouvrir une deuxième fois, mais **non accessible tant que la qualification des ressources ET le consentement explicite de l'utilisateur ne sont pas établis**. Son mécanisme d'armement doit être audité, non contournable par commandes PC non authentifiées, répétition de paquets, compteur arbitraire ou configuration de test. Démontrer en host tests que sans ces conditions, aucun chemin n'atteint `Update.begin/write/end`.
5. **Relevé lisible pour l'utilisateur** via retour borné/authentifié ou journal opérateur sous contrôle explicite : verdict observé, minima heap/plus grand bloc/stack, max fragmentation, état AP/LINK, erreurs et chronologie. **Ne jamais afficher mots de passe, nonces sensibles ni BIN privés.**

### Planchers maintenus (et limites de la preuve)

`heap >= 20480 B`, `largest block >= 16384 B`, `free continuation stack >= 2048 B`, `fragmentation <= 25%`. L'admission initiale OTA garde sa réserve déjà utilisée : `heap >= 25600 B` avant allocations. Aucun seuil abaissé ni marge fictive rajoutée pour obtenir un PASS.

Des échantillons ponctuels ne constituent **pas** une borne mathématique sur le coût maximal du SDK/Wi-Fi/allocateur. La prise de mesures natives, la surveillance aux allocations et un arrêt sur franchissement de seuil améliorent la décision de risque, mais ne garantissent ni l'absence de pics entre mesures ni un rollback après coupure. Le succès du test à blanc ne vaut **pas** permission automatique d'écrire.

## Livraison attendue AVANT notre session physique

- [ ] Un seul dossier de travail sur la PR42 existante, pas de nouvelle branche/phase ; implantations **réelles et appelables** dans une copie d'étude StageA, pas seulement symboles conservés pour le linker.
- [ ] Candidat d'observation **source + build public reproductible**, avec deux modes `DRY_RUN_ONLY` et `OTA_DORMANT`, tous chemins producteurs de flash désactivés jusqu'à l'autorisation explicite. Ne pas enregistrer/promouvoir un BIN propriétaire sans revue séparée.
- [ ] Mesures RAM/BIN/stack Xtensa avant/après, inspection des écritures flash/FS/RTC/eboot et du démarrage normal, classification des mesures vraies vs estimations.
- [ ] Tests host réels de la sonde avec socket/AP mockés *et* tests protocole existants ; auth, mauvais BIN, erreur mémoire, client absent/déconnecté, AP perdu, timeout, annulation après réception complète, reprise LINK, sans aucun `Update.end` involontaire.
- [ ] CI exact HEAD (les 10 workflows encore `queued` au dernier contrôle, ne pas reprendre le 10/10 de l'ancien HEAD), état de PR42 Draft/open/non mergée, rapport limité à **GO_OBSERVATION_ONLY** ou **NO_GO**, avec une phrase expliquant le risque. Le **GO_OBSERVATION_ONLY n'est pas un GO pour écrire ou activer l'OTA**.
- [ ] Un **unique paquet de décision utilisateur** avec SHA exact du candidat, checksums, compteurs, instructions de vérification, séquence de retour vers le firmware gelé en cas de démarrage raté, et étapes opérateur sous approbation explicite. Si la capacité ne suffit pas : STOP et ne pas proposer le flash.

## Ce soir / ce week-end — ordre opératoire envisagé, NON AUTORISÉ à ce stade

1. Vérifier que nous disposons du candidat exact *qualifié hors ligne*, son SHA, les protections FS/tail, et d'un chemin de récupération/hardware réaliste. Ne pas croire un faux « PASS » d'émulation ; contrôler aussi la stabilité physique actuelle.
2. Expliquer clairement le risque résiduel d'un flash sur l'unique appareil et demander ton **autorisation explicite pour l'image exacte**. Sans ton GO, STOP.
3. Si autorisé : **une installation initiale UART**, préservation contrôlée de la flash et démarrage. Vérifier l'AP, les quatre cartes, LINK et l'inventaire FS.
4. Procéder **uniquement** au dry-run sur vrai Wi-Fi et relever minima stack/heap/block/fragmentation ainsi que déconnexion/reprise. Si un seuil échoue, arrêter l'OTA et conserver le firmware stable ; le boîtier ne peut pas encore être déclaré « clos sans UART ».
5. **Décision d'activation distincte après mesures**, encore soumise à revue technique et à ton GO. Une fois autorisée et disponible, une mise à jour SHINO→SHINO Wi-Fi contrôlée, nouvelle identité vérifiée après reboot, FS intact, quatre valeurs/LINK vivants. Une réponse `STAGED` ne suffit PAS : confirmation par vrai démarrage et identité fraîche.
6. **Alors seulement** : retirer toutes les pinces/CH340, refermer le SmallTV et documenter une procédure normale d'update Windows.

**État du présent document : plan de préparation et consignes pour le prochain chantier offline, aucun firmware prêt à flasher attesté.** Aucun contact appareil, COM8, USB, image privée, OTP/EEPROM, écritures flash/RTC/FS, reboot, merge, OTA live ni mise à jour physique autorisés par ce document.
