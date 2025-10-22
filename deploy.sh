#!/usr/bin/env bash
set -euo pipefail

# Construire le site
hugo --minify

pushd public >/dev/null

# Désactiver Jekyll (recommandé)
[ -f .nojekyll ] || touch .nojekyll

# CNAME si domaine custom (décommente et adapte)
# echo "www.example.com" > CNAME

git add -A
msg="Deploy $(date -u +'%Y-%m-%d %H:%M:%S %Z')"
git commit -m "$msg" || echo "Rien à committer."
git push origin gh-pages

popd >/dev/null
echo "✅ Déployé sur gh-pages."
