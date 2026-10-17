# Exploiter les découvertes OEM dans SHINO // TV

**Guide opérationnel — 17 octobre 2026** · [Dossier technique](README.md) · [Matrice des preuves](EVIDENCE_MATRIX.md) · [Recherche générale](../../RESEARCH.md).

Ce document est **l'entrée à consulter lors d'un incident futur**. Il ne remplace ni les sources, ni les reçus originaux, ni l'état de l'appareil. Les rapports V7–V10 sont des **preuves de rétro-ingénierie statique**, **pas** un nouveau firmware, un correctif installé ou une autorisation d'opération.

**Périmètre / provenance :** archives constructeur publiques V9.0.44 et V9.0.50 ; octets officiels et rapports Windows Capstone des V7–V10 documentés dans les liens ci-dessous. Les versions OEM concernent des images d'application, **pas** des sauvegardes flash complètes. Empreintes et offsets historiques : [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md), [START_AUTH_BOUNDARY_V10.md](START_AUTH_BOUNDARY_V10.md). Ne jamais recopier ces empreintes sur un nouveau candidat sans calcul sur ses vrais octets.

## 1. Résultats réutilisables immédiatement

| Résultat | Preuve et portée | Conséquence utile pour SHINO |
| --- | --- | --- |
| Formats ESP8266 et contrôles CRC/XOR OEM | **PROUVÉ** sur les images OEM publiques V9.0.44/V9.0.50, [matrice](EVIDENCE_MATRIX.md) | Aide à diagnostiquer les BIN mal formés ; ne prouve ni signature ni compatibilité OTA avec le firmware installé |
| Chaînes et chemins HTTP `/update`, `/doUpload` | **PROUVÉ** pour les chaînes ; **HOLD** pour certaines correspondances route/callback, [pistes](UPDATE_ENTRYPOINT_TRACE.md), [références](HTTP_ROUTE_CROSS_REFERENCE.md) | Ne jamais assimiler une chaîne à un endpoint activé ou `/doUpload` à l'OTA firmware |
| Callbacks GET/OPTIONS/POST et défi Basic 401 | **FORTEMENT ÉTAYÉ / OBSERVÉ EN DÉSASSEMBLAGE**, [pointeurs](CALLBACK_POINTERS_V7.md), [V7](POST_CALLBACK_V7.md) | Un 401 final n'est pas une preuve de contrôle **avant réception/écriture** |
| Branches upload START/WRITE/END | **PARTIEL** (états 0/1/2 proches de `HTTPUploadStatus`), [V8](POST_UPLOAD_STATIC_V8.md) | Vérifier l'état de session et l'autorisation pour *chaque* phase, et les interruptions |
| Appel candidat `UpdaterClass::write` | **TRÈS FORTE CORRESPONDANCE STATIQUE** des champs/erreurs, pas une preuve d'appel atteint, [V9](UPDATER_CALLTRACE_V9.md) | Le moteur `Updater` n'authentifie pas l'appelant : le firmware SHINO doit le faire |
| Champ `_authenticated` et garde WRITE | **PARTIEL** : écriture candidate en START ; le garde direct WRITE décodé teste un pointeur serveur, **pas** une lecture visible de `_authenticated`, [V10](START_AUTH_BOUNDARY_V10.md) | Ne déclarer **ni vulnérabilité OEM** ni autorisation absente en amont ; dans SHINO, garder une autorisation indépendante effective avant toute écriture |
| `Update.begin` / `Update.end` / eboot | `begin` et END attribués **provisoirement** dans OEM ; API publique Core étudiée ; OEM activation/boot **HOLD**, [V9](UPDATER_CALLTRACE_V9.md), [V10](START_AUTH_BOUNDARY_V10.md) | Distinguer transfert, staging, commit eboot et nouveau firmware réellement exécuté |
| Wi-Fi, fuseau, DST, horloge, LCD | **Notes constructeur / références tierces** ; fonctions OEM non désassemblées, [matrice §F](EVIDENCE_MATRIX.md) | Pistes d'inspiration uniquement ; **aucune capacité LINK ou LCD supplémentaire démontrée par V7–V10** |

