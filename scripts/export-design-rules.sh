#!/usr/bin/env bash
# Export design rules and templates from Mission Control to another project.
# Usage: ./scripts/export-design-rules.sh <target_project_path> [--overwrite]
# Example: ./scripts/export-design-rules.sh ../MyOtherApp

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OVERWRITE=false

# Parse args
TARGET=""
for arg in "$@"; do
  if [ "$arg" = "--overwrite" ]; then
    OVERWRITE=true
  elif [ "$arg" = "--help" ] || [ "$arg" = "-h" ]; then
    echo "Usage: $0 <target_project_path> [--overwrite]"
    echo ""
    echo "Export Mission Control design rules to another project."
    echo ""
    echo "Arguments:"
    echo "  target_project_path    Path to the target project (absolute or relative)"
    echo "  --overwrite            Overwrite existing files (optional)"
    echo ""
    echo "Example:"
    echo "  $0 ../MyOtherProject"
    echo "  $0 /path/to/OtherProject --overwrite"
    exit 0
  else
    TARGET="$arg"
  fi
done

if [ -z "$TARGET" ]; then
  echo "Usage: $0 <target_project_path> [--overwrite]"
  echo "Example: $0 ../MyOtherApp"
  exit 1
fi

# Resolve target to absolute path
if [[ "$TARGET" != /* ]]; then
  TARGET="$(cd "$REPO_ROOT" && cd "$TARGET" && pwd)"
fi

if [ ! -d "$TARGET" ]; then
  echo "Error: Target directory does not exist: $TARGET"
  exit 1
fi

RULES_SRC="$REPO_ROOT/.cursor/rules"
TEMPLATES_SRC="$REPO_ROOT/docs/templates"
RULES_DST="$TARGET/.cursor/rules"
TEMPLATES_DST="$TARGET/docs/templates"

# Mission Control design rules
DESIGN_RULES=(
  "010-mission-control-design-system.mdc"
  "020-mission-control-gates.mdc"
)

# Mission Control templates (if they exist)
DESIGN_TEMPLATES=(
  "COMPONENT-TEMPLATE.md"
  "API-ROUTE-TEMPLATE.ts"
  "PAGE-TEMPLATE.tsx"
)

mkdir -p "$RULES_DST"
mkdir -p "$TEMPLATES_DST"

copy_file() {
  local src="$1"
  local dst="$2"
  if [ ! -f "$src" ]; then
    echo "  Skip (missing): $(basename "$src")"
    return
  fi
  if [ -f "$dst" ] && [ "$OVERWRITE" != "true" ]; then
    echo "  Skip (exists): $(basename "$dst")"
    return
  fi
  cp "$src" "$dst"
  echo "  ✓ Copied: $(basename "$dst")"
}

echo "Exporting Mission Control design rules to $TARGET"
echo ""

echo "Rules -> $RULES_DST"
for f in "${DESIGN_RULES[@]}"; do
  copy_file "$RULES_SRC/$f" "$RULES_DST/$f"
done

echo ""
echo "Templates -> $TEMPLATES_DST"
for f in "${DESIGN_TEMPLATES[@]}"; do
  copy_file "$TEMPLATES_SRC/$f" "$TEMPLATES_DST/$f"
done

# Copy AGENTS.md
echo ""
echo "AGENTS.md -> $TARGET"
if [ -f "$REPO_ROOT/AGENTS.md" ]; then
  if [ -f "$TARGET/AGENTS.md" ] && [ "$OVERWRITE" != "true" ]; then
    echo "  Skip (exists): AGENTS.md"
  else
    cp "$REPO_ROOT/AGENTS.md" "$TARGET/AGENTS.md"
    echo "  ✓ Copied: AGENTS.md"
  fi
else
  echo "  Skip (missing): AGENTS.md"
fi

echo ""
echo "Done! See EXPORT_DESIGN_RULES.md for what to adapt in the new project."
echo ""
echo "Next steps:"
echo "1. Review copied files in $TARGET"
echo "2. Update project-specific paths and references"
echo "3. Adapt design system to your brand (fonts, colors)"
echo "4. Simplify AGENTS.md if not a trading system"
echo "5. Commit the new design rules to git"
