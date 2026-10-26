# SECURITY.md — Trust Boundaries, Upload Safety, Privacy and Data Lifecycle

| Field | Value |
|---|---|
| **Status** | Approved specification. Nothing here is implemented; nothing here has been tested. |
| **Authority** | Mandatory rules, not marketing claims. Subordinate to `DECISIONS.md`, `BUSINESS_RULES.md`, `ACCEPTANCE_TESTS.md`. |
| **Scope** | A local, single-user tool with no authentication and no outbound network calls. The threat model is therefore narrow and specific. It is stated honestly rather than padded. |

---

## 1. Threat model — stated plainly

**What this application is:** a local process, run by one person on their own machine, that reads CSV files that person chose to open, and does arithmetic on them.

**What it is not:** an internet-facing multi-tenant service. It has no login, no user table, no session, and no willingness to expose real seller data.

| Asset | Realistic threat | Control |
|---|---|---|
| The user's machine | A malicious CSV, or a formula payload smuggled through an export | §3, §6 — caps, text-first parsing, formula neutralisation |
| The user's own seller data | Accidentally committed to git or pasted into a chat | §4 — gitignore, `data/private/`, a synthetic-data policy |
| The database file | Committed or shipped inside a demo bundle | §4 — `*.db`, `*.sqlite*` gitignored |
| Credentials | None exist, and none should | §5 — there is no secret in this project |
| Any external service | Nothing is contacted | §7 — no outbound calls in the MVP |
| A deployed demo | Exposure of real seller data because "there is no login" | §8 — synthetic data only, explicit CORS allowlist |

> **Explicit non-goal.** This document does not claim the application is hardened against a determined remote attacker. The honest statement is: it is a local tool, it makes no network calls, and it holds no credentials. Deploying it changes the threat model, and §8 says what that requires.

---

## 2. Trust boundaries

```
  UNTRUSTED                                    │  TRUSTED
  ─────────────────────────────────────────────┼───────────────────────────────
  Uploaded CSV bytes                           │  The backend process
  ├─ filename            ──▶ display label only│  The SQLite file on local disk
  ├─ headers             ──▶ normalised, matched against an alias map
  ├─ cell values         ──▶ parsed to typed Decimal / int / date, range-checked
  └─ row count, byte size──▶ capped before parsing
                                               │
  HTTP request bodies                          │
  ├─ budget, sell_through, salvage, cap  ──▶ range-validated
  └─ sku path parameter                  ──▶ existence-checked
                                               │
                                               │  The frontend is NOT a trust
                                               │  boundary. Client-side checks
                                               │  are convenience only.
```

**Boundary rules**

- **T1.** The backend is the authoritative validator. A client-side check never substitutes for a server-side one.
- **T2.** Nothing from an upload is ever used as a filesystem path, a SQL identifier, or an argument to `eval`, `exec`, `pickle`, or `subprocess`.
- **T3.** Every database access is parameterised. No string-built SQL, anywhere, ever.
- **T4.** A filename is a display string. `..`, `/`, `\`, a drive letter, or a null byte in a filename changes nothing about where anything is written.
- **T5.** Every value crossing the boundary is range-checked before use (`BUSINESS_RULES.md` §2 R2, §3).

---

## 3. CSV upload safety

The import path is the only attacker-influenced surface. It is specified in full in `BUSINESS_RULES.md` §3 and `ARCHITECTURE.md` §4.1, and proved by `ACCEPTANCE_TESTS.md` AT-5.

| Control | Rule |
|---|---|
| Size cap | **5 MB per file**, enforced server-side before parsing |
| Row cap | **20,000 data rows per file**, enforced server-side |
| Read as text | Values are read as strings first (`dtype=str`), so nothing is silently coerced. `"001"` stays `"001"`; a bad value is visible rather than absorbed. |
| Header handling | Normalised for case, surrounding whitespace, and a UTF-8 BOM; unknown columns are ignored with a warning; missing required columns fail the file with every missing name listed |
| Type parsing | Every cell is parsed explicitly to `Decimal`, `int`, or `date`. There is no implicit coercion and no float intermediate for money. |
| Range checks | Money `>= 0`, prices `> 0`, `0 <= returned_units <= units_sold`, `0 <= discount_per_unit <= selling_price`, rates in `[0, 1]` |
| Referential check | A transaction `sku` must exist in `products`, or the row is rejected with the SKU named |
| Duplicates | Duplicate `transaction_id` in one file: the later row is rejected. Repeat imports: skipped via a content hash on `import_batch`. |
| Partial writes | Rejected rows never block valid rows, and nothing is written unless the write succeeds atomically |
| Rejection report | Bounded and summarised; a file with 19,000 bad rows must not produce an unbounded payload |
| Error messages | Plain language. Never a filesystem path, a SQL fragment, a library version, or a Python traceback. |
| Dry run | `/import/validate` performs the full validation and persists nothing |

---

## 4. Privacy and data lifecycle

### 4.1 Permitted data

- **Synthetic data only**, generated by `scripts/make_sample_data.py`.
- **Owner-authorised data only**, meaning the operator's own CSV, kept locally.
- **Never** another person's seller data, a customer list, a real order export, or anything containing a name, phone number, address, or real order ID.

The project handbook anticipates a future feature for safely using a friend's seller data, in a later version. **That feature does not exist here and must not be implied.**

### 4.2 What must never enter version control

`.gitignore` must cover at least:

```
.env
.env.*
*.db
*.sqlite
*.sqlite3
data/private/
.venv/
venv/
__pycache__/
.pytest_cache/
.ruff_cache/
node_modules/
dist/
*.log
```

### 4.3 Lifecycle

| Stage | Rule |
|---|---|
| Generation | Synthetic, deterministic, reproducible from the script |
| Ingestion | Validated, capped, stored locally in SQLite |
| Storage | `data/private/` (gitignored) for any operator data; the bundled `data/sample/` for synthetic fixtures |
| Use | Rendered in the UI with a DEMO DATA badge when sample data is loaded |
| Export | Only if an export feature is added (P1). If added, it must neutralise formula payloads (§6) and must not export anything the view was not already showing. |
| Deletion | The database file is disposable. Deleting it and re-seeding restores a clean state. `DELETE /import/{batch_id}` (P1) removes a batch's rows. |
| Retention claim | None is made. This is a local tool with a local file. |

---

## 5. Secrets

**There is no secret in this project.** That is the design, not an aspiration.

- No API key, token, password, certificate, or private key exists or is needed.
- No `.env` file is required. If one is ever introduced for a deployment, it is gitignored and only its variable *names* are documented, never values.
- Configuration is a date-stamped record in the database, not a credential.
- The optional deployment (P1) uses environment variables for configuration only.

**Pre-commit sweep.** The check below must report only harmless matches, and inspecting any match must show no real value:

```powershell
git grep -n -i -E "password|secret|token|api[_-]?key"
```

Match against committed history too, not just the working tree. A secret that was committed and then deleted is still a leaked secret.

---

## 6. Logging and export safety

### 6.1 Logging

- **Never log a cell value, a row's contents, an uploaded filename, or any user-supplied string.** Log the event and a count, not the payload.
- Never log a SQL statement with interpolated parameters.
- Never log a full stack trace to a response body. A traceback goes to the server's own console during development, and a generic message goes to the client.
- Log lines must be free of anything that could be personal data.

### 6.2 Export safety (spreadsheet formula injection)

If any export feature is added, every user-controlled text cell must be neutralised so a spreadsheet cannot execute it:

| Character | Action |
|---|---|
| `=` `+` `-` `@` | Prefix with a single quote `'` |
| Tab (`0x09`), CR (`0x0D`) | Strip or escape |
| Leading whitespace before one of the above | Treat the row as dangerous and neutralise |

