# SHINO // UPDATE

Une application normale, un serveur HTTP persistant, un installateur Windows.
La livraison reste **non installée / qualification physique non exécutée**.

Le firmware garde le StageA normal : AP WPA2 privé existant, Digest
`SHINO-StageA` pour la télémétrie/statuts, quatre cartes et TTL 6 secondes,
LittleFS monté en lecture seule avec vérification des 24 fichiers/181402 octets.
Les profils historiques et leurs preuves matérielles ne sont pas modifiés.

La mise à jour utilise `POST /api/v1/update` et un BIN brut. Un HMAC-SHA256
authentifie taille, hash, identité appareil/version et nonce à usage unique ;
le mot de passe de maintenance existant reste local. L'upload n'ajoute pas
Digest à cette authentification. `GET /api/v1/update/status` utilise Digest.
Aucun ARM/PROBE/INSTALL, serveur reconstruit, listener 8266, TLS, clé RSA ou
mise à jour de fichiers dans ce graphe. Les anciens prototypes restent des
archives de développement.

Core **3.1.2**, PlatformIO platform **4.2.1**, linker **4m2m**. L'Updater natif
conserve son buffer 4096 octets, son écriture/effacement et eboot. La seule
adaptation est une méthode inline `shinoAbort()` qui appelle `_reset(false)`
sans `end()` : même une image entièrement reçue peut être annulée sans
programmer le prochain boot. Les paquets PlatformIO installés ne sont pas
modifiés. Le parseur HTTP conserve la lecture bornée avant le body et utilise
le même header dans tous les fichiers C++ ; son callback traite l'upload en
streaming et les petites télémétries avec le Core.

Avant commit : SHA256 reçu **et relu en flash**, CRC Arduino, checksums et
bornes des deux images eboot/application, marqueur exact famille/appareil/build.
U_FLASH seulement, BIN 64000..0xFEFF0, une garde de secteur entre application
et staging, staging terminé à `0x200000`. LittleFS `[0x200000,0x3FA000)` et les
derniers 24 KiB sont hors écriture. Le linker est aussi vérifié dans l'ELF.
Admission heap >=25600, puis heap >=20480, bloc >=16384, continuation >=2048,
fragmentation <=25%, contrôlés pendant transfert/validation ; timeout 5 s
d'inactivité et 120 s total. Un franchissement arrête le transfert sans commit.
Les mesures ponctuelles ne bornent pas tous les pics SDK/IRQ/lwIP.

Depuis la racine, préparer une future release privée, sans contact appareil :

```powershell
python tools/shino_http_ota_build.py research-local/m9-owner/release-NOM-UNIQUE --private
```

Le répertoire doit être neuf. Les identifiants existants ne sont pas renouvelés.
Il contient le BIN sous `.pio/build/esp12e_m9_4m2m_normal_qualification/`,
`release.json`, `report.json` et le log local. **Ne partager ni BIN, sources
générées privées, log privé, ni `owner-credentials.json`.** Le build public
sans `--private` garde l'autorité d'installation fermée, tout en liant le même
graphe pour inspection.

Ouvrir `companion/SHINO-UPDATE.cmd`, choisir `release.json` et confirmer le hash
affiché. Vérification hors ligne avant toute connexion. L'outil utilise les
identifiants locaux et l'AP `192.168.4.1`, sans proxy/redirection. Arrêter LINK
pendant l'upload et le relancer quand l'outil le demande. Une seule requête
upload ; aucun retry. Le succès exige un **nouveau boot**, le SHA256 réel du
firmware exécuté, le build attendu, les fichiers vérifiés, les mesures fraîches
et un récepteur OTA encore disponible. Une réponse perdue se résout seulement
par ces lectures ; sinon le résultat reste UNKNOWN.

Pour l'essai initial, `tools/shino_prepare_ota_pair.py` prépare A/B distincts
et un unique paquet local, après commit du code. Il protège l'image installée
et les identifiants originaux. Sa séquence prévoit une seule installation UART
de A, la qualification en lecture seule (`companion/shino_qualify.py`, PRINT_ONLY
par défaut), puis une OTA A→B et les vérifications. **Le paquet ne constitue
aucune autorisation physique.** Aucun port série n'existe dans ces outils de build.

Le paquet crée `QUALIFY-A.cmd`, `UPDATE-B.cmd` et `QUALIFY-B.cmd`. Les lectures
exigent une confirmation ; l'upload exige le hash exact affiché. Chaque lanceur
conserve un résultat JSON local neuf et refuse un résultat déjà présent, pour
éviter une seconde tentative accidentelle. Aucun lanceur n'est exécuté par le
builder. Les budgets simulés et les cadres compilateur restent des preuves host.

`uart-commands.json` contient aussi les commandes initiales COM8 : lectures
PRE/POST privées de4MiB, copie locale du writer existant liée à A, comparaison
indépendante avant boot normal. Le writer fait un seul Begin/DATA/Finish/MD5,
sans répétition ni reboot automatique ; sa commande par défaut est AUDIT.
Le paquet ne lance aucune de ces commandes. L'ancien writer n'est pas rebindé.
Les hashes et ressources du paquet actuel sont dans
[le reçu de livraison](../docs/SHINO_BREAK_THE_LOOP.md).

La staging interrompue ne remplace pas l'application courante. Une coupure
pendant la copie eboot au reboot peut empêcher tout démarrage. Il n'existe
pas de rollback automatique dans ce layout ; la récupération reste le backup
privé 4 MiB et l'UART, sous autorisation distincte. Garder le boîtier ouvert
jusqu'à une OTA physique A→B acceptée.

Sources primaires comparées : [ArduinoOTA 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ArduinoOTA/ArduinoOTA.cpp),
[HTTPUpdateServer 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266HTTPUpdateServer/src/ESP8266HTTPUpdateServer-impl.h),
[ESPhttpUpdate 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266httpUpdate/src/ESP8266httpUpdate.cpp),
[Updater 3.1.2](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp),
[mémoire et limites OTA du Core](https://arduino-esp8266.readthedocs.io/en/stable/ota_updates/readme.html).
