# MASTER_PLAN.md — Four-Day Outcomes, Checkpoints and Cut-Lines

| Field | Value |
|---|---|
| **Status** | Approved specification. Day 0. No task has started. |
| **Authority** | Sixth, on schedule. Subordinate to `DECISIONS.md`, `BUSINESS_RULES.md`, `ACCEPTANCE_TESTS.md`, `PRD.md`, `TECH_STACK.md`, `ARCHITECTURE.md`. |
| **Budget** | 4 days × 5–7 focused hours ≈ **24 hours**, and this **includes** documentation time. |
| **Rule** | When reality diverges from these milestones, update this file in the same session. A silently missed checkpoint is a defect. |

---

## 1. The four outcomes

| Day | Outcome | Must-pass gate |
|---|---|---|
| **1** | Documentation generated and audited; the `Decimal` contribution engine reproduces the golden fixture | Approved, internally consistent docs **and** `1624.08` asserted exactly, with the critical unit tests green |
| **2** | CSV ingestion, persistence and the typed REST API are real and safe | Bad uploads do not crash, reimports do not duplicate, and the API returns figures grounded in the engine |
| **3** | The Budget Lab heuristics and all five views work end to end | Budget/MOQ/stock/cap invariants green, and the full core journey works locally |
| **4** | The project is reproducible, clean and honestly documented | Fresh-setup works from the README alone, test evidence exists, no secrets, a usable local demo |

**Launch gate (all six must hold):** documentation set complete and consistent; `pytest` green on a fresh clone; `npm run build` clean; the ₹1,624.08 fixture reproduced; no secrets and no real seller data; all five views usable at desktop and phone widths.

---

## 2. Hourly budget

| Day | Block | Hours | Notes |
|---|---|---|---|
| 1 | Documentation generation and audit | 1.5–2.0 | **Hard cap.** Prose is the first thing cut, never a formula or an acceptance value. |
| 1 | Environment setup + tooling (T01) | 0.5 | Includes recording the actually-resolved versions |
| 1 | Money primitives + assumptions + contribution engine + unit economics (T02–T05) | 3.5 | The highest-value block in the project |
| **1** | **Total** | **5.5–6.0** | |
| 2 | CSV validation core + attack/edge matrix (T06–T07) | 3.0 | |
| 2 | Persistence + seed (T08) | 1.5 | |
| 2 | Import/reconcile + API (T09–T10) | 2.0 | |
| **2** | **Total** | **6.5** | The heaviest day. T10 may slip into Day 3 morning; that is the expected slip. |
| 3 | Allocator + budget simulation (T11–T12) | 2.5 | |
| 3 | Frontend shell + Overview + Import (T13–T14) | 2.0 | |
| 3 | Profitability + Budget Lab (T15) | 2.0 | |
| **3** | **Total** | **6.5** | |
| 4 | Methodology view + responsive/a11y pass (T16 part 1) | 1.5 | |
| 4 | Stabilisation: fresh clone, lint, build, secret sweep, defect fixes (T16 part 2) | 2.5 | |
| 4 | README, screenshots, demo, `PROGRESS.md` close-out (T16 part 3) | 1.5 | |
| **4** | **Total** | **5.5** | |

Cumulative: **≈24 hours.** There is no slack for P1 work inside these four days.

---

## 3. Checkpoints

### CP-1 — end of the documentation block (Day 1, ~2 h in)
- All 13 documents plus `GLOSSARY.md` exist.
- Every internal link resolves.
- `CONTEXT.md` §4 accurately reports that no code exists.
- **Gate:** if a contradiction is unresolved, implementation does not start. Log it in `DECISIONS.md` or stop and ask.
- **Cut-line:** explanatory prose. Never a formula, an acceptance value, or a P0 boundary.

### CP-2 — end of Day 1
- `pytest backend\tests\test_profit.py` green, including `Decimal("1624.08")` exactly.
- `AT-2` rounding tests green; no float appears in any money result.
- `AT-4` unit-economics tests green.
- **Gate:** the golden fixture must reproduce before any CSV or database code is written. A fixture that is "close" is a blocker, not a rounding nuance.
- **Cut-line:** AT-1.6 to AT-1.8 (the variant expectations that still need hand-derivation), which may be deferred to Day 4 with a note.

### CP-3 — end of Day 2
- AT-5 (all 22 validation cases), AT-6 (idempotency and reconciliation) and AT-8 (API contract) green.
- Loading the synthetic sample seeds the database and prints an observed summary.
- **Gate:** an oversized, empty, binary or malformed upload produces a safe 4xx with nothing persisted, and re-uploading a file changes no row count.
- **Cut-line:** `budget_plan_runs` persistence. A simulation may be returned without being stored. Update `ARCHITECTURE.md` §5 to say so.

