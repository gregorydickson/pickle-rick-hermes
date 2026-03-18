#!/usr/bin/env bash
set -euo pipefail

# Pickle Rick Hermes Plugin Installer (Full)
# Copies all skills into ~/.hermes/skills/autonomous-ai-agents/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_DIR="${HOME}/.hermes/skills/autonomous-ai-agents"
PICKLE_DIR="${SKILLS_DIR}/pickle-rick"

echo "🥒 Installing Pickle Rick Hermes Plugin..."
echo ""

# Create target directories
mkdir -p "${PICKLE_DIR}"/{references,templates,scripts}
mkdir -p "${HOME}/.pickle-rick/sessions"
mkdir -p "${HOME}/.pickle-rick/jar"

# Skills to install (each gets its own directory)
SKILLS=(pickle-rick pickle-rick-meeseeks pickle-rick-microverse pickle-rick-portal-gun pickle-rick-council pickle-rick-jar pickle-rick-morty pickle-rick-morty-review pickle-rick-help pickle-rick-tmux pickle-rick-prd pickle-rick-refine-prd pickle-rick-chaos pickle-rick-dot pickle-rick-dot-patterns pickle-rick-attract)

for skill in "${SKILLS[@]}"; do
    src="${SCRIPT_DIR}/skills/${skill}"
    dst="${SKILLS_DIR}/${skill}"
    
    if [ ! -d "$src" ]; then
        echo "  SKIP: ${skill} (not found)"
        continue
    fi
    
    echo "  Installing ${skill}..."
    mkdir -p "$dst"
    cp "$src/SKILL.md" "$dst/"
done

# Copy pickle-rick supporting files
echo "  Copying references..."
cp "${SCRIPT_DIR}/skills/pickle-rick/references/"* "${PICKLE_DIR}/references/" 2>/dev/null || true

echo "  Copying templates..."
cp "${SCRIPT_DIR}/skills/pickle-rick/templates/"* "${PICKLE_DIR}/templates/" 2>/dev/null || true

echo "  Copying scripts..."
cp "${SCRIPT_DIR}/skills/pickle-rick/scripts/"* "${PICKLE_DIR}/scripts/" 2>/dev/null || true
chmod +x "${PICKLE_DIR}/scripts/"*.py 2>/dev/null || true
chmod +x "${PICKLE_DIR}/scripts/"*.sh 2>/dev/null || true

# Copy layouts
if [ -d "${SCRIPT_DIR}/skills/pickle-rick/layouts" ]; then
    echo "  Copying Zellij layouts..."
    mkdir -p "${PICKLE_DIR}/layouts"
    cp "${SCRIPT_DIR}/skills/pickle-rick/layouts/"* "${PICKLE_DIR}/layouts/" 2>/dev/null || true
fi

# Copy default settings
if [ -f "${SCRIPT_DIR}/pickle_settings.json" ]; then
    echo "  Copying default settings..."
    cp "${SCRIPT_DIR}/pickle_settings.json" "${HOME}/.pickle-rick/pickle_settings.json"
fi

# Append persona to SOUL.md (Hermes equivalent of CLAUDE.md)
SOUL_FILE="${HOME}/.hermes/SOUL.md"
PERSONA_FILE="${SCRIPT_DIR}/skills/pickle-rick/references/persona.md"
PERSONA_MARKER="# Pickle Rick Persona"

if [ -f "$PERSONA_FILE" ]; then
    if [ -f "$SOUL_FILE" ] && grep -q "$PERSONA_MARKER" "$SOUL_FILE" 2>/dev/null; then
        # Already installed — replace the existing persona block
        echo "  Updating persona in SOUL.md..."
        # Remove old persona block (from marker to next # or EOF)
        python3 -c "
import re
soul = open('$SOUL_FILE').read()
# Remove existing pickle rick persona block
pattern = r'\\n?# Pickle Rick Persona.*?(?=\\n# (?!Pickle Rick)|\\Z)'
soul = re.sub(pattern, '', soul, flags=re.DOTALL)
open('$SOUL_FILE', 'w').write(soul)
" 2>/dev/null
        echo "" >> "$SOUL_FILE"
        cat "$PERSONA_FILE" >> "$SOUL_FILE"
    else
        echo "  Appending persona to SOUL.md..."
        echo "" >> "$SOUL_FILE"
        cat "$PERSONA_FILE" >> "$SOUL_FILE"
    fi
fi

echo ""
echo "✅ Installed ${#SKILLS[@]} skills!"
echo ""
echo "Skills installed to: ${SKILLS_DIR}/"
echo "Session data:        ${HOME}/.pickle-rick/"
echo ""
echo "Available commands:"
echo "  pickle-rick           — Autonomous engineering loop"
echo "  pickle-rick-meeseeks  — Iterative code review"
echo "  pickle-rick-microverse — Metric convergence optimization"
echo "  pickle-rick-portal-gun — Pattern transplantation"
echo "  pickle-rick-council   — PR stack review"
echo "  pickle-rick-jar       — Batch job queue"
echo "  pickle-rick-morty     — Worker lifecycle"
echo "  pickle-rick-help      — Show all commands"
echo ""
echo "🥒 Wubba lubba dub dub!"
