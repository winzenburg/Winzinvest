# Mission Control Design System - Complete Index

**Quick navigation to all design system documentation.**

---

## Core Rules (`.cursor/rules/`)

### 010-mission-control-design-system.mdc
**Size**: 13.7 KB | **Lines**: 440

Complete design system covering:
- Typography (Playfair + Inter + JetBrains Mono)
- Color system (stone palette, semantic colors)
- Layout and spacing scale
- Component patterns (cards, tables, badges, alerts)
- Accessibility (WCAG 2.2 AA)
- Data visualization
- Number formatting
- Voice & tone
- Micro-interactions
- Responsive design

**When to read**: Before creating any new UI component

---

### 020-mission-control-gates.mdc
**Size**: 6.8 KB | **Lines**: 284

Quality gates for:
- Code quality (type safety, error handling)
- Trading system (risk limits, position sizing)
- Dashboard quality (WCAG, real data, performance)
- Deployment (build, lint, tests)
- Audit trail logging
- Emergency bypass protocol

**When to read**: Before committing any code

---

## Agent System

### AGENTS.md
**Size**: 7.9 KB | **Lines**: 350+

Defines 6 specialized agents:
- 🎯 Trading System Agent
- 📊 Dashboard Agent
- 🔍 Data Agent
- 🛡️ Audit Agent
- 🧪 Testing Agent
- 🎨 Design Agent

Includes:
- Agent roles and responsibilities
- Coordination patterns
- Decision frameworks
- Workflows (features, bugs, deployments)
- Memory and context management
- Safety and security rules

**When to read**: At the start of each session

---

## Documentation

### README_DESIGN_SYSTEM.md
**Purpose**: Main entry point for design system

Quick start guide covering:
- What's included
- How to use
- File structure
- Design highlights
- Quality gates summary
- Agent roles
- Export instructions
- Current status

**When to read**: First time learning the design system

---

### DESIGN_QUICK_REFERENCE.md
**Purpose**: Copy-paste patterns for developers

Includes:
- Typography classes and patterns
- Color classes and semantic usage
- Layout and spacing patterns
- Component patterns (cards, tables, badges, alerts, buttons)
- Number formatting functions
- Accessibility patterns
- TypeScript patterns (type guards, API fetch)
- Testing checklist

**When to read**: While coding (keep open for reference)

---

### DESIGN_SYSTEM_IMPLEMENTATION.md
**Purpose**: Complete implementation overview

Covers:
- What was implemented
- Design system compliance checklist
- What's missing (future enhancements)
- Comparison to Cultivate framework
- Maintenance guide
- Key principles

**When to read**: To understand the full scope of implementation

---

### DESIGN_BEFORE_AFTER.md
**Purpose**: Visual comparison of transformation

Shows:
- Before/after code examples
- Problem → solution mapping
- Visual examples (metric cards, tables, alerts)
- Impact metrics
- Developer experience improvements
- User experience improvements

**When to read**: To understand the value of the design system

---

### CULTIVATE_INTEGRATION_SUMMARY.md
**Purpose**: Summary of Cultivate integration

Explains:
- What was requested
- What was implemented
- How it differs from Cultivate
- Files created/modified
- Design system compliance
- Key takeaways

**When to read**: To understand how Cultivate principles were applied

---

## Export System

### EXPORT_DESIGN_RULES.md
**Purpose**: Guide for exporting to other projects

Covers:
- What gets exported
- How to export (script + manual)
- What to adapt after export
- Simplification for non-trading projects
- Example: exporting to SaaS product

**When to read**: Before exporting to another project

---

### scripts/export-design-rules.sh
**Purpose**: Automated export script

Features:
- Creates `.cursor/rules/` in target
- Copies design system and gates
- Copies AGENTS.md
- Optional `--overwrite` flag
- Validates target directory

**Usage**:
```bash
./scripts/export-design-rules.sh "../OtherProject"
./scripts/export-design-rules.sh "../OtherProject" --overwrite
```

---

## Quick Navigation

### I want to...

**...create a new UI component**
→ Read `DESIGN_QUICK_REFERENCE.md` for patterns  
→ Check `.cursor/rules/010-mission-control-design-system.mdc` for details

**...understand quality gates**
→ Read `.cursor/rules/020-mission-control-gates.mdc`

**...understand agent workflows**
→ Read `AGENTS.md`

**...export to another project**
→ Read `EXPORT_DESIGN_RULES.md`  
→ Run `./scripts/export-design-rules.sh`

**...see before/after examples**
→ Read `DESIGN_BEFORE_AFTER.md`

**...understand the implementation**
→ Read `DESIGN_SYSTEM_IMPLEMENTATION.md`

