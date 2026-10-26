# INTEGRATIONS.md — What Exists, What Is Deferred, and the Access Caveats

| Field | Value |
|---|---|
| **Status** | Approved specification. **No integration exists. No external service has been contacted.** |
| **Authority** | Fifth, on the integration surface only. Subordinate to `DECISIONS.md`, `BUSINESS_RULES.md`, `ACCEPTANCE_TESTS.md`, `PRD.md`. |
| **Hard rule** | This file must never contain a fabricated endpoint, access token, credential, API key, account ID, or "example" response from a real service. Anything not built is described as not built. |

---

## 1. Summary

| Integration | State | Priority |
|---|---|---|
| Local CSV file import (products, transactions) | **P0 — to be built** | P0 |
| Bundled synthetic sample fixtures | **P0 — to be built** | P0 |
| Local REST API consumed by the SPA | **P0 — to be built** | P0 |
| FastAPI `/docs` OpenAPI UI | P0, provided by the framework | P0 |
| Batch delete of an import | P1 | P1 |
| Public deployment of the demo | P1, optional | P1 |
| Amazon Selling Partner API (SP-API), including Seller Central report import | **Deferred. Not designed, not registered, no credentials.** | P2 |
| Wholesale price scraping / live supplier discovery | **Deferred. Prohibited in the MVP.** | P2 |
| Google Trends ingestion (automated) | **Deferred.** | P2 |
| Authentication provider / SSO | **Deferred. No identity layer exists.** | P2 |

No payment, accounting or ERP integration is contemplated or listed. The P2 set is exactly the one frozen in `PRD.md` §6 and `DECISIONS.md` ADR-003; this table adds nothing to it.

**Nothing in this project makes an outbound network call at runtime.** There is no HTTP client in the backend other than the test client, and no third-party script in the frontend. This is a P0 acceptance condition (`ACCEPTANCE_TESTS.md` AT-9.9).

---

## 2. What exists: the local file import

The only data ingress. Details are authoritative in `BUSINESS_RULES.md` §3 and `ARCHITECTURE.md` §4.1.

| Aspect | Detail |
|---|---|
| Transport | `multipart/form-data` upload to `POST /import` and `POST /import/validate` |
| Formats accepted | UTF-8 CSV (with or without a BOM). Nothing else. |
| Kinds | `products` and `transactions` |
| Size cap | 5 MB per file, enforced server-side |
| Row cap | 20,000 data rows per file, enforced server-side |
| Validation | Backend is authoritative. The frontend may pre-check, but a client-side pass never substitutes for a server-side one. |
| Rejection behaviour | Per-row, with row number, field, offending value, and a plain-language reason. Valid rows still load. |
| Idempotency | A file whose content hash matches an existing `import_batch` is skipped. Re-uploading the same file never duplicates rows. |
| Dry run | `/import/validate` performs the full validation and persists nothing |
| Trust | Filenames are display labels only, never used as a filesystem path |
| Proof | `ACCEPTANCE_TESTS.md` AT-5 (22 cases) and AT-6 |

---

## 3. What exists: the synthetic sample fixtures

| Aspect | Detail |
|---|---|
| Location | `data/sample/products_sample.csv`, `data/sample/transactions_sample.csv` |
| Generation | `scripts/make_sample_data.py`, deterministic, re-runnable |
| Contents | A catalogue of roughly 9–10 SKUs across festive, gifting, decor, kitchen, accessories, apparel and electronics, including **at least one loss-making SKU**, plus a transaction history spanning a pre-festival ramp |
| Policy | Fully synthetic. No real brand, seller, customer, phone number, address, or order ID. Asserted by AT-9.5. |
| Realism claim | None. The data is shaped to exercise the engine, not to resemble a real marketplace. |
| Portfolio total | Not a fixed target. See `DECISIONS.md` ADR-020 and AP-1 — the handbook's ₹26,761.53 is deliberately **not** a required acceptance value. |

---

## 4. What exists: the REST interface

Nine P0 endpoints plus `/docs`. Full method/path/status table in `ARCHITECTURE.md` §6; failure cases in `ACCEPTANCE_TESTS.md` AT-8.

| Aspect | Detail |
|---|---|
| Base | `/api/v1` (final prefix decided in T10 and recorded there) |
| Content type | `application/json`, except the two multipart upload endpoints |
| Money representation | JSON **strings** containing decimal literals, or the literal `"n/a"` for ratios |
| Error body | `{ "error", "detail", "field"? }` — uniform across every failure |
| Auth | **None.** The service is designed to bind to localhost. |
| CORS | Localhost origin allowlist during development; an explicit allowlist in any deployment. Never `*` in production (AT-9.6). |
| Docs | Interactive OpenAPI UI at `/docs`, generated from the Pydantic models |
| Versioning | Path-prefixed. A breaking change means a new prefix; there is no content negotiation. |