**Précision essentielle :** dans le **Core public Arduino ESP8266 3.1.2**, `end(true)` peut ajuster la taille à la progression. C'est une propriété **du Core public**, pas une démonstration d'un défaut exploitable dans OEM. L'implémentation SHINO étudiée utilise `end(false)` avec vérifications préalables ; toujours revérifier cela au **HEAD exact** du firmware à auditer.

## 2. En cas de problème : où aller en premier ?

| Symptôme / objectif | Consulter d'abord | Contrôle SHINO concret |
| --- | --- | --- |
| OTA SHINO rejetée, bloquée ou `FAILED_NO_COMMIT` | [Guide V10 auth/session](START_AUTH_BOUNDARY_V10.md), [Breakthrough SHINO](../../SHINO_HTTP_OTA_BREAKTHROUGH.md) | Relire le vrai `ota/firmware/Normal.cpp` + `ota/firmware/ShinoHttpOta.h` au commit concerné, les statuts, tests et reçus ; contrôler trames et lectures flash alignées, pas d'essai physique automatique |
| Réponse OTA perdue / résultat `UNKNOWN_NO_RETRY` | [Contrats OTA V10](START_AUTH_BOUNDARY_V10.md), [PR #51 — correction Windows](https://github.com/shinobione/SHINO-TV/pull/51) | Conserver `.attempt` et reçu, diagnostiquer **sans renvoyer le POST** ; jamais régénérer un paquet pour contourner le verrou |
| Image incompatible, mauvais offset ou risque LittleFS | [Formats/CRC V44/V50](EVIDENCE_MATRIX.md), [audit layout](../../COMPARATIVE_FLASH_LAYOUT_AUDIT.md) | Vérifier **BIN, linker exact, taille, manifestes, staging, frontières LittleFS et 24 KiB réservés** ; ne jamais transposer les offsets OEM `4m3m` au layout SHINO `4m2m` |
| Retour au firmware constructeur / récupération d'un brick | [Manifeste OEM V9.0.44](../../../recovery/factory_ota_v9_0_44.json), [références récupération](../../V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md) | Séparer **BIN OEM applicatif** et **backup privé intégral 4 MiB** ; ne prétendre ni restaurer LittleFS par une image app-only, ni disposer d'un rollback eboot automatique |
| Connexion Freebox, AP de secours, persistance Wi-Fi | [Notes OEM](EVIDENCE_MATRIX.md), [audit B5.1, branche distincte (PR #47)](https://github.com/shinobione/SHINO-TV/blob/244334edac07701dc25b5ffc494715152ae1bfa5/docs/SHINO_B51_HOME_LAN_RECOVERY.md) | Analyser le SDK ESP8266 et le code LAN réellement installé ; **les notes OEM ne démontrent aucun algorithme Wi-Fi** |
| Horloge/date hors ligne, fuseau, DST | [Notes versions OEM](EVIDENCE_MATRIX.md), [état SHINO](../../AGENT_HANDOFF.md) | Diagnostiquer B5.3/B5.4 et LINK **indépendamment**. Le propriétaire a confirmé le 17 octobre 2026 l'heure/date visibles même PC éteint sur B5.3 ; mécanisme et SHA installé non vérifiés ici |
| Rendu LCD, rotations, scènes, pochettes | [Matériel LCD et limites](EVIDENCE_MATRIX.md), [références 240×240](../../design-reference/README.md) | Utiliser les pilotes et mesures SHINO ; **aucune routine LCD OEM n'a été démontrée par ces reçus** |

> **Priorité produit :** le propriétaire confirme B5.3 fonctionnel (mesures, heure/date, maintien de l'heure PC éteint) ; Codex travaille sur B5.4 séparément. Cet état provient du **retour propriétaire**, pas d'une lecture réseau ou du firmware installé réalisée ici. Ne pas réinstaller B5.1/B5.2, déstabiliser B5.3, ni perturber la branche/worktree B5.4 pour exploiter cette recherche.

## 3. Parcours des preuves V7 → V10

1. **Localisation des routes et des callbacks** : [entrée `/update`](UPDATE_ENTRYPOINT_TRACE.md), [routes HTTP](HTTP_ROUTE_CROSS_REFERENCE.md), [pointeurs V7](CALLBACK_POINTERS_V7.md). Identification de candidats, avec incertitudes sur le graphe d'appels.
2. **V7** : [POST et Basic 401](POST_CALLBACK_V7.md). Chemin de défi visible ; pas de preuve d'autorisation pré-écriture.
3. **V8** : [machine d'états et appels POST B](POST_UPLOAD_STATIC_V8.md). Correspondance partielle avec `HTTPUploadStatus`.
4. **V9** : [trace Updater WRITE/END](UPDATER_CALLTRACE_V9.md). `write` fortement étayé, END incomplet.
5. **V10** : [START, `_authenticated`, BEGIN candidat et contrat Core](START_AUTH_BOUNDARY_V10.md). Contrôle complet de l'autorisation avant WRITE et acceptation OEM **HOLD**.

**Chronologie :** le [README de recherche](README.md) et la [matrice V44/V50](EVIDENCE_MATRIX.md) ont été initiés le 16 octobre ; certaines phrases historiques sur les fonctions « non identifiées » sont **dépassées ou nuancées** par les reçus V7–V10 du 17 octobre. Les garder pour provenance, mais utiliser les conclusions les plus récentes pour chaque question.

## 4. Méthode de réutilisation : symptôme → preuve → correction

1. Identifier le firmware **réellement exécuté**, sa branche/code source **distincts**, le commit HEAD, l'état du working tree, les PR actives et CI du SHA exact. **NON VÉRIFIÉ** si ces sources manquent ; ne pas reconstruire l'état installé depuis une ancienne PR.
2. Énoncer le symptôme concret et la condition de reproduction ; choisir **un** document du tableau ci-dessus et relire ses preuves originales, sans promouvoir une hypothèse en PROUVÉ.
3. Comparer avec les fonctions **SHINO réellement exécutées**, et décider si l'analyse OEM fournit un **écart fonctionnel démontré**. Si non : **aucun chantier de rétro-ingénierie supplémentaire**.
4. Corriger la cause dans une branche coordonnée et isolée de Codex B5.4. Tester les cas nominaux, erreurs/interruptions, authentification, réseau LINK, mémoire, LittleFS, boot/OTA selon la portée, sans baisser les seuils. Tests HOST/CI = **SIMULÉ**, pas preuve physique.
5. Ne proposer de manipulation de l'unique SmallTV qu'après vérification de ses prérequis et **accord explicite nouveau pour l'opération et le candidat SHA exacts**. En OTA incertaine : **STOP, jamais de retry automatique**.

**Ne jamais publier dans ce dépôt :** sauvegarde complète du propriétaire, images BIN privées, identifiants Wi-Fi/HTTP/HMAC, marques `.attempt`, reçus contenant des informations privées ou logs non expurgés. Les rapports existants sont la référence documentaire ; les ZIP de reçus Windows restent hors Git.

## 5. Critère de déclenchement d'une nouvelle analyse OEM

**GO recherche bornée** seulement si un bug SHINO reproductible nécessite une information OEM absente (p. ex. un comportement de staging constructeur pour une récupération impossible autrement), avec un résultat attendu testable. **STOP recherche** si la réponse est déjà dans les sources SHINO/Core, si la question est une amélioration visuelle/LINK non reliée au code constructeur, ou si la nouvelle analyse n'a pas d'effet pratique identifié.

**En bref :** utiliser les découvertes comme **bibliothèque de diagnostic et de contraintes**, pas comme justification pour reconstruire une OTA déjà opérationnelle ni pour interrompre les fonctionnalités B5.4.
