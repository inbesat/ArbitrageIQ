# TECH_STACK.md — Approved Tools, Version Strategy and Local Commands

| Field | Value |
|---|---|
| **Status** | Approved specification. **No dependency has been installed. No command in this file has been run.** |
| **Authority** | Fifth. Overrides `MASTER_PLAN.md` and `PHASES_DETAILED.md` on tooling. Subordinate to `DECISIONS.md` (ADR-001 to ADR-006), `BUSINESS_RULES.md`, `ACCEPTANCE_TESTS.md`, `PRD.md`. |
| **Change control** | Changing a dependency, a major version, or a command requires a new `DECISIONS.md` entry. |

> ## ⚠️ Honesty note on versions
> No version number, compatibility claim, free-tier limit, or package availability in this document has been verified against PyPI, npm, or any vendor's current documentation. The **ranges below express compatibility intent, not a verified fact.** At creation time (task T01), the implementing agent must install, let the resolver pick, pin the exact resolved versions into `requirements.txt` and `package-lock.json`, and **record the actual installed versions in `PROGRESS.md`**. Only then does this document become a statement of fact.

---

## 0. Verified at T01 (2026-10-26)

`TECH_STACK.md` §7 step 5 requires either stating verified facts here or leaving the ranges as
explicit intent. The versions below are **observed facts**, recorded with their commands; the intent
ranges in §1–§3 that they do not match are **left in place and marked as unmatched**, because changing
a major version or a command needs a `DECISIONS.md` entry under §7 change control.

| Item | This document intends | **Observed at T01** | Match? |
|---|---|---|---|
| Python | 3.12 (`>=3.11,<3.13`) | **3.14.2** — `E:\ArbitrageIQ\.venv\Scripts\python.exe --version` | **No** — `PROGRESS.md` §8 DEV-4 |
| Python launcher | `py -3.12` | `py` **fails** in this shell ("The file cannot be accessed by the system"); the interpreter is reachable by absolute path only | **No** — `PROGRESS.md` §6, §8 |
| Node.js | 20 LTS (`>=20,<22`) | **v24.14.1** | **No** — `PROGRESS.md` §8 DEV-5 |
| npm | (unversioned) | **11.14.1** | n/a |
| Vite | 5 | **5.4.21** (resolved) | Yes |
| pandas | "pandas 2.x" (§2) | **3.1.0** (with `numpy==2.5.4`) | **No** — `PROGRESS.md` §8 DEV-3 |
| FastAPI | (unversioned) | **0.162.0** | n/a |
| Starlette | (implied by FastAPI) | **1.10.0** — deprecates `httpx` for `TestClient` in favour of `httpx2` | **Note** — `PROGRESS.md` §7 D-3 |
| uvicorn | (unversioned) | **0.54.0** | n/a |
| SQLAlchemy | 2.x | **2.1.6** | Yes |
| Pydantic | v2 | **2.14.1** | Yes |
| Ruff | (unversioned) | **0.17.2** | n/a |
| pytest | (unversioned) | **9.1.1** | n/a |
| Backend deps | resolved and pinned at T01 | **33 packages pinned** in `backend\requirements.txt`; `pip install -r backend\requirements.txt` → exit 0 from the pinned file | Yes |
| Frontend deps | `package-lock.json` committed | **137 packages** pinned in `frontend\package-lock.json`; `npm ci` → exit 0 | Yes |

**Verified commands at T01** (full output in `PROGRESS.md` §2): `pip install -r backend\requirements.txt` → exit 0; `GET /health` → `200 {"status":"ok"}` over a real socket; `ruff check backend` → "All checks passed!"; `npm ci` and `npm run build` → exit 0; `npx tsc --noEmit` → clean.

**§5.3's documented run command does not work on this machine** (`uvicorn arbitrageiq.api:app --port 8000` crashes the accept path under Python 3.14.2's Proactor event loop — `PROGRESS.md` §7 D-1). The working workaround is recorded there. **The command in §5.3 has deliberately not been rewritten**, because §7 change control requires a `DECISIONS.md` entry first. That entry is an open human action item.

Regenerate these numbers with `pip freeze` and `npm ls --depth=0`; do not copy them forward from this table after a dependency change.

---

## 1. Runtime and platform

| Item | Target | Note |
|---|---|---|
| OS | Windows 11, PowerShell 7+ (Windows PowerShell 5.1 must also work) | The brief's commands are PowerShell. No Bash-only steps. |
| Python | 3.12 (`>=3.11,<3.13` as the compatibility window) | 3.11+ is intended to supply the `X \| None` syntax used throughout — unverified; confirm at T01. **Observed at T01: 3.14.2, outside this window (§0).** |
| Node.js | 20 LTS (`>=20,<22`) | Vite 5 and React 18 are intended to build on Node 20 — unverified; confirm at T01. **Observed at T01: v24.14.1, outside this window; the build nevertheless succeeded (§0).** |
| Package manager (JS) | `npm` with a committed `package-lock.json` | One package manager only; no pnpm/yarn mixture. |
| Shell conventions | Paths with backslashes; use `py -3.12` rather than `python` to avoid Windows launcher ambiguity | |

