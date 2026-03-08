# Mission Control Design System

**Status**: Production Ready  
**Framework**: Cultivate-inspired  
**Version**: 1.0.0  
**Date**: March 7, 2026

---

## Overview

Mission Control now has a complete design system and agent framework inspired by the Cultivate methodology. This system ensures institutional-grade quality, systematic workflows, and exportable design standards.

---

## Quick Start

### For Developers Working on Mission Control

1. **Read the design system**
   ```bash
   cat .cursor/rules/010-mission-control-design-system.mdc
   ```

2. **Use the quick reference for patterns**
   ```bash
   cat DESIGN_QUICK_REFERENCE.md
   ```

3. **Check quality gates before committing**
   ```bash
   cat .cursor/rules/020-mission-control-gates.mdc
   ```

4. **Follow agent workflows**
   ```bash
   cat AGENTS.md
   ```

### For Exporting to Other Projects

```bash
# Export design rules to another project
./scripts/export-design-rules.sh "../YourOtherProject"

# Read the export guide for details
cat EXPORT_DESIGN_RULES.md
```

---

## What's Included

### 1. Design System
**File**: `.cursor/rules/010-mission-control-design-system.mdc`

- Typography (Playfair Display + Inter + JetBrains Mono)
- Color system (stone neutrals, semantic profit/loss colors)
- Layout and spacing scale
- Component patterns (cards, tables, badges, alerts)
- Accessibility (WCAG 2.2 AA)
- Data visualization guidelines
- Number formatting standards
- Voice & tone rules
- Micro-interactions
- Responsive design

### 2. Quality Gates
**File**: `.cursor/rules/020-mission-control-gates.mdc`

- Code quality gates (type safety, error handling)
- Trading system gates (risk limits, position sizing)
- Dashboard quality gates (WCAG, real data, performance)
- Deployment gates (build, lint, tests)
- Audit trail for gate rejections
- Emergency bypass protocol

### 3. Agent System
**File**: `AGENTS.md`

- 6 specialized agents (Trading, Dashboard, Data, Audit, Testing, Design)
- Clear roles and responsibilities
- Agent coordination patterns
- Decision frameworks
- Workflows for features, bugs, and deployments

### 4. Export System
**Files**: `scripts/export-design-rules.sh`, `EXPORT_DESIGN_RULES.md`

- Automated export script
- Export guide with adaptation instructions
- Simplification guide for non-trading projects

### 5. Documentation
**Files**: `DESIGN_SYSTEM_IMPLEMENTATION.md`, `DESIGN_QUICK_REFERENCE.md`, `CULTIVATE_INTEGRATION_SUMMARY.md`

- Complete implementation overview
- Copy-paste patterns for developers
- Comparison to Cultivate framework
- Maintenance guide

---

## File Structure

```
Mission Control/
├── .cursor/rules/
│   ├── 010-mission-control-design-system.mdc  ← Design system
│   └── 020-mission-control-gates.mdc          ← Quality gates
├── scripts/
│   └── export-design-rules.sh                 ← Export automation
├── AGENTS.md                                   ← Agent system
├── EXPORT_DESIGN_RULES.md                     ← Export guide
├── DESIGN_SYSTEM_IMPLEMENTATION.md            ← Implementation overview
├── DESIGN_QUICK_REFERENCE.md                  ← Developer quick reference
├── CULTIVATE_INTEGRATION_SUMMARY.md           ← Integration summary
└── README_DESIGN_SYSTEM.md                    ← This file
```

---

## How to Use

### When Creating a New Component

1. Check `DESIGN_QUICK_REFERENCE.md` for similar patterns
2. Follow typography and color guidelines
3. Ensure WCAG AA contrast
4. Add hover states and transitions
5. Test on mobile/tablet/desktop
6. Run linter before committing

### When Adding a New Feature

1. Follow agent workflow in `AGENTS.md`
2. Plan → Implement → Test → Gates → Deploy → Monitor
3. Check all relevant quality gates
4. Log decisions to audit trail
5. Document in commit message

### When Fixing a Bug

1. Check audit trail for context
2. Reproduce the issue
3. Implement fix with test case
4. Verify fix locally
5. Monitor for 24 hours after deployment

---

## Design System Highlights

### Typography
- **Playfair Display** (serif) for headers and large numbers - emotional impact
- **Inter** (sans-serif) for body text and UI - readability
- **JetBrains Mono** (monospace) for prices and data - precision

### Colors
- **Green** = profit, long positions
- **Red** = loss, short positions
- **Stone** = neutral palette (warmer than gray)
- **Slate-900** = primary text (not pure black)

### Components
- Metric cards with hover effects
- Data tables with semantic HTML
- Badges for categories and status
- Alerts with severity-based styling
- Progress bars with warning states

