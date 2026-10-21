# SHINO // LINK — Issue 83 : vérification du firmware dans le menu Windows

## Réconciliation avec B5.4 postboot (19 octobre 2026)

Depuis le développement HOST de l'issue #83, le [GET postboot de
Codex dans #81](https://github.com/shinobione/SHINO-TV/issues/81#issuecomment-6275185762)
a confirmé **P0+Updater512+B5.4 privé (431 920 octets)**, identité
exactement rapprochée aux preuves privées et boot distinct. **Ce GET
n'a PAS été déclenché par le menu #83** : le nouveau menu reste
non installé et les tests de la PR #85 restent HOST/Win32 simulés.
Le nom B5.4 ne doit toujours être montré au clic que lorsque la
réponse authentifiée et le vrai couple BIN/manifeste local vérifié
coïncident ; aucune table taille→version statique.

**HOLD inchangé avant déploiement :** le reçu historique
`STOP_UNKNOWN_NO_RETRY` et toutes les réservations `.attempt` du
client OTA one-shot #81 sont **conservés**, même après la preuve de
postboot. Notre lecture actuelle ne sait pas encore localiser et
coordonner toutes ces réservations. Ne pas contourner le verrou
du diagnostic ni effacer les marqueurs pour « faire marcher » le menu.
Ce chantier est désormais inclus dans la [PR unique M3-R #85](https://github.com/shinobione/SHINO-TV/pull/85) ;
[#84](https://github.com/shinobione/SHINO-TV/pull/84) est une source historique.


19 octobre 2026. Recherche PC seulement. Branche Draft isolée basée sur PR54/M2, aucun GET physique, OTA ou installation Windows.

## Fonction
Un clic sur « Vérifier le firmware du SmallTV… » déclenche un seul worker éphémère : GET /api/v1/update/status depuis l'IPv4 RFC1918 déjà configurée, lecture authentifiée 401→200 par le client B5 existant, 6 secondes globales, réponse JSON bornée 4096 octets, verrou Digest OS jusqu'à la fermeture. Pas de deuxième émetteur de métriques, polling, retry, POST, OTA, Wi-Fi ni flash.

Une validation d'identité indépendante remplace uniquement la validation du diagnostic B5 spécifique à une release et aux seuils mémoire. Les protections réseau, de framing, de nonce et le verrou Digest existants sont conservés. Un schéma incompatible est refusé, jamais présenté comme B5.4.

Le sous-menu « Identité lue (détails) » montre l'état, le nom seulement si reçu vérifié, les préfixes Build ID et SHA-256, la taille BIN, l'heure locale et les états OTA/LittleFS déclarés. Une réponse GET n'est pas une preuve visuelle sur le LCD ; ota_enabled ne démontre aucune installation.

## Catalogue privé facultatif
Aucun inventaire de releases privées n'est codé en dur. Le fichier facultatif firmware-receipts.json dans le dossier privé de configuration LINK peut contenir un objet schema=1, receipts=liste de 0 à 10 objets comportant exactement name, bin, manifest. Les chemins BIN et manifeste doivent être absolus. Le nom humain provient uniquement de cette liste fournie et approuvée par le propriétaire. shino_update.inspect lit les véritables octets BIN, valide le manifeste, recalcule taille et SHA-256 et confirme l'identité embarquée ; device/build_id/sha256/bytes/descriptor doivent correspondre au GET. Sinon « Version inconnue — identité lue ».

Attention : la provenance ou signature externe d'un reçu privé reste distincte des seules vérifications de cohérence de fichiers. Ne jamais copier dans GitHub une identité privée ni un reçu brut.

## Coordination OTA
Des fichiers *.attempt déjà présents dans le dossier LINK interdisent le GET, avant la lecture des credentials, après et à la fin de l'opération. Aucun marqueur n'est supprimé. La localisation réelle de tous les marqueurs du client OTA #81 reste à unifier et à qualifier : une OTA externe au répertoire surveillé peut ne pas être vue. Aucun déploiement propriétaire jusqu'à coordination prouvée avec l'exécuteur OTA local. STOP si état OTA actif, incertain ou STOP_UNKNOWN_NO_RETRY.

## Tests / statuts
Scénarios HOST : vrai chemin de menu fake pystray, worker unique, 401→200, réponse inconnue, schema invalide, redirection, HTML, oversize, 401/403, absence de reçu, reçu inspecté, file *.attempt, timeout, verrou et erreurs. CI au SHA exact.
Tests Win32 réels sur bureau propriétaire : NOT_RUN. GET physique : NOT_RUN. OTA : NOT_RUN. Aucun firmware modifié.
Les guards source M9/M2 doivent rester stricts et exacts : ne pas abaisser les seuils ni les contourner pour PASS.