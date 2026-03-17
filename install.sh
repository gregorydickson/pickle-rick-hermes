#!/usr/bin/env bash
set -euo pipefail

# Pickle Rick Hermes Plugin Installer
# Copies skills into ~/.hermes/skills/autonomous-ai-agents/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${HOME}/.hermes/skills/autonomous-ai-agents"
PICKLE_DIR="${SKILLS_DIR}/pickle-rick"
MEESEEKS_DIR="${SKILLS_DIR}/pickle-rick-meeseeks"

echo "🥒 Installing Pickle Rick Hermes Plugin..."
echo ""

# Create target directories
mkdir -p "${PICKLE_DIR}"/{references,templates,scripts}
mkdir -p "${MEESEEKS_DIR}"
mkdir -p "${HOME}/.pickle-rick/sessions"

# Copy pickle-rick skill
echo "  Copying pickle-rick skill..."
cp "${SCRIPT_DIR}/skills/pickle-rick/SKILL.md" "${PICKLE_DIR}/"
cp "${SCRIPT_DIR}/skills/pickle-rick/references/"* "${PICKLE_DIR}/references/"
cp "${SCRIPT_DIR}/skills/pickle-rick/templates/"* "${PICKLE_DIR}/templates/"
cp "${SCRIPT_DIR}/skills/pickle-rick/scripts/"* "${PICKLE_DIR}/scripts/"
chmod +x "${PICKLE_DIR}/scripts/"*.py

# Copy meeseeks skill
echo "  Copying pickle-rick-meeseeks skill..."
cp "${SCRIPT_DIR}/skills/pickle-rick-meeseeks/SKILL.md" "${MEESEEKS_DIR}/"

echo ""
echo "✅ Installed successfully!"
echo ""
echo "Skills installed to:"
echo "  ${PICKLE_DIR}"
echo "  ${MEESEEKS_DIR}"
echo ""
echo "Sessions will be stored in:"
echo "  ${HOME}/.pickle-rick/sessions/"
echo ""
echo "Usage:"
echo "  In Hermes: 'Run pickle rick on this project: <your task>'"
echo "  CLI loop:  python3 ${PICKLE_DIR}/scripts/mux_runner.py --task '...' --working-dir ."
echo ""
echo "🥒 Wubba lubba dub dub!"
