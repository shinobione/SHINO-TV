# SHINO // LINK M2 — Menu tray des modes, aperçu PC exclusivement

**17 octobre 2026 — branche de travail isolée.**

## Périmètre livré

L'évolution M2 repose sur M1 / PR #53 (protocole des modes uniquement HOST).
Elle ajoute un menu radio pystray dans le **même** processus SHINO // LINK,
sans changer son worker, les émissions métriques, son cadenceur, sa
configuration, son autostart ni ses fonctions réseau :

- Automatique (défaut à chaque nouveau démarrage).
- Horloge / Météo.
- Monitoring PC.
- Musique.
- Ligne d'aperçu PC recalculée lors de l'ouverture/actualisation du menu.
- Mention permanente : « SmallTV : aucun changement envoyé ».
- Ouverture du tableau de bord SHINO // TV et fermeture existantes préservées.

Sélection manuelle : **prioritaire sur tous les changements de contexte**,
jusqu'à sélection explicite d'Automatique. Les états d'attente
Monitoring indisponible et Lecture musicale non vérifiée **n'effacent pas**
la préférence courante. Radio checkmarks dynamiques.

Le module companion/link_mode_tray.py isole le contrôleur thread-safe et la
construction du menu; companion/shino_link.py ne change que run_tray et
importe ce module paresseusement dans ce chemin. Les actions CLI
--run / --once / --configure / --autostart sont inchangées.

## Limites fondamentales

Cette évolution n'est PAS encore un contrôle de l'écran réel du SmallTV.
Ni l'API de modes authentifiée, ni l'ACK d'application, ni les nouveaux
écrans natifs n'existent ici. Un appui menu **ne doit en aucun cas**
contacter un endpoint firmware (M3 et M4 requièrent d'autres gates et un GO
matériel séparé). Le choix actuel est mémorisé seulement dans la RAM du
processus, sans fichier de préférence ni registre ajouté.

La seule observation automatique de contexte branchée en M2 est la
**fraîcheur de la dernière télémétrie acceptée** : last_success avec horloge
monotone du worker existant, fenêtre 6 000 ms incluse, et refus
des timestamps futurs/non numériques. Ce signal atteste un ACK Windows
récent, PAS une scène active et PAS un état physique lu par GET.
La sortie TIME/WEATHER reste invalide par défaut : les valeurs ne sont
pas inférées à partir de l'horloge Windows ou d'une météo absente.
**La musique GSMTC n'est pas encore reliée au menu** : les scènes proposées
ne revendiquent pas un Spotify réellement PLAYING, même s'il joue.
Le fallback « Lecture musicale non vérifiée » ne prétend pas « pas de musique ».

B5.3 LEAN est installée et opérationnelle au périmètre observé par le
propriétaire (horloge hors PC, mesures à la reconnexion). M2 ne doit
ni rétrograder cet état, ni prendre le relais de Codex sur B5.4.
Le travail B5.4 se poursuit indépendamment : **aucune modification, fusion,
rebase ou installation dans ses branches/worktrees**, aucune activation des
nouveaux modes sur le PC du propriétaire par cette PR.

## Tests et reproductibilité

Depuis la racine, Python 3.10+ :

    python -m unittest discover -s companion -p test_link_mode_tray.py -v
    python -m unittest discover -s companion -p test_link_display_modes.py -v
    python -m unittest discover -s companion -p test_shino_link.py -v

Les tests M2 utilisent un faux pystray/icone, sans UI ni matériel Windows,
et couvrent cases radio, contexte, préférences manuelles, fraîcheur 6s,
types erronés, concurrence, interdiction d'I/O sur clic, actions Web/Exit.
Ils ne constituent PAS un smoke physique Windows. La CI doit être contrôlée
sur le SHA exact après push; la réussite d'un build Linux ne démontre pas le
rendu visuel du tray Windows.

## Gates après M2

1. Revue avec Codex de la compatibilité de la branche B5.4 et des versions
   réellement exécutées par LINK, sans fusion implicite.
2. Qualification manuelle Windows de l'ouverture du tray, quatre boutons et
   fermetures en maintenant l'envoi métrique.
3. Détection musicale GSMTC locale et présentation validée du status,
   sans démarrer un second émetteur.
4. Décision distincte sur persistance optionnelle des modes.
5. M3 : protocole versionné et authentifié de contrôle/ACK, avec budgets
   firmware et consentement exact-candidat, avant toute action SmallTV.

Statuts matériels et signatures de BIN : NON VÉRIFIÉS par cette PR.
