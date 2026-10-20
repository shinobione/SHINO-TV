# SHINO // LINK Windows V1 — livraison du 21 octobre 2026

EXE x64 réellement construit sous Windows avec Python 3.12.10 / PyInstaller
6.22.0, **17 588 605 octets**, SHA-256 :

`9d2fdde369362061cefbf9fe4ecbd9016e6c7bea65012fed001b68a75e926df6`

Chemin local isolé de livraison :

`C:\Users\jerry\SHINO-TV-V06-AUDIT\research-local\SHINO-LINK-Windows-V1-20261021\release\SHINO-LINK.exe`

L'EXE contient son interpréteur, psutil, pystray, Pillow et l'icône ; aucun
Python externe n'est requis. Build local non installé, non signé. Le dossier
contient aussi `BUILD-MANIFEST.json`, le journal de build et les preuves de test.
L'EXE peut être copié seul. Les deux processus du format onefile (chargeur et
application) ne sont pas deux senders : un seul worker métriques est lancé.

## Lancement manuel sûr

**Essai sans configuration, sans capteurs, sans réseau et sans sender :**
Win+R, coller cette commande puis Entrée :

```text
"C:\Users\jerry\SHINO-TV-V06-AUDIT\research-local\SHINO-LINK-Windows-V1-20261021\release\SHINO-LINK.exe" --offline-preview
```

Le tray indique `APERÇU HORS LIGNE · DISCONNECTED`. Clic droit pour consulter
l'état, essayer les choix d'aperçu PC et quitter. Le dashboard est désactivé
dans cet aperçu. Cet essai ne remplace ni ne stoppe le LINK actuellement installé.
L'aperçu possède un verrou distinct et n'est jamais un deuxième émetteur.

**LIVE non exécuté et non autorisé par cette livraison :** un double-clic sans
option lance volontairement le sender avec
`%LOCALAPPDATA%\SHINO-TV\link.json` et son fichier d'identifiants privé existant.
Le verrou historique `SHINO-TV/worker-instance` est acquis AVANT lecture de
configuration et démarrage ; si le LINK installé le détient, l'EXE affiche
une erreur explicite et n'envoie rien. Une mise en route LIVE doit être décidée
séparément par le propriétaire, après contrôle de l'EXE exact et arrêt volontaire
de l'ancien sender. Aucun arrêt de l'ancien LINK n'a été effectué ici.

Pour une future configuration explicite, l'EXE accepte
`--configure --host IP_PRIVÉE --credentials-file CHEMIN_ABSOLU_PRIVÉ`.
Le schéma existant est conservé ; aucun mot de passe sur la ligne de commande,
aucune copie des identifiants dans l'EXE ou `link.json`. Pas d'adresse embarquée
autre que le défaut historique inactif tant qu'aucun envoi n'est lancé.

## Fonctionnement V1

- Tray natif : CONNECTED / RETRYING / DISCONNECTED, couleur et infobulle,
  état/counters accessibles, dashboard uniquement sur clic, Quitter joint le
  worker avant de libérer le verrou. Aucun worker réseau supplémentaire.
- Même `LinkEngine`, collecte CPU/RAM psutil et GPU/GPU temp NVIDIA, sérialisation,
  POST métriques, Digest, locks, délai 3 s, cadence 2 s et backoff 2/4/8/16/30 s.
  TTL 6 s inchangé. Aucun changement des sources historiques.
- NVIDIA requiert le pilote et `nvidia-smi` existant sur PATH. Absence =
  `gpu_available=false` selon le protocole historique, signalée dans l'état ;
  les zéros de repli du protocole ne sont pas qualifiés de mesures GPU valides.
  CPU et RAM continuent. Aucun programme console lancé par la collecte.
- Horloge B5.2 conservée opt-in par `--clock-b52-host IP` pour une cible déjà
  vérifiée ; pas activée implicitement, état visible dans le menu.
- Modes Automatique / Horloge-Météo / Monitoring / Musique : **aperçu PC uniquement**,
  mention permanente « SmallTV : aucun changement envoyé » ; musique réelle non reliée.
- Diagnostic firmware #83 : menu désactivé, motif coordination OTA HOLD ;
  module exclu du bundle. Aucun GET de diagnostic déclenché.
- Autostart compatible EXE, chemin réel `sys.executable` et quoting Windows ;
  `--autostart enable|disable|status` uniquement sur demande explicite. Refus
  d'écraser/supprimer une entrée différente, y compris le launcher Python actuel.
  Option d'horloge explicite préservée dans la commande si demandée.
  Aucun registre, tâche planifiée ou autostart réellement modifié pendant la livraison.