### CP-4 — end of Day 3
- AT-7 (all allocator invariants, including the 500-case randomised sweep) green.
- AT-10.1 to AT-10.9 green: the core journey works locally across all five views.
- **Gate:** the budget is never exceeded, every quantity is `0` or `≥ MOQ` and `≤ max_supply`, the capped plan respects its cap, and identical inputs give identical output.
- **Cut-line:** the Methodology view may ship as structured text with no styling. Charts are already out of P0.

### CP-5 — end of Day 4 (launch gate)
- AT-9, AT-10.10 to AT-10.15, AT-11 all green.
- Fresh clone + fresh virtual environment + README steps only → `pytest` green, `npm run build` clean.
- An independent hand recomputation of three SKUs agrees with the app.
- Screenshots depict the actually-running application.
- `PROGRESS.md` carries pasted command output for every claim.
- **Cut-line:** hosting and every P1 item.

---

## 4. Drop-list, in order

Cut from the top. **Never cut a P0 acceptance condition listed in `ACCEPTANCE_TESTS.md`.**

| # | Droppable | Why it is safe to drop |
|---|---|---|
| 1 | Public deployment | P1, and a local demo satisfies the definition of done |
| 2 | Extra visualisation and any chart | Explicitly P1 |
| 3 | Inventory warning | P1 at most |
| 4 | `DELETE /import/{batch_id}` | P1 |
| 5 | Methodology view styling | Content is required; polish is not |
| 6 | Persisting budget plan runs | A returned plan is enough to demonstrate the feature (requires an `ARCHITECTURE.md` update) |
| 7 | `cost_updated_on` handling | Retained in the schema, but no P0 behaviour consumes it |
| 8 | AT-1.6 to AT-1.8 variant expectations | Variants of the covered golden path; the primary fixture is never droppable |
| 9 | Frontend unit tests | AT-10 is a manual E2E matrix; there is no P0 row a unit test satisfies |
| 10 | Documentation prose polish | Last resort. Formulas, acceptance values and boundaries are never droppable. |

**Never droppable:** the ₹1,624.08 fixture; the gross-`units_sold` semantic; the settlement-override rule; `Decimal` money; the five views; the import safety cases; the frontend production build; the no-secrets rule.

---

## 5. Three-day stretch fallback

If a full day is lost, keep: CSV validation, the golden contribution engine, the Budget Lab, and one responsive Overview. Postpone persistence to an explicitly labelled **local-only, in-memory mode** — and say so in the README and `PROGRESS.md`. Do not claim a database-backed application if storage was dropped, and do not claim a view exists if it does not.

---

## 6. Working agreement

Per `AGENTS.md`:

- One bounded task at a time, never "build the app".
- The agent states the task, the files it will touch, the done condition and the proving acceptance IDs **before** editing.
- Test-first for logic, with expectations taken from `ACCEPTANCE_TESTS.md`.
- Run the targeted test, then the full backend suite, then the frontend build where relevant.
- Review the full diff, report exactly what passed, failed, skipped and was not run, and update `PROGRESS.md` with pasted output.
- Commit only after human approval. Never auto-push, never auto-deploy.
- Two agents never write the same files without isolated worktrees.

---

## 7. Risk watchlist for this plan

| Risk | Watch for | Response |
|---|---|---|
| Documentation overruns its 2-hour box | CP-1 drifting past Day 1 morning | Cut prose, start T01 immediately |
| The golden fixture will not reproduce | Any value other than `1624.08` | Treat as a code bug. Do not adjust the expectation (`AGENTS.md` rule 4) |
| `units_sold` read as net | Any figure near ₹2,624.08 where ₹1,624.08 is expected | Read `BUSINESS_RULES.md` §3 before touching a formula |
| Float money leaking in | A `float` in a money module, or a numpy import in `allocator.py` | Blocking review item (`DECISIONS.md` ADR-006) |
| UI re-implementing a formula | Arithmetic on a money value in `frontend/src` | Reject the change; money is a string on the client |
| Day 2 overrun | API not green by end of Day 2 | Take the CP-3 cut-line, move T10 to Day 3 morning |
| Scope creep into P2 | Any mention of SP-API, scraping, auth, trends, forecasting, Docker | Stop and ask (`AGENTS.md` §Stop conditions) |
| Time-pressure test weakening | A skipped test, an `xfail`, a suppression, a loosened assertion | Stop and ask. This is a stop condition, not a shortcut |

---

## Cross-references

- Task definitions and time estimates: `PHASES_DETAILED.md`
- Acceptance conditions referenced above: `ACCEPTANCE_TESTS.md`
- Evidence tracker: `PROGRESS.md`
- Decisions behind the boundaries: `DECISIONS.md`
- Stack and commands: `TECH_STACK.md`
