# Synchronisation publique MUSIC follow â€” 3 novembre 2026

Cette mise Ã  jour concerne exclusivement le code et GitHub. Aucun Ã©tat matÃ©riel n'a Ã©tÃ© relu et aucune installation n'a Ã©tÃ© effectuÃ©e. Les constatations ci-dessous sont datÃ©es ; une copie d'Ã©cran de Â« derniÃ¨re lecture rÃ©ussie Â» ne prouve pas le SHA de l'EXE exÃ©cutÃ© ni les transitions musicales.

## Audit et sÃ©lection

DÃ©part de cette conversation : branche `feature/shino-tv-b3-telemetry-scratch-experiment`, HEAD `244334edac07701dc25b5ffc494715152ae1bfa5`, identique Ã  sa branche distante au contrÃ´le du 3 novembre. Working tree initial non propre, dont ROADMAP modifiÃ© et dossiers privÃ©s/non suivis : conservÃ© intÃ©gralement.

`main` (`8425dd7f2526c29e6c53b4294909a4bf03d3112f`) est un checkpoint documentaire ; il diverge de cette pile. La prÃ©paration publique est isolÃ©e depuis PR #85, SHA `1e27cec7b95c19fdc93651800f83524cb2583e93`, sans importer les modifications non committÃ©es de son worktree. Les travaux UI/firmware parallÃ¨les et les autres PR restent inchangÃ©s. La nouvelle PR dÃ©pend de #85 et reste Draft ; aucune fusion ou promotion de firmware.

## Ã‰tat rÃ©ellement Ã©tabli dans la conversation

| Travail | Ã‰tat / portÃ©e | Traitement public |
| --- | --- | --- |
| Installateur MUSIC temporaire et reconnaissance postboot | Outils opÃ©rationnels liÃ©s Ã  des preuves privÃ©es ; historique OTA UNKNOWN conservÃ© | Restent privÃ©s ; aucune autoritÃ© ni reÃ§u importÃ© |
| Collecte GSMTC, transitions et pochette 64x64 | Sources terminÃ©es et qualification HOST ; anciennes pochettes observÃ©es par le propriÃ©taire | Runtime et tests sÃ©lectionnÃ©s dans `review/music_follow` |
| Classification NOT_SENT / UNKNOWN / ACK | HOST qualifiÃ© ; aucune rÃ©pÃ©tition automatique aprÃ¨s Ã©mission possible | Transport publiÃ© comme source de revue |
| DÃ©couplage des modes | HOST 33 PASS antÃ©rieurement ; Horloge/Monitoring non grisÃ©s observÃ©s pendant l'incident du 27 octobre | Patch exact assaini ; intÃ©gration opÃ©rationnelle complÃ¨te reste liÃ©e aux preuves privÃ©es |
| Diagnostic DECOUPLED du 27 octobre | Session PLAYING ; BEGIN et deux TILE validÃ©s, TILE suivante HTTP 200 puis TIMEOUT post-ACK ; HOLD sans COMMIT/retry | RÃ©sumÃ© seulement ; trace et reÃ§u restent privÃ©s |
| Correctif POST_ACK | 14 tests HOST antÃ©rieurs PASS ; candidat produit, non lancÃ© physiquement par cette mission | Sources finales et cas de rÃ©gression reproductibles |
| Firmware MUSIC V1 installÃ© | Boot authentifiÃ© indÃ©pendamment dans la conversation ; ce constat ne rÃ©Ã©crit pas l'UNKNOWN du transfert | Ã‰tat rapportÃ© et datÃ© ; aucun BIN, identifiant d'unitÃ© ou preuve sensible publiÃ© |

La sÃ©lection ne contient aucun EXE, BIN/ELF/MAP, dump, sauvegarde, secret, identifiant Wi-Fi, clÃ© HMAC, fichier `.attempt`, reÃ§u privÃ©, journal de session ou trace physique brute. Les sources publiÃ©es sont passives Ã  l'import ; aucun launcher opÃ©rationnel nouveau n'est raccordÃ© au compagnon existant.

## Validation et limites

La suite publique ciblÃ©e reprend les qualifications existantes avec dÃ©pendances publiques, donnÃ©es synthÃ©tiques et transports injectÃ©s. Elle couvre le codec/artwork, GSMTC, le coordinateur, les contrats ACK/HMAC, les rÃ©sultats ambigus, le crÃ©neau mÃ©triques et la chaÃ®ne BEGIN + neuf TILE + COMMIT. Les gardes d'admission privÃ©es ne sont pas remplacÃ©es par des stubs opÃ©rationnels.

La compilation native ESP8266, heap/CONT/WDT, LittleFS, Wi-Fi/reconnexion physique et ressources du firmware sont **NON VÃ‰RIFIÃ‰S dans cette synchronisation** : aucun firmware n'est changÃ©. L'EXE POSTACK reste **NON QUALIFIÃ‰ physiquement** par les preuves prÃ©sentes. Les anciens 33 et 14 PASS restent des rÃ©sultats HOST datÃ©s, distincts de la nouvelle suite et de sa CI au SHA publiÃ©.

Le contrÃ´leur d'admission opÃ©rationnel complet, l'installateur et les artefacts spÃ©cifiques au propriÃ©taire restent en **HOLD de publication**. Les exporter nÃ©cessiterait un travail distinct de gÃ©nÃ©ralisation des preuves, non autorisÃ© ici. Le prÃ©sent checkpoint ne fabrique aucun secours, n'affaiblit aucun garde et ne prÃ©tend pas constituer un paquet d'installation.

## TraÃ§abilitÃ©

[SÃ©lection et reproduction](../review/music_follow/README.md) ; empreintes originales/publiques dans `review/music_follow/SOURCES.json`. La CI doit Ãªtre lue sur le SHA exact de cette branche ; un statut SKIPPED n'est pas un test rÃ©ussi. Toute opÃ©ration physique ultÃ©rieure exige une nouvelle autorisation exacte.
