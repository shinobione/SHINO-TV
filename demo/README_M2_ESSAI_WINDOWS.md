# SHINO // LINK — Essai visuel Windows M2

**Outil d'essai distinct de SHINO // LINK — 17 octobre 2026**

## Ce que cet exécutable FAIT

Le programme `SHINO-LINK-M2-ESSAI.exe` ouvre une **icône de démonstration**
dans la zone de notification Windows. Il reprend la logique exacte du menu
M2 de la PR #54 (4 modes exclusifs, prévisualisation, choix automatique/manuels)
et propose deux interrupteurs de simulation :
« PC connecté (simulé) » et « Musique en lecture (simulée) ».

Le bandeau **DÉMONSTRATION 100% LOCALE** et la mention
**SmallTV : aucun changement envoyé** doivent rester visibles.

## Ce qu'il NE FAIT PAS

- Ne lance pas SHINO // LINK, ne remplace pas l'installation en service.
- Ne collecte pas les métriques réelles du PC et ne détecte pas Spotify.
- Aucun réseau, HTTP, mot de passe, fichier `link.json`, registre ou autostart.
- Aucun accès SmallTV, OTA, flash, LittleFS, Wi-Fi, ni redémarrage.
- Aucun état sélectionné n'est conservé après fermeture.
- N'installe pas d'application et ne modifie pas B5.3 ou B5.4.

L'exécutable est portable, **non signé** par un éditeur et créé par
PyInstaller sur un runner Windows. Un avertissement SmartScreen éventuel ne
constitue pas une preuve de malveillance ni une garantie d'innocuité :
vérifier l'origine GitHub et l'empreinte téléchargée avant toute exécution.

## Essai manuel sur le bureau du propriétaire

1. Télécharger l'artifact **SHINO-LINK-M2-ESSAI-WINDOWS** depuis les
   Actions de la PR d'essai, puis extraire le ZIP dans un dossier temporaire.
2. Vérifier l'empreinte SHA256 du fichier EXE contre le fichier SHA256 inclus.
   Ne jamais utiliser un EXE provenant d'une autre source.
3. Double-cliquer `SHINO-LINK-M2-ESSAI.exe`. **Aucune console ne doit rester
   ouverte**. L'icône de démonstration possède un **point doré** (distinct
   de l'icône SHINO // LINK en service).
4. Dans la zone de notification, cliquer si besoin sur la flèche **^**,
   puis **clic droit** sur l'icône SHINO // LINK — ESSAI LOCAL (SIMULÉ).
5. Sous **Mode d'affichage (aperçu PC)**, sélectionner successivement
   Automatique, Horloge / Météo, Monitoring PC et Musique. Le point radio
   sélectionné et la ligne **Aperçu PC** doivent suivre.
6. Sous **Contexte SIMULÉ**, cocher/décocher le PC et la lecture musicale :
   en AUTO musique en lecture + PC connecté donne Musique ; musique OFF +
   PC connecté donne 4 cartes ; PC OFF donne Horloge/Météo en aperçu. Un
   mode manuel doit résister à ces changements.
7. Cliquer sur **Quitter cet essai**. L'icône de démonstration disparaît.
   Le SHINO // LINK installé poursuit son fonctionnement normal.

Les libellés d'aperçu ne constituent pas un LCD physique : la météo et
l'heure réelles du SmallTV ne sont pas lues.

## Reproduction de la construction

Source : `demo/link_m2_owner_preview.py`.
Dépendances : `companion/requirements-link.txt`; compilation Windows avec
PyInstaller dans `.github/workflows/link-m2-owner-demo.yml`.

- `python demo/link_m2_owner_preview.py --self-test` : diagnostic source,
  sans ouverture d'icône.
- `SHINO-LINK-M2-ESSAI.exe --self-test` : diagnostic de l'EXE empaqueté,
  exécuté par la CI sous Windows sans ouverture de tray.
- `SHA256.txt` : empreinte calculée sur les octets finaux **après** build,
  jamais une taille/SHA déduite du code.
- PASS dans une CI Windows n'est **pas** PASS sur le bureau de l'utilisateur.

**Statut : OWNER_DESKTOP=NOT_RUN** jusqu'à retour explicite du propriétaire.
