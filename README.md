# Veille · Convergence numérique — blog quotidien auto-généré

Une page par jour. Chaque matin, Claude Code recherche les actualités, met à jour des
prédictions sourcées, et un générateur déterministe publie une nouvelle édition sur
GitHub Pages.

## Pièces

| Fichier            | Rôle                                                                    |
|--------------------|-------------------------------------------------------------------------|
| `state.json`       | Mémoire de la veille : 23 signaux, probabilités, historique, sources.   |
| `prompt.md`        | Instructions données à Claude Code chaque jour (avec garde-fous).       |
| `build.py`         | Générateur déterministe → `posts/`, `index.html`, `feed.xml`.           |
| `style.css`        | Feuille de style (inlinée dans chaque page).                            |
| `run-veille.sh`    | Orchestrateur cron : agent → build → git push.                          |
| `changelog.md`     | Journal append-only des changements (créé au 1er run).                  |
| `posts_index.json` | Manifeste des éditions (créé au 1er run).                               |

Séparation clé : **l'agent ne fait que la recherche et l'écriture de `state.json`** ;
tout le HTML est produit ensuite par `build.py`, de façon déterministe. L'IA ne décide
jamais d'une couleur ni d'une mise en page — seulement d'un fait sourcé et d'un chiffre.

## Pré-requis

- **Claude Code** installé et authentifié sur le PC (`claude --version`).
- **Python 3** (stdlib seule, aucune dépendance).
- **git**, avec le dossier initialisé comme dépôt et un remote `origin` pointant vers ton
  dépôt GitHub.

## Installation

```bash
git init
git remote add origin git@github.com:TON-PSEUDO/veille.git
chmod +x run-veille.sh
# Renseigne ton URL GitHub Pages dans state.json → meta.base_url
# (utilisée pour les liens du flux RSS)
```

Premier rendu manuel pour vérifier :

```bash
python3 build.py        # génère posts/veille-AAAA-MM-JJ.html + index.html + feed.xml
xdg-open index.html     # ou ouvre le fichier dans un navigateur
```

## Lancement quotidien (cron)

```bash
crontab -e
# tous les jours à 6h30 :
30 6 * * * /chemin/vers/veille/run-veille.sh
```

Le script logge dans `logs/AAAA-MM-JJ.log`. S'il n'y a aucun changement, il ne commite pas.

## GitHub Pages

1. Dépôt **public** (Pages gratuit ; un dépôt privé exige GitHub Pro).
2. Repo → **Settings → Pages → Source : Deploy from a branch**, branche `main`, dossier `/ (root)`.
3. L'`index.html` à la racine devient la page d'accueil (l'archive), `posts/` contient les éditions.
4. Limites : 1 Go de site, 100 Go/mois de bande passante, build < 10 min. Une page/jour =
   quelques Ko : tu es tranquille pour des décennies.

> Alternative sans PC : un workflow **GitHub Actions** planifié (`on: schedule`) peut exécuter
> tout `run-veille.sh` côté GitHub. Mets la clé/auth en *secret* du dépôt. Le build par Actions
> supprime aussi la limite des 10 builds/h.

## Authentification & coût

`run-veille.sh` appelle Claude Code, qui utilise l'authentification déjà configurée sur le poste :

- **Connexion par abonnement** (Pro/Max) : l'usage quotidien est décompté des limites de
  l'abonnement, pas facturé à l'acte.
- **Clé API** (`ANTHROPIC_API_KEY`) : facturation à l'usage (tokens + recherches web).
  Ordre de grandeur avec Sonnet : ~0,30–0,50 $/jour. Avec Haiku : ~0,10–0,20 $/jour.

Astuce reproductibilité : épingle la version de Claude Code, son comportement headless peut
varier entre versions.

## Garde-fous (anti-bruit)

- Une probabilité ne bouge que sur un **fait matériel sourcé**, plafonné à `meta.delta_cap`
  points/jour (5 par défaut).
- Les **jours calmes** ne produisent pas de mouvement artificiel.
- Chaque changement porte sa **raison + sa source** (auditable), et `changelog.md` garde une
  trace append-only même en cas de corruption de `state.json`.
- L'agent **paraphrase** les sources : pas de reproduction d'articles.

## Ajouter / retirer un signal

Édite `state.json` → tableau `signals`. Modèle minimal :

```json
{
  "id": "slug-unique", "domain": "Crypto", "horizon": "T-1",
  "title": "…", "when": "…", "status": "…",
  "is_bascule": true, "prob": 50, "prob_range": [40, 60],
  "prob_history": [{ "date": "AAAA-MM-JJ", "prob": 50 }],
  "up": "ce qui aggrave…", "down": "ce qui freine…",
  "created": "AAAA-MM-JJ", "last_change": null
}
```

`is_bascule: false` (et `prob: null`) pour un signal suivi sans probabilité chiffrée :
il apparaît en carte mais pas dans le baromètre.
