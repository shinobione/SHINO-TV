# SHINO // LINK — M3-A : contrat de contrôle d'affichage (HOST, aucune liaison appareil)

**17 octobre 2026 — développement autonome empilé sur PR #54.**
**Statut : PROPOSÉ + LABORATOIRE PYTHON hors ligne. M3 NATIF : HOLD.**

## Décision et frontière de sécurité

Le propriétaire a donné « go M3 » après validation des quatre modes M1/M2
et du tray visuel Windows. Ce GO autorise **le développement du contrat et des
tests HOST** ; il ne vaut **pas** autorisation d'OTA, de modifier la B5.3
installée, de lancer SHINO // LINK sur le PC, de contacter le SmallTV,
de fusionner les PR, ni d'interrompre Codex pendant B5.4.

Ce dossier ajoute seulement le modèle `experiments/link_m3_control_contract/`.
Il n'est importé ni par `companion/shino_link.py`, ni par le firmware,
ni par le démonstrateur Win32. Aucun endpoint des noms proposés n'existe
sur la B5.3 physique. Ne jamais utiliser `LabTransport` comme adaptateur
réseau : il **n'accepte qu'une instance `FakeDevice` en mémoire**.

## Protocole candidat (noms de routes NON déployés)

| Opération | Route envisagée | Méthode | Usage |
| --- | --- | --- | --- |
| Capabilities | `/api/v1/display/capabilities` | GET | Accord strict de version, liste des quatre modes, identité et boot |
| Status | `/api/v1/display/status` | GET | Révision, préférence confirmée, scène effective, dernière transaction |
| Select mode | `/api/v1/display/mode` | POST | Une intention utilisateur authentifiée, puis ACK et GET indépendant |

Identifiant `protocol = shino-display-control-1`, **candidat seulement**.
Schémas JSON **fermés** sans clés inconnues/dupliquées, nombres non entiers,
booléens déguisés en entiers, valeurs NaN/Inf ou chaînes illimitées.
Bornes hors ligne : POST ≤ **240 octets**, capabilities ≤ **384 octets**,
ACK ≤ **256 octets**, status ≤ **384 octets**. Ce sont des limites de contrat
candidates, **pas** des mesures de pile, d'allocations du WebServer,
d'empreinte réelle ni des ressources matérielles validées.

Command (champs exacts) :

`{"protocol":"shino-display-control-1","device":"<16 hex minuscule>","boot":"<32 hex minuscule>","revision":0,"mode":"AUTO","tx":"<32 hex minuscule>"}`

ACK (champs exacts) :

`{"protocol":"shino-display-control-1","device":"...","boot":"...","revision":1,"mode":"AUTO","tx":"...","accepted":true}`

Status (champs exacts) :

`{"protocol":"shino-display-control-1","device":"...","boot":"...","revision":1,"mode":"AUTO","scene":"OFFLINE","last_tx":"..."}`

Capabilities: mêmes protocol/device/boot + `control:true`,
`modes:["AUTO","CLOCK_WEATHER","MONITORING","MUSIC"]`,
`max_command:240`.

- `device` identifie le SmallTV préalablement qualifié, **pas** l'IP seule.
- `boot` est un jeton distinct et non réutilisé à chaque démarrage. **Source
  d'entropie/anti-répétition native NON PROUVÉE** ; sans elle : M3 HOLD.
- `revision` est CAS, `uint32` sans rollover permis; à la limite,
  commandes refusées jusqu'à un nouveau boot.
- `tx` est une intention unique par clic et non un identifiant réutilisé ;
  l'obtention aléatoire sûre reste à démontrer dans l'adaptateur Windows.
- Le mode **demandé** est distinct du mode **reçu et confirmé**, lui-même
  distinct de la scène **effectivement rendue**. Un ACK n'est **pas** une
  preuve de pixel ST7789; cette qualification reste native/physique M4.
- Idempotence dans le modèle : double livraison strictement identique du
  dernier `tx` renvoie le même ACK sans second commit, une collision/altération
  est refusée. **Le client n'utilise JAMAIS cette idempotence pour rejouer
  un POST ayant produit un résultat incertain.**

## Flux d'une seule intention

1. L'utilisateur choisit un mode. Il faut une **liaison appareil + boot déjà
   approuvée**. Aucun simple numéro IP reçu d'un GET ne vaut approbation.
2. Sous le **même coordonnateur Digest existant** à qualifier, lire
   capabilities et status. Refuser protocole inconnu, version/boot/appareil
   divergents, liste différente ou contrôle indisponible.