## Preuves réellement exécutées

**155 tests de comportement Windows/HOST PASS** : V1 12, LINK 28, menu 15,
politique modes 13, publisher clock 21, clock loopback 7 (dont cadence réelle
60 s), clock transport 17, sender 19, collecte 3, coordination 7, Win32 tray 2,
inspecteur historique sur faux transport 11.

**7 tests d'identité historique PASS sur export des blobs Git exacts LF.**
Leur exécution brute sur le checkout Windows CRLF échoue : cause démontrée
par égalité blob Git / fichier normalisé, sans modifier fichiers, pins ou tests.
Les sources historiques de `shino_link.py`, menu, Digest et clock sont inchangées.

**Vrai EXE final : PASS**, copie de l'EXE seul dans un chemin avec espaces,
PATH réduit à System32, `PYTHONPATH` / `PYTHONHOME` / venv supprimés :

- PE x64, sous-système GUI et absence de console, icône embarquée lisible.
- Création réelle tray HWND/HMENU Win32 ; callbacks modes, état, dashboard et Quitter.
- Même moteur et vrai code de POST LINK / verrou Digest sur faux HTTP :
  RETRYING → CONNECTED → RETRYING → CONNECTED ; quatre mesures fixture vérifiées.
- Blocage socket/DNS : zéro tentative réseau ; collecte réelle CPU/RAM séparée
  hors ligne, aucune mesure fixture présentée comme celle du PC ou du SmallTV.
- Un worker, garde anti-double worker, exclusion par verrou d'un second EXE,
  reprise du verrou après sa sortie et fermeture complète du worker.
- Aperçu hors ligne réel : tray visible, aucun worker, dashboard désactivé, sortie propre.
- Boîtes Windows réelles vérifiées et fermées : config absente, identifiants absents,
  arguments invalides ; codes de sortie 1 / 1 / 2. Correction du harnais de
  fermeture WM_COMMAND → WM_CLOSE après timeout ; aucun changement produit associé.

Preuves locales : `tests/FROZEN-SMOKE.json` et `tests/EXE-TESTS.json` dans le
dossier livré. **OWNER_DESKTOP_SMOKE=NOT_RUN**, aucune validation humaine de
l'apparence Explorer, aucun test LIVE NVIDIA/SmallTV, aucun test de session
Windows/autostart. Les preuves automatisées Win32 ne remplacent pas ces essais.

## Périmètre et reproduction

Source : branche existante `feature/link-m3r-unified-integration-20261019`,
Draft PR #85, départ local/GitHub `bbec50e19e4fc4a7d91f9b63a52d2dfbdb43ab63`,
26 workflows terminés SUCCESS avant édition. Autre chat de développement inactif
au contrôle de coordination. Aucun nouveau chantier, branche ou PR.

Patch HMAC local incrément 8 et ses preuves préservés, non importés/non committés ;
inventaire initial de **8 589 fichiers**, comparaison intégrale SHA-256 avant/après.
Les notes HMAC locales de ROADMAP restent hors commit Windows. Aucun firmware,
VM, SmallTV, identifiant, installation existante, sauvegarde ou marqueur modifié.
La CI du commit final doit être vérifiée séparément ; ce rapport local n'est
pas une affirmation anticipée de CI verte.

Reconstruction Windows dans un venv isolé, sans secret :

```text
python -m pip install -r companion/requirements-windows-build.txt
python tools/build_link_windows.py --output C:\chemin\nouveau-dossier
python tools/test_link_windows_exe.py --exe C:\chemin\nouveau-dossier\SHINO-LINK.exe --output C:\chemin\nouveaux-tests
```

Les sources du bundle sont copiées par allowlist dans le dossier de build.
`provision_home_wifi.py` est inclus pour la classe Digest réutilisée par
l'horloge historique ; aucune commande de provisionnement n'est exposée par
l'entrée Windows. Configuration et secrets sont recherchés uniquement dans le
profil utilisateur réel lors d'un lancement LIVE volontaire, jamais dans
`sys._MEIPASS`, le CWD ou le répertoire EXE.

Packaging fondé sur les documentations officielles
[runtime frozen](https://pyinstaller.org/en/stable/runtime-information.html) et
[mode windowed](https://pyinstaller.org/en/stable/usage.html).
Livraison puis STOP ; M3-R et coordination OTA #83 demeurent HOLD.
