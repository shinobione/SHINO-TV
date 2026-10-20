# B5.4 / M3-R — import du handoff HOST, 20 octobre 2026

## État et périmètre

Import logiciel uniquement sur la branche réservée de PR #85. Le graphe
B5.4 public #72 n'existait pas dans cette branche ; écraser son `firmware/`
B5.3 aurait été incorrect. L'import est donc un overlay vérifié de six
fichiers, exécuté sur une copie isolée du vrai graphe B5.4 public épinglé.
Il n'active aucun endpoint productif ni aucune commande d'écran.

GO et réservation : commentaires #6295828617 et #6296135179 de PR #85.
Départ local/distant propre : `02141e8aa2ace440d47d6974760420ad68e41b79`.
Responsable unique désigné : session Codex Desktop de l'incrément 2/3.
Aucune branche source ni preuve privée modifiée ; aucun merge des PR sources.

## Identité et intégration

- Dépendance publique #72 exacte : `91969aceb45e0c43d44f93a702a3997b57e8f89e`.
  Inventaire public fermé de 439 fichiers vérifié avant copie, inchangé.
- Les six adaptations de l'overlay antérieur sont contrôlées par empreintes
  avant/après et application exacte sans recherche approximative ni fuzz.
- Les en-têtes M3-C/R/BearSSL existants de #85 sont conservés et épinglés.
  Écart de la copie BearSSL de l'ancien labo : une ligne vide finale en plus,
  sans delta d'algorithme. La source Git actuelle est utilisée explicitement.
  CRLF/LF sont normalisés pour les identités du nouveau laboratoire.
- `_parseRequest` conserve la ligne StageA bornée, puis prend la socket avant
  headers. Le Core rend la référence par CLIENT_IS_GIVEN. La même boucle
  `httpBusy` possède la seule Gate M3-C ; pas de second listener/parser HMAC.
- Admissions STA/AP/sous-réseau/config/OTA/journal/ressources préservées.
  HMAC avant tout corps, SHA/framing/FIN ensuite, effacement/libération en sortie.
  Délais comptés depuis le début StageA, sans remise à zéro au transfert.
- Même VerifiedFrame termine par **503**, aucun ACK de commande, ledger
  productif, changement renderer ou mode MUSIC fictif. M3-O reste deny-only.
  Opt-in HOST uniquement, erreur de compilation hors HOST ; aucun firmware
  installable n'est construit par le nouveau runner/workflow.

Voir [README et six diffs](../experiments/link_m3r_b54_handoff/README.md),
`overlay.patch`, `overlay-identities.json`, `PINS.json` et `materialize.py`.
Les licences du graphe source restent incluses dans la dépendance épinglée.

## Validation locale et CI

Les **32 cas HOST d'origine** ont été exécutés sur le code matérialisé depuis
ce worktree : 19 handoff + 13 régressions, zéro FAIL/SKIPPED. Quatre contrôles
supplémentaires d'intégrité de patch passent. Ils couvrent authentification
pré-corps, erreurs/fragments/limites, EOF/timeout/FIN, concurrence/réentrance,
libération de verrou, Digest/journal, quatre mesures LINK/TTL 6 s, horloge,
météo signée/ACK/rejeu et HMAC/Core Updater512/CRC/RTC/flash **simulés en RAM**.
Les régions protégées [0x200000,0x400000) restent intactes dans ce modèle.

Une requête valide consomme exactement 641 octets réseau (466 en-têtes,
175 corps), un accept ; HMAC invalide : zéro corps lu. Listener unique
subsistant après libération. Aucun write SDK/flash ni reboot dans les cas
de handoff ; les écritures OTA des régressions visent uniquement la RAM HOST.

La CI ajoutée récupère la dépendance publique au SHA exact, vérifie son
inventaire et teste l'overlay sur Linux avec le vrai code Core/BearSSL.
**Au moment de ce document, le verdict CI du futur commit reste à obtenir.**
Le verdict final exige les résultats Actions du nouveau SHA et le commentaire
de clôture #85 ; les anciens succès CI ne certifient pas cet import.

## Ressources et limites

Mesure Windows x64 HOST finale sur l'import : Gate **1480 octets**, handle
WiFiClient **32 octets**. EXE avant **502784**, après **521728** octets,
écart **+18944**. `.text` virtuelle **362628→377124 (+14496)** ; `.data`
virtuelle **20628→23348 (+2720)**, dont zones PE initialisées/non initialisées.
Ces nombres incluent simulateur, runtime, instrumentation et alignements.
L'écart EXE initial de cet incrément était +18432 avec un autre chemin
de build ; la nouvelle invocation finale mesure +18944. Les deltas
`.text`/`.data` restent identiques dans les deux invocations. Les reçus privés contiennent les
empreintes et sections réellement produites pour chaque invocation.

**Aucune mesure physique ESP8266**, ni BIN firmware, RAM statique native,
minimum heap/bloc, CONT, frames Xtensa ou WDT n'est déduite. Le heap du
simulateur est injecté. Seuils inchangés : heap 20480, bloc 16384,
CONT 2048, fragmentation 25 %. Pas de qualification de commande productive,
anti-rejeu d'un futur commit de mode, musique, déploiement ou endurance.

## Incidents et garanties

La première préparation documentaire Windows a exigé UTF-8 explicite ; aucune
preuve n'a été modifiée. Le contrôle d'identité a ensuite refusé un pin JSON
calculé sur CRLF : le nouveau pin est explicitement LF, tandis que les six
pins de code et la preuve antérieure restent inchangés. Les refus sont
conservés dans le compte rendu privé distinct, pas masqués en PASS.

Aucun SmallTV/VM/COM contacté, OTA/flash/reboot physique, EXE déployé,
activation météo/écran, effacement de marqueur, force-push ou merge.
Le firmware installé et les 18 autres worktrees sont hors périmètre.