---

## 2. Backend stack

| Concern | Choice | Why | Rejected alternative |
|---|---|---|---|
| Language | Python 3.12 | Brief mandate; pandas ecosystem | |
| Web framework | FastAPI | Typed request/response models, automatic OpenAPI at `/docs`, validation errors for free | Flask (no schema layer); Django (far too much for nine endpoints) |
| ASGI server | uvicorn | Standard FastAPI pairing, single-process is enough | gunicorn (POSIX-oriented, unnecessary here) |
| Validation / serialisation | Pydantic v2 | Native `Decimal` support and JSON-schema generation; the money-as-string contract depends on it | dataclasses + manual validation (no schema, no `/docs`) |
| ORM | SQLAlchemy 2.x | Explicit models, `NUMERIC` mapping for `Decimal`, no magic | raw `sqlite3` (verbose, no models); an ORM-less query builder (no migration path) |
| Database | SQLite | Zero setup, file-based, disposable (`DECISIONS.md` ADR-005) | PostgreSQL, Docker — deferred to P2 |
| Data loading | pandas 2.x | Brief mandate. Used **only** for CSV I/O and shape inspection | Python `csv` (would work, but pandas is specified and better at encoding edge cases). **Observed at T01: 3.1.0 resolved (§0) — needs a decision.** |
| Money | Python `decimal.Decimal` | Exact decimal arithmetic; the whole financial model depends on it | `float` (banned, ADR-006); `int` paise everywhere (retained only for budget comparison, ADR-006) |
| Server-rendered templates | none | The frontend is a separate SPA | Jinja2 |

### 2.1 What pandas is and is not allowed to do

- **Allowed:** reading a CSV as text (`dtype=str`), inspecting shape, reporting row counts.
- **Forbidden:** any monetary arithmetic. pandas will coerce to `float64`. Money is parsed to `Decimal` cell by cell, after reading as text.

This is a structural rule, not a style preference, and it is the reason `validation.py` must not import `profit.py` (`ARCHITECTURE.md` §3).

### 2.2 `requirements.txt` shape (ranges are intent only)

```
fastapi
uvicorn[standard]
pydantic>=2
sqlalchemy>=2
pandas>=2
python-multipart
pytest
httpx
ruff
```

`python-multipart` is intended for FastAPI's multipart file upload; `httpx` is intended to back FastAPI's `TestClient` (unverified — confirm at T01). Versions are resolved and pinned at T01.

---

## 3. Frontend stack

| Concern | Choice | Why | Rejected alternative |
|---|---|---|---|
| Framework | React 18 | Brief mandate; component model suits the plan-comparison UI | Streamlit (ADR-001); Svelte, Vue (not specified, no advantage here) |
| Build tool | Vite 5 | Fast dev server, one-command production build that the acceptance criteria depend on | CRA (reportedly deprecated and slow — unverified) |
| Language | TypeScript 5 | The money-as-string contract and API types need compile-time enforcement | plain JS (no contract safety) |
| Styling | Tailwind CSS 3 | One system, no bespoke design language to maintain (`DECISIONS.md` AP-2) | plain CSS modules (more code); a component library (heavyweight, generic look) |
| Routing | React Router | Five routes; the standard choice | hand-rolled routing (needless) |
| Server state | none — a typed `fetch` wrapper in `api/client.ts` | Five views with local state do not justify a query library | React Query, Redux (added surface — see `ARCHITECTURE.md` §8) |
| Charts | **none in P0** | The brief lists extra visualisation as P1 | Recharts / Chart.js — P1 only |
| Icons | inline SVG, no icon package | A handful of glyphs do not justify a dependency | an icon library |

### 3.1 Money on the client

`api/types.ts` declares every monetary field as `string`. The client **never** calls `parseFloat`, `Number()`, or any arithmetic on a money value. It formats for display only. This is what keeps a single source of financial truth (ADR-024, `AGENTS.md` rule 7).

---

## 4. Test and quality tooling

