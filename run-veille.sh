#!/usr/bin/env bash
# run-veille.sh — orchestrateur quotidien.
# 1) Claude Code recherche les news et met à jour state.json + changelog.md
# 2) build.py rend les pages HTML + index + RSS (déterministe)
# 3) git commit/push (déclenche le déploiement GitHub Pages)
set -euo pipefail
cd "$(dirname "$0")"

DATE="$(date +%F)"
LOG="logs/${DATE}.log"
mkdir -p logs

echo "=== Veille ${DATE} : $(date -Is) ===" | tee -a "$LOG"

# --- 1. Agent : recherche + mise à jour de l'état -----------------------------
# Outils minimaux : recherche web + lecture/écriture des fichiers d'état.
# Pas de Bash pour l'agent (le build et le git sont faits ici, de façon déterministe).
# --bare : ignore hooks/MCP/CLAUDE.md du poste → comportement reproductible.
timeout 600 /home/raziel/.local/bin/claude -p "$(cat prompt.md)" \
  --allowedTools "WebSearch,Read,Edit,Write" \
  --permission-mode acceptEdits \
  --max-turns 40 \
  --model claude-opus-4-8 \
  2>&1 | tee -a "$LOG"

# --- 2. Validation rapide de l'état avant de générer --------------------------
python3 -c "import json,sys; json.load(open('state.json',encoding='utf-8'))" \
  || { echo "state.json invalide — abandon, rien n'est publié." | tee -a "$LOG"; exit 1; }

# --- 3. Rendu déterministe ----------------------------------------------------
python3 build.py 2>&1 | tee -a "$LOG"

# --- 4. Publication -----------------------------------------------------------
git add -A
if git diff --cached --quiet; then
  echo "Aucun changement — pas de commit aujourd'hui." | tee -a "$LOG"
  exit 0
fi
git commit -m "veille ${DATE}" 2>&1 | tee -a "$LOG"
git push 2>&1 | tee -a "$LOG"
echo "Publié." | tee -a "$LOG"