**...get started quickly**
→ Read `README_DESIGN_SYSTEM.md`

**...understand Cultivate integration**
→ Read `CULTIVATE_INTEGRATION_SUMMARY.md`

---

## File Sizes

| File | Size | Lines | Purpose |
|------|------|-------|---------|
| `.cursor/rules/010-mission-control-design-system.mdc` | 13.7 KB | 440 | Complete design system |
| `.cursor/rules/020-mission-control-gates.mdc` | 6.8 KB | 284 | Quality gates |
| `AGENTS.md` | 7.9 KB | 350+ | Agent system |
| `DESIGN_QUICK_REFERENCE.md` | ~8 KB | 400+ | Developer patterns |
| `EXPORT_DESIGN_RULES.md` | ~5 KB | 200+ | Export guide |
| `DESIGN_SYSTEM_IMPLEMENTATION.md` | ~10 KB | 400+ | Implementation details |
| `CULTIVATE_INTEGRATION_SUMMARY.md` | ~8 KB | 350+ | Integration summary |
| `DESIGN_BEFORE_AFTER.md` | ~6 KB | 300+ | Before/after comparison |
| `README_DESIGN_SYSTEM.md` | ~7 KB | 300+ | Main entry point |
| `scripts/export-design-rules.sh` | ~2 KB | 100+ | Export automation |

**Total**: ~75 KB of design system documentation

---

## Reading Order

### For New Developers

1. **Start here**: `README_DESIGN_SYSTEM.md` (overview)
2. **Learn patterns**: `DESIGN_QUICK_REFERENCE.md` (copy-paste)
3. **Understand gates**: `.cursor/rules/020-mission-control-gates.mdc` (quality)
4. **Read workflows**: `AGENTS.md` (process)
5. **Deep dive**: `.cursor/rules/010-mission-control-design-system.mdc` (full system)

### For Experienced Developers

1. **Quick patterns**: `DESIGN_QUICK_REFERENCE.md` (keep open while coding)
2. **Quality checks**: `.cursor/rules/020-mission-control-gates.mdc` (before commit)
3. **Agent workflows**: `AGENTS.md` (for complex features)

### For Exporting

1. **Export guide**: `EXPORT_DESIGN_RULES.md` (instructions)
2. **Run script**: `./scripts/export-design-rules.sh`
3. **Adapt**: Follow guide for project-specific changes

### For Understanding Impact

1. **Before/after**: `DESIGN_BEFORE_AFTER.md` (visual comparison)
2. **Implementation**: `DESIGN_SYSTEM_IMPLEMENTATION.md` (what was built)
3. **Integration**: `CULTIVATE_INTEGRATION_SUMMARY.md` (how Cultivate was applied)

---

## Maintenance

### Updating the Design System

When design standards change:

1. Update `.cursor/rules/010-mission-control-design-system.mdc`
2. Update `DESIGN_QUICK_REFERENCE.md` with new patterns
3. Update affected components
4. Test on all pages
5. Document change in git commit
6. Re-export to other projects if needed

### Adding New Gates

When adding quality gates:

1. Update `.cursor/rules/020-mission-control-gates.mdc`
2. Implement enforcement in code
3. Add audit logging
4. Test that gates fire correctly
5. Document in `AGENTS.md`

### Adding New Agents

When adding agents:

1. Define in `AGENTS.md`
2. List key files
3. Define rules
4. Add to workflow
5. Create decision framework

---

## Search Tips

### Find specific patterns
```bash
# Typography patterns
grep -n "font-serif" DESIGN_QUICK_REFERENCE.md

# Color patterns
grep -n "text-green" DESIGN_QUICK_REFERENCE.md

# Component patterns
grep -n "MetricCard" DESIGN_QUICK_REFERENCE.md
```

### Find gate definitions
```bash
# Code quality gates
grep -n "Code Quality Gates" .cursor/rules/020-mission-control-gates.mdc

# Trading gates
grep -n "Trading System Gates" .cursor/rules/020-mission-control-gates.mdc
```

### Find agent responsibilities
```bash
# Dashboard agent
grep -n "Dashboard Agent" AGENTS.md

# All agents
grep -n "Agent" AGENTS.md | grep "###"
```

---

## Summary

Mission Control's design system is **comprehensive, documented, and exportable**:

📚 **10 documentation files** covering every aspect  
🎨 **440 lines** of design system rules  
🚪 **4 gate categories** for quality enforcement  
🤖 **6 specialized agents** with clear workflows  
📤 **One-command export** to other projects  

Everything you need to build institutional-grade trading dashboards with systematic quality.

---

**Last Updated**: March 7, 2026  
**Version**: 1.0.0  
**Framework**: Cultivate-inspired