### Accessibility
- All text meets WCAG 2.2 AA (4.5:1 contrast)
- Visible focus states on all interactive elements
- Color + text + icons (never color alone)
- Semantic HTML structure
- Keyboard navigation

---

## Quality Gates Summary

### Code Quality
✅ Type safety (no `any`)  
✅ Type guards for external data  
✅ No console.log (console.error in catch blocks is OK)  
✅ Error handling for all API calls  
✅ Alt text on all images  

### Dashboard Quality
✅ Works with real IBKR data  
✅ Error states handled gracefully  
✅ Loading states shown  
✅ WCAG AA compliance  
✅ Responsive design  
✅ Performance (<2s load)  

### Deployment
✅ Build success  
✅ Linter clean  
✅ Git clean  
✅ Documentation updated  

---

## Agent Roles Summary

| Agent | Role | Key Files |
|-------|------|-----------|
| 🎯 Trading System | Strategy development | `trading/scripts/execute_*.py` |
| 📊 Dashboard | UI/UX and visualization | `trading-dashboard-public/app/**/*.tsx` |
| 🔍 Data | Data aggregation | `trading/scripts/dashboard_data_aggregator.py` |
| 🛡️ Audit | Logging and monitoring | `trading/scripts/audit_logger.py` |
| 🧪 Testing | Backtesting and validation | `trading/backtest/nx_backtest.py` |
| 🎨 Design | Design system enforcement | `.cursor/rules/010-*.mdc` |

---

## Exporting to Other Projects

### Quick Export
```bash
./scripts/export-design-rules.sh "../OtherProject"
```

### What Gets Copied
- Design system rule (`.cursor/rules/010-mission-control-design-system.mdc`)
- Quality gates rule (`.cursor/rules/020-mission-control-gates.mdc`)
- Agent system (`AGENTS.md`)

### After Export
1. Update project-specific paths
2. Adapt design system to your brand
3. Simplify AGENTS.md if not a trading system
4. Test that rules apply correctly
5. Commit to git

**See `EXPORT_DESIGN_RULES.md` for detailed instructions.**

---

## Comparison to Cultivate

### What We Adopted from Cultivate ✅
- Gate enforcement at every phase
- Structured agent organization
- Automation focus
- Decision frameworks
- Professional quality standards

### What We Adapted for Trading 🔄
- Color semantics (green/red for P&L)
- Typography (serif for emotional impact)
- Tone (institutional vs consumer)
- Data visualization (canvas charts)
- Domain-specific gates (risk limits)

### What We Didn't Need ❌
- Brand landscape (private dashboard)
- Landing pages (not a marketing site)
- Voice & tone glossary (simpler requirements)
- Visual asset stack (data-focused)

---

## Current Status

### ✅ Complete
- Design system documented
- Quality gates defined
- Agent system established
- Export script created
- All documentation written
- Fonts configured (Playfair + Inter + JetBrains Mono)
- Dashboard follows design system
- All quality gates pass

### 🔄 In Progress
- None

### 📋 Future Enhancements
- Add unit tests for components
- Create component library (Storybook)
- Implement keyboard shortcuts
- Add visual regression tests
- Create loading skeleton components

---

## Resources

| Document | Purpose |
|----------|---------|
| `.cursor/rules/010-mission-control-design-system.mdc` | Complete design system |
| `.cursor/rules/020-mission-control-gates.mdc` | Quality gates |
| `AGENTS.md` | Agent roles and workflows |
| `DESIGN_QUICK_REFERENCE.md` | Copy-paste patterns |
| `EXPORT_DESIGN_RULES.md` | Export instructions |
| `DESIGN_SYSTEM_IMPLEMENTATION.md` | Implementation details |
| `CULTIVATE_INTEGRATION_SUMMARY.md` | Integration summary |
| `scripts/export-design-rules.sh` | Export automation |

---

## Support

### Questions?
- **Design patterns**: Check `DESIGN_QUICK_REFERENCE.md`
- **Quality gates**: Check `.cursor/rules/020-mission-control-gates.mdc`
- **Agent workflows**: Check `AGENTS.md`
- **Export help**: Check `EXPORT_DESIGN_RULES.md`

### Issues?
- Check audit trail: `trading/logs/audit_trail.json`
- Check dashboard logs: `trading/logs/dashboard_aggregator.log`
- Check browser console for frontend errors
- Review recent commits for changes

---

## Summary

Mission Control now has a **production-ready design system** inspired by Cultivate:

✅ Comprehensive design rules  
✅ Systematic quality gates  
✅ Clear agent roles  
✅ Automated export  
✅ Complete documentation  

The system is **institutional-grade** and can be exported to other projects with minimal adaptation.

---

**Last Updated**: March 7, 2026  
**Maintained By**: Mission Control Team  
**Framework**: Cultivate-inspired