3. Émettre un POST strictement borné avec un `tx` frais et le CAS attendu,
   **une fois maximum**. Le serveur doit authentifier la requête
   **avant de lire ou allouer le corps**. Un échec d'admission ne doit
   changer aucune scène ni aucun état persistant.
4. Vérifier identité, boot, transaction, révision et mode de l'ACK, puis
   **GET status indépendant** pour la même transaction et même révision.
   `CONFIRMED` n'existe que si ACK ET readback concordent.
5. Coupure, timeout, ACK perdu, parse invalide, réponse incohérente,
   verrou Digest occupé ou boot changé : **UNKNOWN / HOLD**,
   aucune répétition automatique. Un GET de réconciliation en lecture seule
   est permis, mais ne libère pas automatiquement le HOLD.
6. Une intention ultérieure exige une session neuve et un geste explicite ;
   un clic rapide pendant HOLD n'est pas une permission de rejouer.
7. Les métriques CPU/GPU/RAM/GPU temp gardent l'envoi dans le worker unique
   toutes les ~2 s et le TTL 6 s ; la commande de mode ne se substitue jamais
   au POST métrique et n'a aucune priorité absolue.

## Point bloquant : serveur ESP8266 actuel

La source examinée au SHA de base #54 `88f2163c512429e804e96aabbc8b60b71602936b` :
`firmware/src/boot/M9NormalStageA.cpp` collecte Authorization,
authentifie par `server.authenticate()` dans ses handlers existants,
puis applique le JSON télémétrique. **Cela ne prouve pas que le WebServer
n'a pas déjà alloué ou lu les octets POST avant le handler.**
Le code M3-A simule un booléen `SimulatedAuth(digest_verified,
prebody_admitted)` et appelle le contrôle avant le parse body,
mais cette simulation **ne démontre absolument pas** la sécurité Digest
du firmware réel. Aucun ajout de route dans `service.on(...)`.

Le cœur ESP8266 et les bibliothèques épinglées doivent être analysés
ensemble : parsing pré-handler, authentification dans le chemin pré-body,
Digest mutable, limites de lecture, challenge/nonce et synchronisation
avec la télémétrie et l'horloge, réponse bornée et absence de buffer
incontrôlé. Un test C++ natif avec *vraie implémentation* sera requis,
pas une émulation Python déclarée équivalente.

## Matrice de qualifications / gates

| Gate | État M3-A |
| --- | --- |
| Encode/décode strict, borne taille, rejet entrées invalides | HOST simulé, tests à exécuter |
| Appareil/boot/CAS, replay/idempotence dernière transaction | HOST simulé, tests à exécuter |
| ACK et status concordants | HOST simulé, tests à exécuter |
| Coupure avant/après application, timeout, statut perdu, pas de retry | HOST simulé, tests à exécuter |
| Concurrence / vrai verrou Digest et cadence LINK sur Windows | **NON VÉRIFIÉ** |
| Authentification Digest *avant* lecture POST native | **HOLD** |
| Unicité boot/token et budget borné de table replay native | **HOLD** |
| Allocation heap/largest block/stack/IRAM et scheduler natifs | **HOLD** |
| Scènes CLOCK_WEATHER/MONITORING/MUSIC natives 240² | **NON IMPLÉMENTÉES** |
| Météo Internet B5.4, `verified/sdkStackCovered/sharedPoolsCovered/schedulerCovered` | **HOLD**, chantier Codex séparé |
| Acceptation firmware réel et rendu écran physique | **NOT_RUN / aucun GO demandé** |

**Critère de sortie de M3-A :** tests Python de la grammaire et de la
machine de transaction sur Windows et Linux en CI à un SHA exact ; protection
contre I/O et effet de bord ; PR Draft sans fichier de firmware/companion
modifié, et toutes les inconnues natives explicitement conservées.
**Critère de sortie de M3 réel :** preuves natives pré-body Digest,
CAP/ACK/readback, mémoire et concurrence sans faux PASS,
puis approbation propriétaire du candidat exact avant intervention matérielle.

Commande des tests locaux (sans accès réseau) :

`python -m unittest discover -s experiments/link_m3_control_contract -p 'test_*.py' -v`

L'introduction d'un futur adaptateur natif pourra nécessiter une refonte
du profil HTTP plutôt que le simple ajout de `server.on` : aucune
hypothèse de sécurité du modèle HOST ne vaut autorisation de firmware.
