# MCP servers for this project

Cursor uses the config in **`.cursor/mcp.json`**. After editing, restart Cursor so changes apply. Toggle servers in **Settings → Tools & MCP**; view logs in **Output → MCP Logs**. Make sure **Filesystem** is enabled so the agent can read configs, `.env.example`, strategy docs, and trade logs.

---

## 1. Filesystem (`filesystem`)

- **Purpose:** Lets the AI read (and with care, write) your strategy configs, watchlists, risk.json, execution logs, and historical data under the project.
- **Server:** `@modelcontextprotocol/server-filesystem` (npx). Allowed directory: project root (`.`), so `trading/`, configs, and logs are accessible.
- **If it fails:** Use an absolute path instead of `.` in `args`, e.g. the full path to this repo (e.g. `"/Users/you/.../Mission Control"`).
- **Requires:** Node.js 18+ (for npx).

---

## 2. Fetch / docs (`fetch`)

- **Purpose:** Fetches web pages and converts them to markdown. Use it so the AI can pull **IBKR API** and **ib_insync** docs when generating or debugging code—the IBKR API is quirky and doc-accurate code is much more reliable.
- **Server:** `mcp-server-fetch` (uvx). No URL is “baked in”; the agent calls the `fetch` tool with a URL when needed.
- **Key doc URLs to keep in mind (for you or the AI):**
  - **IBKR API (TWS/Gateway):**  
    https://interactivebrokers.github.io/tws-api/
  - **ib_insync (Python):**  
    https://ib-insync.readthedocs.io/  
    - Specific pages the agent can fetch: API reference, `Order`/`Contract` types, `placeOrder`, `reqHistoricalData`, etc.
- **Requires:** [uv](https://docs.astral.sh/uv/) (`uvx` in PATH). If you don’t use uv, switch to pip in `mcp.json`:
  - `"command": "python", "args": ["-m", "mcp_server_fetch"]`
  - After: `pip install mcp-server-fetch`

---

## 3. SQLite (`sqlite`)

- **Purpose:** Once your trade log lives in a SQLite DB, the agent can answer questions like “why did we get stopped out on NVDA last Tuesday?” or “show me all trades where slippage exceeded 0.5%” by querying the DB directly.
- **Server:** `mcp-sqlite` (npx). DB path in `mcp.json`: `trading/logs/trades.db`.
- **Setup:** Create `trading/logs/` and, when you have a trade log DB, point to it (e.g. `trading/logs/trades.db`). If the file doesn't exist, the server may fail—create an empty DB or disable the server until you have one. To use a different path, change the last element in `args` in `mcp.json`.
- **If you don’t use a DB yet:** Disable the `sqlite` server in **Tools & MCP** or remove its entry so it doesn’t fail on startup.

---

## 4. GitHub (`github`)

- **Purpose:** Create issues, review PRs, and manage the repo from the editor. Useful for fast iteration on strategy logic with clear commit discipline.
- **Server:** `@modelcontextprotocol/server-github`, started via `.cursor/run_github_mcp.sh`, which sources your local **`.env`** so the token is never in `mcp.json`.
- **Setup:** Add `GITHUB_PERSONAL_ACCESS_TOKEN=your_token` to **`.cursor/.env.local`** (or project-root `.env`). The wrapper loads `.env` then `.cursor/.env.local` so local overrides win. Both are in `.gitignore`. Alternatively, set the token in **Settings → Tools & MCP** for the `github` server.
- **Requires:** Node.js 18+ and a [GitHub PAT](https://github.com/settings/tokens) with scopes needed for the repo (e.g. repo, read:org).

---

## 5. Docker (`docker`)

- **Purpose:** If you containerize the bot, the agent can manage containers, check logs, and restart services.
- **Server:** `mcp-server-docker` (uvx). Provides tools for container stats, log tailing, and managing containers/images/volumes.
- **Requires:** [uv](https://docs.astral.sh/uv/) and Docker (socket available to the process running the MCP server).

---

## 6. Postgres (`postgres`) — when you switch from SQLite

- **Purpose:** Same as SQLite MCP but for a PostgreSQL trade log: the agent can query the DB to answer questions like “why did we get stopped out on NVDA last Tuesday?” or “trades where slippage exceeded 0.5%”. Use **either** SQLite **or** Postgres for your trade log, not both in the same flow.
- **Server:** `@modelcontextprotocol/server-postgres` (npx). Read-only: runs queries in `READ ONLY` transactions; also exposes schema (tables, columns) as resources.
- **Setup:** In `mcp.json`, the last element in `args` is the connection string (e.g. `postgresql://localhost:5432/trades`). Replace with your real host, port, database, and optionally user/password (e.g. `postgresql://user:password@host:5432/dbname`). Keep credentials out of the repo: use a local override or env (if your setup supports it). Disable the server until Postgres is in use so it doesn’t fail on startup.
- **Requires:** Node.js 18+ and a running PostgreSQL instance.

---

## Quick reference

| Server   | Runtime | What the AI can do |
|----------|---------|--------------------|
| filesystem | npx   | Read/write project files (configs, logs, strategy docs) |
| sqlite   | npx     | Query SQLite trade log (stop-outs, slippage, by symbol/date) |
| postgres | npx     | Query Postgres trade log (same use cases; use when you switch from SQLite) |
| fetch    | uvx     | Fetch any URL (e.g. IBKR / ib_insync docs) as markdown |
| github   | npx     | Create issues, review PRs, manage repo |
| docker   | uvx     | Manage containers, check logs, restart services |
