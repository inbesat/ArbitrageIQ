# AGENTS.md — ArbitrageIQ Engineering Instructions

Persistent instructions for any agent working in this repository. Short by design. Project facts live in `plans/`.

## What this project is

A local decision-support tool for an Indian ecommerce reseller: import product and transaction CSVs, compute **contribution profit** per SKU with configurable fee/GST/refund assumptions, and compare two heuristics for spending a ₹50,000 inventory budget. Demo data is synthetic; only the operator's own CSVs may be imported. Not a scraper, forecaster, tax adviser, or automation tool.

Stack: Python + FastAPI + SQLAlchemy + SQLite (backend), React + Vite + TypeScript (frontend). Money is always `Decimal`.

## Read order

1. `plans/CONTEXT.md` — the document index and the source-of-truth order.
2. `plans/PROGRESS.md` — what is actually done, doing, blocked, next.
3. The **one** task in `plans/PHASES_DETAILED.md` you are about to work on.
4. Only the spec sections that task names. Do not preload the whole `plans/` directory.

## Source-of-truth order (full statement in `plans/CONTEXT.md` §3)

1. An approved, dated entry in `plans/DECISIONS.md`
2. `plans/BUSINESS_RULES.md` (money and data)
3. `plans/ACCEPTANCE_TESTS.md` (required observed outcomes)
4. `plans/PRD.md` (scope and UX)
5. `plans/TECH_STACK.md` and `plans/ARCHITECTURE.md`
6. `plans/MASTER_PLAN.md` and `plans/PHASES_DETAILED.md`

This file governs **how** work is done; it never overrides a formula. A disagreement is surfaced and logged, never guessed away.

## Non-negotiable rules

1. **Plan before editing.** State: which task, which files you will touch, what the done condition is, and which acceptance IDs (`AT-n`) prove it. If any of that is unclear, stop and ask.
2. **One bounded task at a time.** One vertical slice. Never "build the app". Never two agents writing the same files without isolated worktrees.
3. **Test-first for logic.** Write or update the failing assertion first, derived from `plans/ACCEPTANCE_TESTS.md`. Never derive an expected value from the function under test.
4. **Never edit `plans/BUSINESS_RULES.md` or `plans/ACCEPTANCE_TESTS.md` to make a test pass.** A failure means the code is wrong first. Changing an expected value requires human approval and a `DECISIONS.md` entry.
5. **No `float` for money.** Not in arithmetic, not in storage, not in JSON. `Decimal` in Python, `NUMERIC` in SQLite, decimal strings on the wire.
6. **`units_sold` is GROSS and includes returned units.** Read `plans/BUSINESS_RULES.md` §3 before writing any formula.
7. **The backend is the only place money is calculated.** The UI renders what the API returns. Never re-implement a formula in TypeScript.
8. **Verify before claiming.** Run the checks. Then report exactly what passed, what failed, what was skipped, and what was not run. No run logs may be invented.
9. **Update `plans/PROGRESS.md`** with pasted command output after each implemented slice. Evidence, not adjectives.
10. **No secrets, no real seller data.** Synthetic and owner-authorised data only. `data/private/`, `.env`, and database files stay gitignored.
11. **No live integrations.** No Amazon calls, no scraping, no order execution, no auth. All are P2 and out of scope.
12. **Never claim optimality or prediction.** The allocator is two transparent heuristics. The UI must never contain "optimal", "guaranteed", or "AI predicts sales".
13. **Diff review before commit.** Read the full diff. Commit only after human approval. Never auto-deploy, never auto-push.
14. **Scope discipline.** P0 first. P1 only after every P0 acceptance row passes. P2 is not in this project.

## Safe commands (Windows PowerShell, from the repo root)

Backend:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pytest backend\tests -q
ruff check backend
uvicorn arbitrageiq.api:app --reload --port 8000   # run from backend\
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev      # dev server
npm run build    # production build; must succeed before a task is called done
npx tsc --noEmit # type check
```

Verification sweep before calling anything done:

```powershell
git grep -n -i -E "password|secret|token|api[_-]?key"   # must be empty of real values
git log -p -S "password" -- "*.py" "*.ts" "*.tsx"        # history sweep; a deleted secret is still leaked
git status --short                                       # nothing unintended
```

If a command's exact form is uncertain, check `plans/TECH_STACK.md` rather than guessing.

## Reporting format

After each slice, report in this shape and nothing longer:

```
Task:        T##
Files:       <paths touched>
Done when:   <condition from PHASES_DETAILED.md>
Acceptance:  AT-x.y  ->  <observed output>
Tests run:   <command>  ->  <result, or "not run: <reason>">
Backend:     <command>  ->  <result, or "not run: <reason>">
Build:       <command>  ->  <result, or "not run: <reason>">
Skipped:     <what and why>
Next:        <one line>
```

If a check was not run, say so. Silence is never a pass.

## Escape hatch

Every task in `plans/PHASES_DETAILED.md` names a fallback. If a task exceeds its timebox, take the fallback, report it, and update `plans/MASTER_PLAN.md`. Do not silently continue past the box and do not quietly drop the acceptance condition.

## Stop conditions — ask a human before proceeding

- A task requires changing a formula, a field semantic, a rounding rule, or an expected value.
- A conflict appears between two documents. Resolve via `plans/CONTEXT.md` §3 and log it in `plans/DECISIONS.md`.
- A task appears to require a P2 capability.
- A test cannot be made to pass without weakening it, skipping it, or adding a suppression.
- Real data, credentials, or an external service would be needed.