| Purpose | Tool | Scope |
|---|---|---|
| Backend tests | pytest | Unit + integration, `backend/tests` |
| HTTP tests | FastAPI `TestClient` (via `httpx`) | Endpoint contract, error bodies, status codes |
| Property tests | pytest + `hypothesis` (add only if AT-7.1's 500-case random sweep is slow to write by hand) | Allocator invariants |
| Python lint + format | Ruff | `ruff check`, `ruff format --check` |
| Float-in-money guard | Ruff rule configuration | A rule banning float literals that are **used as money** (operands of money arithmetic, or money-typed assignments) in `money.py`, `profit.py` and the money paths of `allocator.py`. A dimensionless fraction cap such as `min(1, sell_through)` is not money and is permitted. If Ruff cannot express the distinction, a small pytest that walks the AST of those modules is the fallback — decide at T01 and record it. |
| Frontend types | `tsc --noEmit` | Must be clean |
| Frontend build | `vite build` | Must succeed; this is a P0 acceptance condition |
| Frontend tests | **none in P0** | Justified by `ACCEPTANCE_TESTS.md` AT-10 being a manual E2E matrix. Adding a test runner is surface without a P0 acceptance row to satisfy. If time remains, Vitest on the money-formatting helper only. |

---

## 5. Exact local commands (Windows PowerShell)

Run from the repository root unless stated.

### 5.1 Backend — first-time setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

If `Activate.ps1` is blocked by execution policy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 5.2 Backend — database

```powershell
# run from backend\
python -m arbitrageiq.db init
python -m arbitrageiq.db seed
```

`init` creates the schema; `seed` loads `data/sample/` and prints a summary of what it inserted. Neither command may invent real data.

### 5.3 Backend — run and verify

```powershell
# run from backend\
uvicorn arbitrageiq.api:app --reload --port 8000

# from the repository root, virtual environment active
pytest backend\tests -q
pytest backend\tests\test_profit.py -q
ruff check backend
ruff format --check backend
```

### 5.4 Frontend — first-time setup, run and verify

```powershell
cd frontend
npm ci
```

```powershell
cd frontend
npm run dev          # dev server, prints the local URL
npm run build        # production build; must succeed before a task is called done
npx tsc --noEmit     # type check only
```

### 5.5 Regenerating the synthetic fixtures

```powershell
python scripts\make_sample_data.py
```

The generator must be deterministic: the same command produces byte-identical output on every run (`BUSINESS_RULES.md` §11.5 invariant B7 applies to the allocator, and the same determinism principle applies to fixtures).

### 5.6 Pre-commit verification sweep

```powershell
git grep -n -i -E "password|secret|token|api[_-]?key"
git log -p -S "password" -- "*.py" "*.ts" "*.tsx"   # history sweep; a deleted secret is still leaked
git status --short
pytest backend\tests -q
cd frontend; npm run build
```

---

## 6. Tooling explicitly rejected

| Tool | Why rejected |
|---|---|
| **Docker / Docker Compose** | Adds setup time the four-day budget cannot absorb and proves nothing that SQLite does not. P2. |
| **PostgreSQL** | Same reason; SQLite has no operational cost for a single local user. P2 (`DECISIONS.md` ADR-005). |
| **Alembic** | Migration tooling for a schema that is created from scratch on every demo run. P2. |
| **Streamlit** | Cannot deliver the responsive, non-colour-dependent comparison UI the brief requires (`DECISIONS.md` ADR-001). |
| **A design-system package (MUI, Chakra, shadcn)** | Imports a visual language the brief already specifies (navy/near-white, teal/green, amber) and adds a large surface for five views. |
| **A state-management library** | Five views, view-local state. Nothing to manage globally except the assumption set. |
| **A charting library in P0** | Visualisation is explicitly P1. |
| **`numpy` in the allocator** | Would reintroduce float money (ADR-006). Pure-`Decimal` greedy is fast enough for the catalogue sizes involved. |
| **Authentication, JWT, OAuth** | P2. The tool is local and single-user. |
| **Paid cloud services, hosted databases, CI runners** | The brief's four-day scope excludes paid services. A local demo is an acceptable outcome. |
| **A hosted free-tier deployment as a P0 requirement** | Deployment is P1 and optional (`DECISIONS.md` ADR-003). |

---

## 7. Version-pinning procedure (task T01)

1. Create the virtual environment and install the backend dependencies **without** version pins.
2. Run `pip freeze > backend\requirements.txt`.
3. Create the frontend and run `npm install` so `package-lock.json` is produced.
4. Record the actually-resolved versions in `PROGRESS.md` under the T01 entry, with the observed command output.
5. Only then update the version tables above to state verified facts, or leave them as intent and say so explicitly.

**Until step 4 is done, this document describes intentions, not facts.**

---

## Cross-references

- Decisions behind each choice: `DECISIONS.md` ADR-001 to ADR-006, AP-2
- The layout these tools build: `ARCHITECTURE.md`
- Acceptance conditions that depend on the build and test commands: `ACCEPTANCE_TESTS.md` AT-11
- Security tooling and the secret sweep: `SECURITY.md`
- Task that executes this setup: `PHASES_DETAILED.md` T01
