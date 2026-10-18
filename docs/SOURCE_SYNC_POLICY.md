# SHINO // TV — Synchronisation GitHub / worktrees Windows

**Décision du 19 octobre 2026 : rendre les sources de travail inspectables depuis GitHub sans publier le matériel privé.** Ce protocole complète [PROJECT_STATE.md](PROJECT_STATE.md) et [AGENTS.md](../AGENTS.md). Il n'est **pas** une permission de flash, d'OTA, de déploiement VM ni de fusion des branches produit.

## Le problème à résoudre

Le GitHub `main` est le point d'entrée documentaire, **pas** la copie actuelle du firmware installé. Les worktrees Codex `codex/tv-stabilization-p0`, `codex/b54-lan-weather` et `codex/p0-512-b54-integration` ont été rapportés **locaux uniquement** lors du dernier contrôle. Leurs commits/artefacts ne sont pas consultables par les assistants limités à GitHub ; les captures et rapports ne permettent pas une revue du code source exact.

**Objectif : une PR Draft de revue technique, à HEAD public stable et vérifiable**, contenant le graphe source combiné P0+512/B5.4, le code non secret et les tests. La documentation stable reste sur `main`. Les anciennes PR empilées LINK/M3 et les branches originales ne sont pas fusionnées, rebasées ou écrasées pour cette opération.

## Répartition des sources de vérité

| Surface | Contient | Partage |
| --- | --- | --- |
| GitHub `main` | `AGENTS.md`, `docs/PROJECT_STATE.md`, ce protocole | Public, point d'entrée |
| GitHub PR Draft de l'intégration | Code source public révisable, tests/fixtures synthétiques, rapports expurgés, SHA des **commits publics** | Public **après audit** |
| Worktrees Windows Codex | Commits locaux, sources réelles, historiques et diffs privés | Audit local préalable, pas de publication implicite |
| `research-local/`, BIN/ELF/manifeste/reçus, identités et clés | Artifacts propriétaires, sauvegardes, clés HMAC/OTA, empreintes privées, marqueurs `.attempt` | **Local uniquement**, jamais GitHub public |
| SmallTV / VM Freebox | État physique/réseau | Constat daté et degré de preuve ; aucune synchronisation par Git |

Ne jamais publier les adresses personnelles, MAC/ID matériel, secrets Wi-Fi, mots de passe, clés/certificats privés, identités signées du matériel, binaire privé, dumps, reçus, noms de fichiers locaux sensibles ou logs bruts de transport.

## Opération Codex autorisée — synchronisation du code, pas déploiement

1. **Lire la dernière version de `main` de `AGENTS.md`, `docs/PROJECT_STATE.md` et de ce protocole**, puis `AGENTS.md`, `docs/AGENT_HANDOFF.md`, `docs/ROADMAP.md` dans les worktrees concernés. Les consignes de sécurité les plus strictes restent applicables.
2. **Inventorier les vrais états locaux** (`git worktree list --porcelain`, `git rev-parse HEAD`, `git status --porcelain`, relations d'ancêtres et suivis distants) sans altérer ni nettoyer l'arbre de travail. Relire les PR distantes, leurs bases et le graphe des commits avant de choisir un point d'ancrage. Garder intacts les worktrees P0, B5.4, l'intégration et leurs marqueurs.
3. **Audit de confidentialité de toute la publication potentielle**, pas seulement du fichier HEAD : suivre fichiers modifiés, commits ancêtres nouveaux pour le distant, suppressions et objets pouvant devenir accessibles via un push. Contrôler `git diff`, `git log -p`, listes de fichiers, contenus générés, fichiers suivis jusque dans l'historique, avec un détecteur de secrets disponible ou des contrôles ciblés. **Ne jamais afficher les secrets dans le compte rendu.** `.gitignore` ne protège pas des secrets déjà suivis dans l'historique.
4. **STOP si un secret/artefact privé serait publiable** par un push de la branche locale. Ne pas pousser la branche ni réécrire son historique. Préparer au besoin une **branche publique de copie/export à historique indépendant** contenant seulement une sélection de sources non secrètes et de tests, et garder la correspondance vérifiable avec la version compilée **dans un reçu local privé**. Une copie assainie n'est pas automatiquement le commit source exact du BIN ; déclarer la limite de provenance.
5. **Vérifier l'équivalence fonctionnelle** des fichiers publiables aux sources du candidat, à l'exception *explicitement documentée* de la matérialisation des identités/clefs privées (remplacées par fixtures synthétiques). Si un test a besoin d'une clé propriétaire, fournir une fixture synthétique séparée ; aucun mécanisme de préproduction ne doit permettre une identité factice en production.
6. **Créer UNE branche publique d'intégration isolée et UNE PR Draft** vers la base distante déterminée par `merge-base` et la lisibilité du diff, sans changer `main`, sans forcer de push, sans changer de base des PR existantes et sans merger quoi que ce soit. Vérifier qu'un autre agent ne publie pas la même branche. La PR doit expliquer clairement si elle reflète les commits originaux complets ou un export assaini, avec les tests source exécutés.
7. **Contrôler depuis GitHub, après publication** : SHA du HEAD distant, liste/diff des fichiers, absence de données privées, CI du SHA exact (ou `NON EXÉCUTÉE`), sources clés accessibles. À défaut de contrôle GitHub indépendant, marquer la synchronisation **HOLD**.
8. **Actualiser `docs/PROJECT_STATE.md` via PR documentaire distincte si nécessaire** avec un seul lien vers la PR source canonique, HEAD distant, état du candidat installé (toujours P0+512), B5.4 non installé, blocages et prochaine action. Ne pas recopier un ancien SHA comme s'il venait d'être relu. Pour chaque nouveau jalon, mettre à jour la PR de travail et ses preuves expurgées ; publier dès qu'un commit public peut être revu, sans multiplier les branches provisoires.

## Politique STOP

STOP et rapport concis si : divergence entre source compilée et source à publier, branche/working tree modifié par un autre agent, secret détecté dans les objets poussables, absence de base Git commune claire, outil de scan absent non compensable, CI en échec, risque de perdre des modifications locales, référence privée nécessaire à l'exactitude du code. **Aucun `reset --hard`, force-push, écrasement de branche, cleanup de worktree, suppression de fichiers, `git add -A` aveugle ni merge.**

## Critère d'acceptation

La synchronisation est **PASS** uniquement lorsque :
- un **lien PR Draft réel** permet à un assistant GitHub de lire le code source combiné non secret et les tests nécessaires ;
- un HEAD distant exact, une base clairement documentée et un inventaire des fichiers sont vérifiés **après** push ;
- une vérification de confidentialité inclut aussi **l'historique des commits publiés** ;
- la correspondance et les écarts public/privé sont consignés sans exposer le firmware ou les identifiants ;
- `main` documente la PR canonique et aucun worktree privé n'a été détruit.

Sinon : **PARTIAL/HOLD**, avec une seule action suivante. Il ne suffit **pas** d'une capture ou d'un rapport pour déclarer le code synchronisé.

## Non-objectifs

Cette opération ne valide pas la mémoire physique, l'affichage météo LCD, la liaison réelle VM → SmallTV, le premier transfert OTA physique ni la récupération UART. Le propriétaire devra les autoriser séparément le moment venu.
