# Cursor-specific settings for this project

Quick reference so the AI and your workflow stay effective across sessions.

---

## 1. Turn on "Always search the web"

- **Where:** Cursor Settings → AI / Features → enable **"Always search the web"** (or equivalent in your Cursor version).
- **Why:** IBKR’s API (TWS/Gateway and ib_insync) has quirks, version-specific behavior, and subtle contract/order rules. Web search lets the AI pull current docs and examples when you ask about API behavior, error messages, or best practices.
- **Use when:** Asking about IBKR-specific behavior, ib_insync APIs, contract qualification, order types, or error codes.

---

## 2. Use Notepads for persistent strategy context

- **What:** Cursor Notepads are persistent notes that can be included in context across chats and sessions.
- **Use for:** Strategy logic you want the AI to remember without re-explaining:
  - Entry/exit rules in your own words
  - Which indicators or thresholds matter (e.g. NX composite, RS, structure)
  - Regime rules or allocation preferences
  - Symbols or universes you care about
- **Tip:** Keep one Notepad as a "strategy brief" and reference it when starting a session or when asking for changes that should respect your rules.

---

## 3. Use @codebase when changes span multiple files

- **When:** You’re asking for changes that touch several parts of the project (e.g. adding a new signal type end-to-end: screener → types → executor → log).
- **How:** In the chat input, use **@codebase** (or add it to the prompt) so Cursor indexes and considers the relevant files instead of only the current file or a small set of @-mentioned files.
- **Examples:**
  - "Add a new signal type X: screener output, types.py, and execute_dual_mode" → use **@codebase**
  - "Add a new gate to execution_gates and wire it in execute_candidates and execute_dual_mode" → use **@codebase**
  - Single-file edits (e.g. "fix this function") often don’t need it.

---

## Summary

| Setting / habit | Purpose |
|-----------------|--------|
| **Always search the web** | Better, up-to-date answers for IBKR/ib_insync API quirks |
| **Notepads** | Persistent strategy context across sessions |
| **@codebase** | Multi-file changes (new signals, gates, executors) get full context |
