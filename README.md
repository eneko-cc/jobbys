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

## Installation (une seule fois)

Il faut Python 3.11 ou plus récent.

```bash
git clone https://github.com/eneko-cc/jobbys.git
cd jobbys
python -m venv .venv
# Windows : .venv\Scripts\activate      macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Puis :

1. Copie `.env.example` en `.env` et remplis au moins `ANTHROPIC_API_KEY` et une source
   (France Travail ou Adzuna). Chaque ligne du fichier explique où trouver la clé.
2. Copie `data/profile.example.yaml` en `data/profile.yaml`, remplis-le, et mets ton CV dans `data/cv.pdf`.

## Lancer

```bash
python -m app
```

Le navigateur s'ouvre sur http://localhost:8000. Clique sur **Chercher des offres**, attends
l'analyse, puis swipe : glisse la carte, ou utilise les boutons ✕ / ♥, ou les flèches ← / →.

Les emails sont en **mode test** au départ (`EMAIL_DRY_RUN=true`) : ils sont rédigés mais pas
envoyés. Passe la valeur à `false` dans `.env` quand tu es prêt.

## Bon à savoir

- **Coût Claude** : chaque offre analysée et chaque message coûtent quelques centimes
  d'API. Le modèle se change avec `JOBBYS_MODEL` dans `.env`.
- **Formulaires** : le navigateur ouvert par Jobbys garde ses cookies (dans `data/browser`).
  Connecte-toi une fois à Welcome to the Jungle ou HelloWork dans cette fenêtre et tu le resteras.
- Tes données (offres, candidatures, profil, CV) restent dans le dossier `data/`, qui n'est pas envoyé sur GitHub.

## Tests

```bash
pytest
```
