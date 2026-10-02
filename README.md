# Jobbys

Trier les offres d'emploi comme sur Tinder : Jobbys récupère les offres de plusieurs sites,
fusionne les doublons, résume chaque offre sur une carte avec un score de correspondance,
et quand tu likes, il prépare ta candidature avec un message personnalisé.

## Ce que fait le like

| L'offre se postule…            | Ce que fait Jobbys                                                                 |
|--------------------------------|------------------------------------------------------------------------------------|
| par email                      | Envoie l'email tout seul, avec ton CV en pièce jointe.                             |
| par formulaire (WTTJ, site…)   | Ouvre le formulaire dans un navigateur, le préremplit. **Tu cliques sur Envoyer.** |
| sur LinkedIn                   | Ouvre l'offre et prépare le message à copier. Tu postules toi-même.               |

Tous les messages sont visibles dans l'onglet **Candidatures**.

Jobbys ne postule jamais automatiquement sur LinkedIn : c'est interdit par leurs conditions
d'utilisation et ton compte risquerait d'être restreint.

## Sources

- **France Travail** : API officielle et gratuite. Elle reprend aussi beaucoup d'offres de partenaires.
- **Adzuna** : API gratuite qui agrège de nombreux sites.
- **Welcome to the Jungle** : lu directement sur le site, sans clé (peut casser si le site change).
- **LinkedIn** : offres publiques lues sans ton compte. Désactivé par défaut, car LinkedIn bloque vite ces lectures.

## Démarrer (en un clic)

1. Télécharge Jobbys : [jobbys-main.zip](https://github.com/eneko-cc/jobbys/archive/refs/heads/main.zip),
   puis dézippe-le où tu veux (par exemple dans Documents).
2. Double-clique sur **Jobbys.bat** (Windows) ou **Jobbys.command** (Mac).

C'est tout. Au premier lancement, Jobbys installe ce dont il a besoin (quelques minutes, et
Python lui-même s'il manque sur Windows), ajoute un raccourci **Jobbys** sur ton bureau Windows,
puis ouvre la page dans ton navigateur. Les fois suivantes, le raccourci ouvre Jobbys directement.
Laisse la fenêtre noire ouverte pendant que tu utilises Jobbys : la fermer arrête Jobbys.

Sur Mac, la première fois, fais clic droit sur **Jobbys.command** puis **Ouvrir**, car le fichier
ne vient pas de l'App Store.

La première page qui s'ouvre est **Réglages** : renseigne la clé Claude, au moins une source
(France Travail ou Adzuna), ce que tu cherches et ton CV, puis **Enregistrer**. Chaque champ
indique où trouver la clé correspondante. Ensuite, clique sur **Chercher des offres** et swipe :
glisse la carte, ou utilise les boutons ✕ / ♥, ou les flèches ← / →.

Les emails sont en **mode test** au départ : ils sont rédigés mais pas envoyés. Décoche
« Mode test » dans Réglages quand tu es prêt.

## Bon à savoir

- **Coût Claude** : chaque offre analysée et chaque message coûtent quelques centimes
  d'API. Le modèle se change avec `JOBBYS_MODEL` dans `.env`.
- **Formulaires** : le navigateur ouvert par Jobbys garde ses cookies (dans `data/browser`).
  Connecte-toi une fois à Welcome to the Jungle ou HelloWork dans cette fenêtre et tu le resteras.
- Tes données (offres, candidatures, profil, CV) restent dans le dossier `data/`, qui n'est pas envoyé sur GitHub.

## Pour les développeurs

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
python -m app     # lance le serveur
pytest            # lance les tests
```

Les réglages de la page sont enregistrés dans `.env` (modèle : `.env.example`) et le profil
dans `data/profile.yaml` (modèle : `data/profile.example.yaml`).
