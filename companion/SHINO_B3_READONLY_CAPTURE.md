# B3 — capture locale des marges mémoire (lecture seule)

**Statut : outil propriétaire expérimental, qualification physique B3 HOLD.**
Il n'autorise aucune nouvelle installation du firmware.

Script Windows : companion/shino_b3_capture.py
Vérification sans accès à l'appareil :
    py -3 companion\shino_b3_capture.py

Une fois un firmware B3 privé distinctement autorisé et installé, avec son
BIN, manifest et fichier d'identité locaux correspondants, la capture
nécessite un drapeau explicite :
    py -3 companion\shino_b3_capture.py --authorize-read --bin "research-local\m9-owner\firmware.bin" --manifest "research-local\m9-owner\release.json" --identity "research-local\m9-owner\owner-credentials.json" --output "research-local\m9-owner\b3-readonly-capture.json"

Les chemins ci-dessus sont uniquement des exemples : aucun fichier privé
n'est embarqué dans le dépôt et il est interdit de committer les données
du propriétaire dans GitHub ou de les coller dans une PR.

L'outil limite la cible à l'AP 192.168.4.1 et effectue au plus 33 GET
Digest authentifiés sur 200 s ; aucune commande POST, OTA, écriture ou
redémarrage. Les réponses sont bornées à 4096 octets, l'accès Digest est
coordonné avec SHINO LINK, et aucun mot de passe, nonce ni entête ne sont
conservés dans la capture. Un changement de boot/firmware interrompt le
relevé, sans réessai automatique.

Le rapport privé doit avoir un chemin inédit sous research-local/ (ignoré
par Git). L'outil n'écrase jamais une preuve antérieure. Relecture offline :
    py -3 tools\shino_b3_resource_evidence.py --input "research-local\m9-owner\b3-readonly-capture.json"

Seuils inchangés : stack 2048 B, heap 20480 B, plus grand bloc 16384 B,
fragmentation maximum 25 %. L'observation du high-water et des extrema à
la cadence du firmware ne prouve pas les pics inobservés, la provenance
cryptographique ou la sûreté d'un nouvel OTA. Le verdict physique demeure
HOLD jusqu'à validation indépendante.
