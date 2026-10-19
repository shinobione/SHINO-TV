# SHINO // TV — Règles de reprise pour assistants et agents

**Première lecture obligatoire : [état opérationnel daté](docs/PROJECT_STATE.md).** Ensuite consulter les instructions/guards plus détaillés de la branche active (`docs/AGENT_HANDOFF.md`, `docs/ROADMAP.md`, code et tests). Les documents historiques ne décrivent pas nécessairement le firmware installé.

## Publication des sources et reprise entre outils

- Pour les tâches P0+Updater512 / B5.4, lire **[la politique de synchronisation source](docs/SOURCE_SYNC_POLICY.md)** et **[la mission Codex #71](https://github.com/shinobione/SHINO-TV/issues/71)** avant de demander des captures ou d'inférer l'état local depuis GitHub.
- Une PR Draft GitHub inspectable n'existe **pas encore** pour le commit local combiné au checkpoint. Un rapport Codex ne remplace pas la relecture de sa source.
- Publier uniquement les sources et tests non secrets après audit du **contenu et de tout l'historique poussable** ; s'il y a un secret ancestral, ne pas pousser l'historique local, préparer un export public assaini et déclarer ses limites de correspondance au candidat privé.
- **Ne jamais** synchroniser BIN/ELF, secrets, identité de l'appareil, reçus, sauvegardes, `research-local/` ou marqueurs privés dans le repo public.
- Préserver les worktrees/branches Codex et les PR existantes ; aucune fusion/force-push. Une fois une PR de source réellement publiée, lier HEAD/CI/base exacts au checkpoint et utiliser cette PR comme référence pour les revues distantes.

## Source de vérité
- Identifier séparément **GitHub**, **worktree Windows**, **binaire privé/manifeste/reçu** et **matériel/VM**. Aucune synchronisation implicite.
- Vérifier branche, HEAD, working tree, PR actives, dépendances et CI du commit exact **avant toute modification**. Respecter le travail parallèle de Codex.
- Associer chaque état à sa preuve et date : PROUVÉ FICHIER, OBSERVÉ PROPRIÉTAIRE, HOST/SIMULÉ, HYPOTHÈSE, HOLD/NON VÉRIFIÉ. Build PASS n'implique pas boot ; OTA transférée n'implique pas acceptation postboot.
- Si une décision explicite récente du propriétaire contredit un ancien document, la décision récente prévaut ; la consigner dans `docs/PROJECT_STATE.md` avec sa portée, **sans falsifier l'historique**.

## Garde-fous
- Aucune OTA/écriture flash/UART/RTC/SDK/LittleFS, redémarrage, modification Wi-Fi, activation ou déploiement VM Freebox, merge ou action destructive sans un GO spécifique récent pour **l'action et le candidat exacts**. Un ancien « GO » n'est jamais une autorisation permanente.
- Pas de force-push, `reset --hard`, suppression de backup/MASTER/VERIFY/reçu/marqueur `.attempt`, ni d'envoi de secrets. Eboot n'offre pas de rollback automatique ; OTA incertaine = STOP, jamais retry automatique.
- Préserver le SmallTV-Ultra ESP8266 flash 4 MiB, layout `4m2m` **selon les vrais artefacts**, LCD 240×240, quatre mesures SHINO LINK, HMAC/Digest, LittleFS, horloge et voie de récupération.
- Ne pas abaisser de seuil pour obtenir PASS ni faire passer des simulations pour des validations physiques.
- Toujours vérifier sur le code local réel les commandes Python/PowerShell avant de les transmettre ; ne pas demander au propriétaire de refaire des vérifications automatisables.

## Déroulé
1. Lire le checkpoint opérationnel puis les sources pertinentes ; résumer **acquis / blocage / prochaine action** sans redemander les éléments déjà connus.
2. Traiter **la tâche demandée**, pas inventer de nouveaux sous-projets.
3. Tester hors ligne, rapporter fichiers/commit/CI/mesures **vérifiés seulement**.
4. Actualiser le checkpoint à chaque changement réel, avec preuve, date et degré de certitude.
