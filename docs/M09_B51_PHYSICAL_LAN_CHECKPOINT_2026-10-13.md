# Mission 9 — B5.1 PHYSICAL LAN checkpoint, 13 octobre 2026

**Jalon fonctionnel : PASS PHYSIQUE rapporté par le propriétaire.**
Ce document fige des observations déjà réalisées et leur provenance. La mission
de gel ne contacte pas le SmallTV et ne modifie aucun firmware.

## Provenance et identité figée

Source publique : [compte rendu propriétaire sur PR #47](https://github.com/shinobione/SHINO-TV/pull/47#issuecomment-6155556845),
publié par `shinobione` le 13 octobre 2026 à 21:26:58 UTC.
Le mandat propriétaire de gel précise l'adresse DHCP observée et les limites
ci-dessous. Les captures sont rapportées dans ce compte rendu ; aucune nouvelle
capture ni lecture matérielle n'est effectuée pendant ce gel.

- Image propriétaire B5.1 : **414176 octets**.
- SHA-256 : `973cf725ab1d7a259d00d60e8af8a8e8e2da544af39578e06b649218588607cf`.
- Source de compilation conservée : `50b732e084079b58e21e33f22ac2f5f4611047c1`,
  distincte du HEAD documentaire de départ `a063c001d69ffaffb6beac8427e03941d371ac68`.
- Branche : `feature/shino-tv-b3-telemetry-scratch-experiment` ; PR #47 reste
  ouverte, Draft et non fusionnée. Aucun BIN ou identifiant privé n'est publié.

## Preuves physiques et portée

| Observation | Preuve et verdict |
| --- | --- |
| Transfert complet Windows | 414176/414176 octets envoyés rapportés, sans retry automatique. Ce seul compteur ne prouve pas le démarrage. |
| Reçu initial | `POSTBOOT_ACCEPTANCE_UNCONFIRMED` : acceptation après démarrage non confirmée à cet instant. Le reçu historique n'est pas réécrit en succès. |
| Identité exécutée | GET physique authentifié ultérieur de `/api/v1/update/status` via Freebox LAN et captures propriétaires confirmant taille/SHA B5.1 : **PASS PHYSIQUE**. |
| Premier boot et Freebox | B5.1 exécuté et connecté au LAN : **PASS PHYSIQUE** pour ce premier démarrage observé. |
| Adresse LAN | `192.168.1.70`, bail DHCP observé selon le mandat propriétaire ; aucune configuration fixe ni garantie de conservation de l'adresse. |
| LittleFS | `fs_ok=true`, **24 fichiers / 181402 octets**, rapportés par le GET physique. |
| Route OTA | `ota_enabled=true` dans le statut physique ; cette annonce ne qualifie pas un transfert complet sur LAN. |
| Quatre cartes et LINK | CPU, GPU, RAM, GPU temp fonctionnelles, mesures vivantes confirmées par le propriétaire via SHINO LINK sur LAN depuis le PC Ethernet : **PASS PHYSIQUE**. |

La preuve du transfert Windows, le reçu incertain et la confirmation physique
ultérieure restent trois preuves distinctes. Le support réseau du transfert
initial n'est pas déduit de la lecture LAN ultérieure.

Le compte rendu conserve aussi l'essai partiel antérieur sur **B5 récepteur** :
8192 octets envoyés, `FAILED_NO_COMMIT`, minima échantillonnés heap24128 B,
bloc22736 B, continuation2128 B et fragmentation maximale11 %.
Cette preuve concerne B5 pendant cet essai partiel ; elle ne qualifie ni les pics
d'un transfert complet ni la mémoire native B5.1. La marge de continuation
observée reste80 B au-dessus du seuil2048 B.

## NON VÉRIFIÉS — HOLD

- Redémarrage volontaire ou cycle de courant après ce premier boot.
- Reconnexion automatique après perte de routeur, réseau ou alimentation.
- Retour de l'AP secours et récupération après perte du LAN.
- OTA complète effectuée sur LAN, y compris transfert interrompu ou réponse perdue.
- Récupération RTC/eboot, absence actuelle de commande de boot en attente et
  récupération d'un firmware non démarrant. Eboot ne garantit pas de rollback.
- Maxima mémoire OTA natifs simultanés : heap, plus grand bloc, continuation et
  fragmentation dans tous les chemins SDK/ROM.

Le PASS fonctionnel décrit plus haut n'autorise aucun nouveau GET/POST physique,
OTA, reboot, provisionnement ou opération de récupération. Une autorisation
propriétaire distincte reste nécessaire pour chaque future opération exacte.

## Gel logiciel et confidentialité

Les sources/tests des diagnostics B5 et du transport partiel sont sauvegardés
comme outils historiques explicites, hors production : inspection locale par
défaut, autorisations physiques séparées, aucune reprise automatique. Le
transport partiel conserve son AP192.168.4.1 exclusif ; il n'est pas un outil
d'OTA LAN B5.1 et ce gel ne le réarme pas. Le registre durable et le verrou
Digest doivent appartenir au même profil Windows que LINK ; le LOCALAPPDATA
temporaire d'un sandbox ne prouve pas une coordination avec le profil normal.

Les identités et secrets nécessaires à une séance propriétaire ne sont pas
nécessaires aux tests synthétiques. Les tests du transport partiel utilisent
le dossier temporaire ignoré `research-local` : ce dossier doit exister pour
reproduire ces tests dans un clone neuf, sans aucun paquet propriétaire.

Le BIN B5.1, ses BIN/ELF/manifestes/rapports privés, le MASTER4 Mio, les secrets,
reçus et marqueurs `.attempt` restent exclusivement locaux et préservés.
Seuls sources, tests et documents publics revus entrent dans ce gel.

`SceneEngine.h`, `ArtworkAdapter.inc`, `media_sessions.py` et la documentation
[du pilote PR #40](artwork-pilot/README.md) restent intacts. V2.2 horloge/pochette
reste un pilote distinct hors ligne, **non installé et non intégré à B5.1**
par cette mission.

Les résultats HOST antérieurs et la CI de `a063c001` conservent leur portée
logicielle. La CI du **nouveau HEAD de gel** doit être lue après push, avec ses
jobs exécutés, ignorés ou non déclenchés séparément. Aucun résultat CI ne vaut
une preuve physique de redémarrage, reconnexion, AP secours ou récupération.

Contrôles locaux du gel : syntaxe des quatre sources/tests Python PASS ;
**14 tests HOST ciblés PASS**, garde globale socket/DNS sans aucun appel.
Ils couvrent le défaut hors ligne, le sentinel IP hors STA, le second401,
le plafond/HMAC, les écritures courtes, l'AP exclusif, la réservation par image,
les instances concurrentes, les échecs incertains/fsync, les secrets et la
collecte séparée. Les suites complètes et leurs tests TCP loopback n'ont pas été
relancés localement ; aucun firmware n'a été reconstruit. Les quatre éléments
V2.2 demandés correspondent au HEAD de départ et leurs empreintes sont conservées.

La première CI du commit `251be908d760ff3d61958dff851afd384a3f267b` a révélé
un défaut de classification : les gardes signed/StageA cherchaient les nouveaux
scripts dans leur baseline historique `7455f6b`. La maintenance ciblée inscrit
uniquement les quatre blobs Git publics revus dans les listes d'empreintes
exactes existantes de ces deux gardes. Aucune exemption globale, aucun ancien
pin, seuil mémoire, firmware ou transport normal n'est changé.
**5 régressions de garde source PASS** après reproduction de l'échec : clôture
des fichiers Git suivis des deux gardes, empreintes revues, refus de chacun des quatre scripts
altérés, refus d'un script inconnu et maintien du gel d'un ancien companion.
Ces régressions exécutent le bloc réel de pin/comparaison extrait des gardes,
sans dupliquer sa logique et sans SDK ; seuls lectures/Git sont nécessaires,
sockets/DNS sont interdits. Le job général a révélé la dépendance SDK indue de
la première version du test ; elle a été retirée. Le clone superficiel du job
général ne contient pas non plus les anciennes révisions : les tests unitaires
utilisent les blobs HEAD immuables comme snapshot, tandis que les gardes
spécialisées continuent de contrôler les vraies références historiques.
Les gardes complètes restent
exécutées avec leur SDK public par les workflows spécialisés, sans changement.
La CI du HEAD suivant doit être contrôlée séparément des échecs précédents.
