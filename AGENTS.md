# SHINO // TV — Règles de reprise pour assistants et agents

**Première lecture obligatoire : [état opérationnel daté](docs/PROJECT_STATE.md).** Ensuite consulter les instructions/guards plus détaillés de la branche active (`docs/AGENT_HANDOFF.md`, `docs/ROADMAP.md`, code et tests). Les documents historiques ne décrivent pas nécessairement le firmware installé.

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