This is asserted by AT-5.17. The rule exists because a cell value beginning `=` is executed by Excel and by most spreadsheet tools on open, and the values here originate in an uploaded file.

### 6.3 Rendering safety

- The frontend renders server strings as text. It must not use `dangerouslySetInnerHTML`, `innerHTML`, or an equivalent, on any value that originated in an upload.
- No user-supplied value is ever used to construct a URL, a redirect, or a DOM selector.

---

## 7. Outbound network calls

**There are none.** No Amazon call, no scraping, no telemetry, no analytics, no font or CDN fetch, no update check. This is asserted by AT-9.9.

Consequences of this rule:

- The application works fully offline.
- Scraping Amazon, or any access-control bypass, is prohibited in this project at any priority (`INTEGRATIONS.md` §5.3). It is a boundary, not a backlog item.
- Any proposed change that adds a network call is P2 by definition and requires a `DECISIONS.md` entry plus a fresh review of this document.

---

## 8. If the demo is deployed (P1, optional)

Deploying changes the threat model from "one person's laptop" to "anyone on the internet". All of the following are required, not optional:

1. **Synthetic data only.** No real seller data in a deployed instance, ever.
2. **An explicit CORS allowlist.** Never `*`. The vague safety of "there is no login" is not safety.
3. **Caps active.** The 5 MB and 20,000-row limits must be enforced in the deployed environment, not only locally.
4. **Implicit trust in the operator must not be assumed.** A deployed instance is publicly reachable by definition.
5. **No secrets in the repository or the image.** Configuration comes from the environment.
6. **A stated statement of limitations** on the landing surface: synthetic data, not tax advice, not a forecasting tool, local-first project.

If any of these cannot be satisfied, **do not deploy.** A local demo with screenshots satisfies the definition of done (`PRD.md` §8).

---

## 9. Known limitations, stated honestly

| Limitation | Consequence | Accepted because |
|---|---|---|
| No authentication | Anyone with access to the machine or a deployed URL can use the tool | It is a local single-user tool; deployment is P1 and synthetic-only |
| No rate limiting in local mode | A local caller can hammer the API | Single local user; a deployment must add limits (§8) |
| No encryption at rest | The SQLite file is readable by anyone with filesystem access | The data is synthetic or the operator's own, on the operator's own disk |
| No audit log | No record of who imported what | There is only one user and no identity layer |
| Validation is not a security boundary against a crafted binary payload | A malformed file is rejected safely, but this is not a fuzzing-hardened parser | The realistic threat is a messily-formatted CSV, not a memory-corruption exploit |
| Python and library CVEs | Not tracked | Dependency pinning is a **P0** requirement (T01, `TECH_STACK.md` §7, `ACCEPTANCE_TESTS.md` AT-11.2). A `pip audit` is an optional post-P0 hardening step, not a P1 deliverable |

None of these are claims that the tool is secure for multi-user or internet-facing deployment. It is not, and §8 lists what would be required.

---

## Cross-references

- Upload behaviour in full: `BUSINESS_RULES.md` §3, `ARCHITECTURE.md` §4.1
- Security acceptance cases: `ACCEPTANCE_TESTS.md` AT-5, AT-9
- What is deliberately not integrated: `INTEGRATIONS.md`
- The synthetic-data policy: `INTEGRATIONS.md` §3, `DECISIONS.md` ADR-003
- Task that creates `.gitignore` and the tooling: `PHASES_DETAILED.md` T01
- Terms used precisely: `GLOSSARY.md`
