# CONTEXT.md — Documentation Index and Source-of-Truth Order

| Field | Value |
|---|---|
| **Purpose** | The canonical index of every document in this project, and the authority order to use when two documents disagree. |
| **Status** | Approved specification. No source code exists yet. |
| **Maintenance rule** | If a document is added, renamed, or deleted, this file is updated in the same change. A link here that does not resolve is a defect. |
| **Read this first** | Yes. Every agent session should read this file and `AGENTS.md` before touching anything. |

---

## 1. What this project is

**ArbitrageIQ** is a local decision-support tool for a small Indian ecommerce reseller. It helps them evaluate wholesale products, understand **contribution profit** per SKU after configurable fees, GST and refund assumptions, and compare how to spend a ₹50,000 inventory budget under uncertainty.

It is **not** a scraper, a sales forecaster, an accounting system, a tax adviser, or an Amazon automation tool. All public sample data is **synthetic**.

- Product scope and boundaries → `PRD.md`
- Money rules → `BUSINESS_RULES.md`
- System shape → `ARCHITECTURE.md`

---

## 2. Document index

| File | Purpose | Read when | Update when |
|---|---|---|---|
| `../AGENTS.md` | Persistent engineering instructions for any agent working in this repo | Always, first | The working method changes |
| `CONTEXT.md` | This index and the authority order | Always, first | Any document is added, renamed, or deleted |
| `BUSINESS_RULES.md` | **Authoritative** formulas, field semantics, GST/fee/refund treatment, rounding, data schemas, the golden fixture | Writing or reviewing any financial logic or schema | A formula, a semantic, the rounding rule, or the fixture changes — requires human approval |
| `ACCEPTANCE_TESTS.md` | **Authoritative** independently defined expected values and the acceptance matrix | Defining a task's done condition, or reviewing a test | An expected value changes — requires human approval and a `DECISIONS.md` entry |
| `DECISIONS.md` | Dated ADRs: decision, context, alternative rejected, consequences | Before proposing a change to an approved choice; when resolving a conflict | Any decision is made, changed, or superseded. Append only |
| `PRD.md` | Personas, journeys, the five views, MVP boundaries, empty/error states, definition of done | Planning UI or scope work | Product scope changes — requires human approval |
| `ARCHITECTURE.md` | Modular-monolith structure, module dependency rules, repository tree, ERD, API boundaries | Writing any backend or frontend code | Real code diverges from the description |
| `TECH_STACK.md` | Chosen tools, version strategy, exact local commands, alternatives rejected | Setting up or running the project | A dependency or command changes — requires a `DECISIONS.md` entry |
| `MASTER_PLAN.md` | The 4-day outcomes, checkpoints, timeboxes, cut-list and launch gate | Starting a day's work; deciding what to cut | Reality diverges from the milestones |
| `PHASES_DETAILED.md` | 16 bounded implementation tasks with prerequisites, file ownership, done conditions, tests, fallbacks | Picking up the next task | A task is split, added, or removed (stays within 12–16) |
| `SECURITY.md` | Trust boundaries, CSV upload safety, data privacy, secrets, logging, export safety | Touching input handling, storage, logging, or exports | A control changes |
| `INTEGRATIONS.md` | What exists locally today, the REST interface, and what is explicitly deferred with its access caveats | Wondering whether something is wired up | An integration is added or deferred |
| `PROGRESS.md` | Evidence-based Done / Doing / Blocked / Next, with observed command output | Starting or ending a work session | After every implemented slice |
| `GLOSSARY.md` | One-line definitions of the terms this project uses precisely | Unsure what a word means here | A term is introduced or redefined |

---

## 3. Source-of-truth order (for conflicts)

When two documents disagree, the higher entry wins:

```
1. An approved, dated entry in DECISIONS.md          (human-approved decisions)
2. BUSINESS_RULES.md                                 (money and data semantics)
3. ACCEPTANCE_TESTS.md                               (required observed outcomes)
4. PRD.md                                            (scope, UX, product boundaries)
5. TECH_STACK.md and ARCHITECTURE.md                 (technology and structure)
6. MASTER_PLAN.md and PHASES_DETAILED.md             (schedule and task breakdown)
```

`AGENTS.md` governs **how work is done**. It never overrides a formula, an expected value, or a scope boundary.

**Hard rules on conflicts**

- **C1.** Never silently pick whichever file was opened last. Surface the conflict, and record the resolution as a new dated entry in `DECISIONS.md`.
- **C2.** Never edit `BUSINESS_RULES.md` or `ACCEPTANCE_TESTS.md` to make a test pass. A failing test means the code is wrong first; only a hand-checked, human-approved derivation may change an expected value.
- **C3.** A statement in the original planning brief or the project handbook that this document set contradicts is resolved by `DECISIONS.md`, not by re-reading the PDFs.
- **C4.** If a conflict cannot be resolved without a human decision, stop and ask. Do not guess and proceed.

---

## 4. Status of this documentation set

| Aspect | State |
|---|---|
| Documents in this set | 13 requested + `GLOSSARY.md` |
| Source code | **None. Not started.** |
| Tests run | **None. No test results exist.** |
| Dependencies installed | **None.** |
| Data | No real data of any kind. Sample fixtures are synthetic and are created during implementation. |
| Approvals outstanding | See `DECISIONS.md` §"Open approvals" |

> Any claim that a test passes, a build succeeds, or an endpoint works is invalid until `PROGRESS.md` carries pasted command output.

---

## 5. Original source material

Two external documents informed this specification set. Neither is maintained here, and neither is authoritative over this set.

| Document | Role |
|---|---|
| `ArbitrageIQ_OpenCode_Planning_First_4_Day.pdf` (V2.0, 26 Oct 2026) | The planning brief. Defines the 4-day scope, the P0/P1/P2 boundary, the 13-file set, and the ₹1,624.08 fixture. |
| `ArbitrageIQ_Project_Handbook.pdf` (94 pp, 15 Oct 2026) | Supporting financial and pedagogical reference. Source of the worked scenario, the rounding rule, and the schemas. Its own code was never executed by its author and must be treated as a specification sketch, not working software. |

Both are recorded in `DECISIONS.md` with the specific points where this set departs from them and why.

---

## 6. Where to start

- **New agent session:** `../AGENTS.md` → `CONTEXT.md` → `PROGRESS.md` → the one task in `PHASES_DETAILED.md`.
- **Writing financial logic:** `BUSINESS_RULES.md` → `ACCEPTANCE_TESTS.md` → `ARCHITECTURE.md`.
- **Writing UI:** `PRD.md` §views → `ARCHITECTURE.md` §API boundaries → `TECH_STACK.md`.
- **Reviewing a change:** `ACCEPTANCE_TESTS.md` §traceability → `SECURITY.md`.
