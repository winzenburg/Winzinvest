# Export Design Rules and Agents to Another Project

This guide explains how to copy Mission Control's design rules and agent system to another project so the same quality gates and design standards apply there.

---

## What Gets Exported

### 1. Design Rules (`.cursor/rules/*.mdc`)

| Rule | Purpose |
|------|---------|
| `010-mission-control-design-system.mdc` | Complete design system: typography, colors, components, layout, accessibility, data visualization, voice/tone |
| `020-mission-control-gates.mdc` | Quality gates for code, trading system, dashboard, and deployment |

### 2. Agent System (`AGENTS.md`)

Defines the agent workflow and responsibilities:
- **Trading System Agent** - Strategy development and execution
- **Dashboard Agent** - UI/UX and data visualization
- **Data Agent** - Data aggregation and processing
- **Audit Agent** - Logging and monitoring
- **Testing Agent** - Backtesting and validation
- **Design Agent** - Design system enforcement

### 3. Export Script (`scripts/export-design-rules.sh`)

Automated script to copy rules and agents to another project.

---

## How to Export

### Option A: Run the export script (recommended)

From Mission Control root:

```bash
# Export to a sibling project
./scripts/export-design-rules.sh "../YourOtherProject"

# Or with an absolute path
./scripts/export-design-rules.sh "/path/to/OtherProject"

# Overwrite existing files
./scripts/export-design-rules.sh "../YourOtherProject" --overwrite
```

The script:
- Creates `.cursor/rules/` in the target if missing
- Copies design rules (`010-*.mdc`, `020-*.mdc`)
- Copies `AGENTS.md`
- Does not overwrite existing files unless you pass `--overwrite`

### Option B: Manual copy

1. **Create directories in the other project**
   ```bash
   cd /path/to/OtherProject
   mkdir -p .cursor/rules
   ```

2. **Copy rule files**
   ```bash
   cp /path/to/MissionControl/.cursor/rules/010-mission-control-design-system.mdc .cursor/rules/
   cp /path/to/MissionControl/.cursor/rules/020-mission-control-gates.mdc .cursor/rules/
   ```

3. **Copy AGENTS.md**
   ```bash
   cp /path/to/MissionControl/AGENTS.md ./
   ```

---

## After Export: What to Adapt

### 1. Update Project-Specific References

**In `010-mission-control-design-system.mdc`:**
- Update font choices if different brand
- Adjust color palette for different product
- Modify component patterns to match tech stack
- Update file paths (e.g., `trading-dashboard-public/` → your app folder)

**In `020-mission-control-gates.mdc`:**
- Remove trading-specific gates if not applicable
- Add domain-specific gates for your project
- Update file paths in examples
- Adjust quality thresholds

**In `AGENTS.md`:**
- Remove Trading System, Data, Audit, Testing agents if not applicable
- Keep Dashboard and Design agents (universal)
- Add project-specific agents
- Update file structure section
- Update common commands

### 2. Simplify for Non-Trading Projects

If your project is not a trading system, you can:

**Keep:**
- Design system (typography, colors, components, a11y)
- Code quality gates
- Dashboard quality gates
- Deployment gates
- Dashboard Agent
- Design Agent
- Agent workflow (planning → implementation → testing → deployment)

**Remove:**
- Trading system gates
- Trading System Agent
- Data Agent (unless you have similar data aggregation)
- Audit Agent (unless you need audit trails)
- Testing Agent (unless you do backtesting)

**Simplify AGENTS.md to:**
```markdown
# AGENTS.md - [Your Project Name]

## Core Agents

### 📊 Dashboard Agent
[Keep this section, update file paths]

### 🎨 Design Agent
[Keep this section]

### [Your Domain Agent]
[Add agents specific to your domain]

## Agent Workflow
[Keep the workflow, adjust phases to your needs]

## Decision Framework
[Replace trading decisions with your domain decisions]
```

### 3. Adapt Design System to Your Brand

**Typography:**
- Replace `Playfair Display` with your brand's display font
- Replace `Inter` with your brand's body font
- Update font sizes to match your hierarchy

**Colors:**
- Replace profit/loss greens/reds if not financial
- Update accent colors to match brand
- Keep WCAG AA contrast requirements

**Components:**
- Adapt metric cards to your data types
- Modify table patterns for your content
- Update badge colors for your categories

### 4. Create Project-Specific Templates

Consider adding to `docs/templates/`:
- Component templates
- Page templates
- API route templates
- Test templates

---

## Quick Reference: Files to Copy

Use this list for manual copy:

```
.cursor/rules/010-mission-control-design-system.mdc
.cursor/rules/020-mission-control-gates.mdc
AGENTS.md
scripts/export-design-rules.sh (optional, for future exports)
```

---

## Example: Exporting to a SaaS Product

Let's say you're building a SaaS analytics dashboard:

### 1. Run export
```bash
./scripts/export-design-rules.sh "../MySaaSProduct"
```

### 2. Adapt design system
- Change "Mission Control" → "MySaaS"
- Update color palette to match brand
- Replace trading-specific components with SaaS patterns
- Keep typography, spacing, accessibility rules

### 3. Adapt gates
- Keep: Code quality, dashboard quality, deployment gates
- Remove: Trading system gates
- Add: SaaS-specific gates (e.g., API rate limits, user quotas)

### 4. Adapt agents
- Keep: Dashboard Agent, Design Agent
- Remove: Trading System, Data, Audit, Testing agents
- Add: API Agent, User Management Agent, Billing Agent

### 5. Test
```bash
cd ../MySaaSProduct
npm run dev
# Verify design system applies correctly
```

---

## Summary

| Step | Action |
|------|--------|
| 1 | Run `./scripts/export-design-rules.sh ../OtherProject` |
| 2 | Update project-specific references in copied files |
| 3 | Simplify AGENTS.md if not a trading system |
| 4 | Adapt design system to your brand |
| 5 | Test that rules apply correctly |
| 6 | Commit to git |

After that, Cursor in the other project will use the same design standards and agent workflows.

---

## Differences from Cultivate/SaaS-Starter

Mission Control's design system is **trading-focused** and may differ from the Cultivate framework in:

- **Color semantics**: Heavy use of green/red for profit/loss
- **Data visualization**: Canvas-based charts for performance
- **Typography**: Serif fonts for large numbers (emotional impact)
- **Tone**: Professional/institutional vs consumer SaaS
- **Gates**: Trading-specific risk gates

If you want the **full Cultivate design rules** from SaaS-Starter (WCAG, brand system, voice/tone, landing pages, etc.), those are more comprehensive and consumer-focused. Mission Control's rules are a **subset focused on institutional dashboards**.

For the full Cultivate export, refer to the guide you provided and fetch rules from the SaaS-Starter repo (if you have access to the private `.cursor/rules/` folder).