---

## 5. Deferred integrations and their real caveats

These are recorded so that no future agent invents them. **None of the following has been designed, prototyped, registered, or approved.**

### 5.1 Amazon Selling Partner API (SP-API) — P2

**What it would be for:** replacing manual CSV export with seller-authorised, automated retrieval of order, fee and settlement reports.

**Why it is not in the MVP:**
- It reportedly requires a developer registration and Amazon's approval (an unverified external-process assumption — confirm before relying on it). That process is outside the four-day scope and is not something this project has started.
- It requires seller authorisation and credential custody, which introduces an authentication and secret-management surface the MVP deliberately does not have.
- The brief lists it as P2 explicitly, and the handbook names SP-API as the legitimate *future* route for seller-side data while stating that scraping and access-control bypass are not acceptable at any point.

**Caveats a future implementer must resolve before writing a line:** registration and approval status; the exact report types and their schedules; the difference between the fee figures in settlement reports and the illustrative model in `BUSINESS_RULES.md` §5; token storage and rotation; and the fact that a settlement figure must **replace** the fee model, never be added to it (`DECISIONS.md` ADR-009).

**Do not** write placeholder credentials, a mock endpoint, or a "coming soon" panel for this. As of now it does not exist.

### 5.2 Amazon Seller Central report import — P2

**What it would be for:** letting a seller download their own settlement report from their own account and import it, with no API registration.

**Why it is not in the MVP:** the report schemas are versioned, wide, and change without notice. Supporting one properly is a project of its own. Note that this route still requires the seller to own and authorise the data, and that a real settlement report must never be committed to the repository (`SECURITY.md` §4).

### 5.3 Wholesale price scraping and supplier discovery — P2, and prohibited in the MVP

**Status:** not built, and **not to be built** in this project.

The brief forbids scraping, bypassing access controls, and using credentials that are not the operator's own. This is a boundary, not a backlog item. There is no compliant-but-faster version of it, and no "just for the demo" exception.

### 5.4 Google Trends ingestion — P2

**What it would be for:** a demand-interest signal per keyword.

**Why it is not in the MVP:** automated collection has access constraints and rate behaviour that are cited as a risk (not verified here) rather than a documented fact; and, more fundamentally, **search interest is not sales**. The handbook is explicit that any trend signal must be presented with a warning that interest is not demand. A trend score was considered for P0 and **cut** (`DECISIONS.md` ADR-002 for the five views, ADR-003 for the frozen P2 boundary). No trends view exists, no trends column exists, and no trend data is imported.

**Do not** present a trend score anywhere, and do not derive a `sell_through` assumption from one.

### 5.5 Deployment — P1, optional

**What it would be:** hosting the demo so a reviewer can open a URL.

**Caveats if attempted:** demo data only; environment variables for any configuration, never committed values; an explicit CORS allowlist; the 5 MB and 20,000-row caps active; and the acknowledgement that **"no login" does not make publicly exposed seller data safe** — which is why only synthetic data may ever be deployed. If hosting slips, a local demo with screenshots satisfies the definition of done (`PRD.md` §8).

### 5.6 Authentication — P2

**Status:** there is no identity layer, no user table, no session, and no token. The application is designed for a single local operator. Any statement that this tool supports multiple users is false.

---

## 6. Rules for anyone extending this file

1. **Built vs deferred must stay obvious.** A deferred item is described as not built, in the past-tense-absent voice. Never present a deferred capability as available.
2. **No fabricated detail.** No endpoint URLs that were not called, no response bodies that were not observed, no credential names that do not exist, no rate limits that were not read from a source.
3. **A deferred item needs a caveat list.** If it is worth mentioning, it is worth stating what a future implementer must resolve first.
4. **Moving something from deferred to built requires:** a `DECISIONS.md` entry, a `SECURITY.md` review of the new trust boundary, new acceptance tests in `ACCEPTANCE_TESTS.md`, and a `PHASES_DETAILED.md` task. Never a silent addition.
5. **The MVP has no outbound network calls.** If a proposed change adds one, it is P2 by definition.

---

## Cross-references

- Upload safety, trust boundaries and privacy: `SECURITY.md`
- The API contract in full: `ARCHITECTURE.md` §6
- Import acceptance cases: `ACCEPTANCE_TESTS.md` AT-5, AT-8, AT-9.9
- Decisions that defer these: `DECISIONS.md` ADR-003 (the frozen P0/P1/P2 boundary), ADR-005 (SQLite, no Docker/Postgres)
- Why there is no trends view or alerts page: `PRD.md` §4, `DECISIONS.md` ADR-002
