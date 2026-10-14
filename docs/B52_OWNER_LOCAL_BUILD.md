# B5.2 — Construction propriétaire locale

Le build B5.2 public inerte a réussi sur GitHub (commit f67cadf8c46f24a0edab9718cf80d258f78e0c12).
421536 octets et SHA-256 8e6679789b6406da8f479ddea5c2efb84c6468bc91a2b68dd71c390ebdadd1d4
concernent UNIQUEMENT ce BIN public. Aucun candidat propriétaire ne leur est identique.

Dans le worktree Windows `codex/b52-owner-build-prep`, avec un Git propre :

    python tools/shino_b52_owner_candidate.py --bootstrap-libraries

Le lanceur réutilise les dépendances épinglées déjà installées ; si elles sont absentes,
l'option amorce un build public B5.1 qui peut télécharger des paquets PlatformIO.
Le programme cherche une seule copie existante des identifiants sous
`research-local/m9-owner/` dans les worktrees de ce dépôt, sans copier,
modifier ni imprimer les mots de passe. Les sorties privées sont placées
uniquement dans le dossier `research-local/m9-owner/` du worktree actif.
En cas d'absence ou d'ambiguïté, il refuse de compiler et ne génère pas d'identité.

Le reçu local `b52-safe-receipt.json` donne la taille et le SHA calculés à partir
du vrai BIN, le commit, le layout 4m2m et la RAM statique. Le build ne contacte
jamais le SmallTV, n'effectue aucune OTA et n'autorise aucune installation.
Tout BIN, secret, identifiant matériel, manifeste privé ou build log reste local.

Les tests en CI utilisent exclusivement des fixtures et ne construisent aucun
firmware privé. La réussite d'une compilation ne prouve pas le boot, la RAM
native en fonctionnement, l'affichage 240×240 ou le transfert OTA réel.

PHYSICAL HOLD : un GO distinct et le candidat exact sont requis pour tout essai.
