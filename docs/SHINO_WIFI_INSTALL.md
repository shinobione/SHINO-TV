# SHINO // INSTALL — décisions produit pour les mises à jour Wi-Fi

**Décision utilisateur, 9 octobre 2026.** Le besoin est **un choix de BIN dans Windows, un bouton Installer, puis un SmallTV qui redémarre sur la nouvelle version, sans UART/CH340 pour les mises à jour ordinaires**. Ce document prévaut sur les ambitions non demandées d'un gestionnaire OTA « industriel ». Les recherches signées de PR42 S/T restent disponibles, mais ne sont pas un prérequis à dérouler mécaniquement.

## Architecture candidate SIMPLE — à qualifier, pas encore retenue comme firmware livrable

**Piste prioritaire : une petite adaptation locale du protocole ArduinoOTA du Core ESP8266 3.1.2, restreinte à l'APPLICATION (U_FLASH), sur le Wi-Fi privé SHINO existant**, avec un installateur Windows minimal. L'outil PC inspecte le BIN et le manifeste de build compatible 4m2m **avant** d'ouvrir une session d'installation. Le SmallTV accepte uniquement un upload application identifié et authentifié ; il ne doit jamais admettre U_FS, formatage LittleFS, fichiers génériques ou update à partir d'Internet. Une entrée CLI sûre en secours ; GUI « Choisir / Vérifier / Installer / Résultat » comme interface principale.

**Pourquoi cette voie mérite le premier essai :**
- ArduinoOTA existe déjà dans le Core épinglé, permet l'envoi d'un firmware depuis un PC et ne dépend pas d'un gros POST HTTP sur /status ou /metrics. Un listener de maintenance UDP/TCP dédié peut être plus simple à isoler qu'un second chemin d'upload dans le parseur HTTP StageA.
- **Pendant une mise à jour**, on peut afficher « Mise à jour en cours » et suspendre temporairement les valeurs LINK. Il est inutile d'exiger 915 GET simultanés à une écriture flash : les métriques doivent reprendre après.
- On peut conserver **le serveur HTTP StageA actuel sans modifier ses routes**, le layout 4m2m et le LittleFS ; l'étape décisive sera la mesure réelle de la mémoire d'un graphe StageA + service d'update, comparé au StageA seul.

**Ce que l'on refuse tel quel, d'après les sources du Core 3.1.2 :**
- `ArduinoOTA.cpp` accepte **U_FLASH et U_FS** et déclenche `Update.begin(_size, _cmd)` **avant** le callback `onStart`. Un simple callback `if (getCommand()==U_FS)` serait trop tardif : il faut un garde-fou *avant* `Update.begin`, via un adaptateur/minifork audité sans modifier le Core installé.
- `ESP8266HTTPUpdateServer-impl.h` expose une interface pour l'application **et** le filesystem, supporte Basic/OPTIONS ouverts et utilise `Update.end(true)`. Pas d'activation « juste pour essayer ».
- L'ESP8266 `Updater`/eboot peut copier la nouvelle application au redémarrage, mais **n'offre pas de rollback atomique** si l'alimentation coupe pendant la copie. Ce risque ne disparaît pas avec le protocole le plus complexe.
- L'approche RSA signée S/T a montré **+4204 B statiques**, **10839 B de payloads dynamiques natifs** et une admission stack/heap non démontrée. Ne pas la faire passer pour le prix minimal d'une simple MAJ Wi-Fi.

**Sécurité proportionnée mais réelle :** réseau WPA2 privé uniquement, authentification distincte des lectures HTTP/du cookie navigateur, mot de passe de maintenance fort et privé généré pour le device, limites strictes sur taille/identité/format application, vérification d'intégrité et refus définitif sur erreur. Pas d'Internet public ni de commande distante sans consentement PC explicite. Une session authentifiée par mot de passe n'est **pas équivalente** à une signature RSA du fournisseur ; documenter cette limite. Le plan Windows ne fait jamais confiance au seul nom de fichier : BIN identifié au manifeste exact de build et au layout 4m2m. L'appareil ne doit pas pouvoir écraser LittleFS même si le PC envoie une mauvaise commande.

## Étape de développement unique à exécuter avant le moindre flash

**Livrable : « SHINO Wi-Fi Update — candidate simple »**, plutôt qu'une nouvelle mission à lettres.

1. **Prototype offline contrôlé** : instrumenter un adaptateur OTA application-only dérivé du mécanisme Core. Refuser `U_FS` **avant** l'ouverture d'une écriture, limiter tailles et interfaces, autoriser seulement le Wi-Fi privé et l'identité de mise à jour dédiée. Aucun envoi réseau au SmallTV réel ; utiliser clients/sink fictifs en tests.
2. **Deux compilations réelles à entrées identiques** : StageA 4m2m public *sans* et *avec* adaptateur. Mesurer BIN, RAM statique, buffers dynamiques, fragmentation admissible et stack, sans perdre les planchers physiques existants (heap >= 20480, largest block >= 16384, stack >= 2048, frag <=25%). **Ne pas promettre un PASS physique depuis une simulation.**
3. **Un petit installateur Windows** qui choisit un fichier, vérifie le manifeste compatible et l'empreinte exacte, affiche la taille, le device cible et une confirmation, puis utilise le protocole seulement si un récepteur compatible est explicitement détecté. Pas de vraie installation dans les tests/CI. Un échec est affiché sans auto-réessai ni déclaration de succès non confirmée.
4. **Finir par une décision concrète** :
   - **GO POUR CANDIDAT TEST** si l'upload application-only est correctement sécurisé, les ressources hors ligne plausibles et le firmware sait reconnaître/encadrer le format. Cela **n'autorise pas** une installation physique.
   - **NO-GO** si U_FS ne peut être interdit avant toute écriture, si le Core ne permet pas d'abandonner proprement, si la mémoire ne tient pas, ou si la récupération est jugée trop risquée. Donner un seul motif principal ; ne pas repartir automatiquement dans du RSA lourd.
5. **Transition** : le firmware StageA **actuel n'a pas de receveur d'update Wi-Fi**. Une **unique installation initiale** sera nécessaire pour introduire le récepteur ; aucune garantie que cette première transition soit possible en Wi-Fi. Utiliser seulement une méthode déjà prouvée et séparément autorisée. Conserver le backup privé complet. Après qualification de cette transition, prouver un **second SHINO -> SHINO par Wi-Fi**, puis arrêter les interventions UART de maintenance ordinaire.

## Ordre de priorité ensuite

Une fois la possibilité de mise à jour clarifiée (ou classée NO-GO sans y perdre plus de soirées), **reprendre le produit visuel** : les quatre cartes CPU/GPU/RAM/GPU TEMP restent fonctionnelles ; améliorer lisibilité native, puis horloge, météo de ville configurable et musique/pochette via SHINO // LINK. On ne retarde plus ces fonctions pour une « phase de sécurité OTA » sans fin.

**Statut : décision d'orientation et contrat de livraison, pas code déjà intégré.** Aucun flash, RTC, LittleFS, UART, tentative réseau ou merge autorisé. PR42 reste Draft. Résultats passés S/T et StageA inchangés.
