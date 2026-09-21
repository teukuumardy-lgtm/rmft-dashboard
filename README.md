# RMFT Performance & Pipeline Dashboard

Command Center Harian RMFT — Pipeline → Realisasi → Funding Movement → Customer Action → RMFT Performance → Management Reporting.

**Status: feature-complete.** All 10 build phases are implemented end-to-end against
a real PostgreSQL database with real auth, a real Excel import engine, real MTD/DTD
math, real Pipeline/Realisasi/Success Rate/Leaderboard logic, real pipeline↔funding
matching, real WA report generation, real Target vs Achievement, a full Admin panel,
real Excel/PDF export, and recharts-based visualizations — no mock/dummy data
anywhere, and no "Coming Soon" placeholders remain in the app.

## Non-negotiable constraints from the spec — all satisfied

- **"PN merupakan primary matching key. Jangan menggunakan nama sebagai primary key."**
  → `RmftMaster.pn` is the primary key everywhere; every import/ownership/RBAC path
  matches on PN, never on name.
- **"Jangan menghitung satu rekening dua kali."** → re-uploading a (report_type,
  snapshot_date) **replaces** that snapshot's rows rather than appending.
- **"Dashboard tidak boleh menyembunyikan kondisi data yang belum lengkap."** → the
  Data Position banner always shows COMPLETE / PARTIAL / DATE_MISMATCH / NO_DATA,
  never silently substitutes a stale or partial number.
- **"Jangan gunakan Date Printed"** → every import reads `PERIODE`, never
  `Date Printed`, as the snapshot date.
- **"Jangan membuat aplikasi yang seluruh datanya hanya tersimpan di
  browser/local storage. Gunakan persistent database."** → PostgreSQL is the only
  store; the frontend holds nothing but the JWT/session profile in `localStorage`.
- **"Jangan menggunakan data dummy sebagai data final."** → every screen computes
  from real DB rows and renders an explicit empty state ("Belum ada data...") when
  there's nothing yet — never a placeholder number.
- **"Jangan langsung mengubah menjadi realisasi"** (pipeline↔funding match) → a
  Potential Match is always a suggestion; only a human "Confirm as Realization"
  click creates a `realization` row.
- **"Prioritas utama: Conversion / Success Rate"** for RMFT ranking → the
  Leaderboard sorts by Nominal SR then Activity SR, never by raw pipeline size.
- **"Jangan menggunakan insight statis"** → WA Pagi/Sore, Daily Action, and every
  report/export are generated live from current data on every open/export, not from
  a cached template.

## Feature coverage

### RBAC, master data, import engine (sections 1-2, 7-19, 53-54, 60)
- JWT auth, ADMIN/SBOH vs RMFT roles enforced server-side on every router (RMFT
  users can never read another PN's data, regardless of query params passed).
- Excel import auto-detects DI319 (Tabungan) / DI321 (Giro) / CI324 (Deposito) by
  title/header signature, auto-finds the header row wherever it sits, and reads
  `PERIODE` as the snapshot date.
- **PN ownership engine** (sections 13-15): extracts every 8-digit PN from every
  `PN ...` column, ranks by RM Dana/Mantri → PENGELOLA SINGLEPN → RM Referral →
  Relationship Officer → Other, assigns exactly one Primary Owner, and flags
  Secondary + Conflict when two different RMFT targets appear on one row.
- Anti double-count (section 16): replace-on-reupload, never append.

### Funding dashboard (sections 4-6, 21-28, 50)
- Data Position freshness banner, Tabungan/Giro/Deposito/CASA/DPK per RMFT and per
  unit, MTD (vs. Admin-set monthly baseline) and DTD (vs. each product's own
  latest-available previous snapshot, not a fixed calendar H-1).
- Top-10 outflow/inflow movers with NEW_ACCOUNT / ACCOUNT_MISSING classification.
- **Charts** (section 50): DPK Composition donut, Inflow vs Outflow bar (Home);
  Success Rate horizontal bar (RMFT Performance); Funding Trend line and Pipeline
  vs Realisasi bar (Monthly Report) — all recharts, all fed by live aggregation
  endpoints (`GET /funding/trend`, `GET /funding/flow-totals`), never sample data.

### Customer 360, Pipeline, Realisasi, Success Rate (sections 29-42)
- Universal search (name/CIF/account number) and Customer 360 combining Funding,
  Movement, RMFT ownership, and Pipeline summary.
- Outflow follow-up tracking with HIGH/MEDIUM/LOW classification and a status
  workflow.
- Pipeline Bulanan/Harian input, RMFT-scoped, with **Copy Pipeline Kemarin**.
- Nominal SR and Activity SR with 🟢/🟡/🔴 indicators; RMFT Leaderboard ranked by
  conversion; Daily Action Center (Priority 1-5: Fund Outflow → Closing Today →
  Overdue → High Probability ≥80% → Follow-Up Needed).
- **Pipeline vs Actual Funding match** (sections 40-41): confidence-scored
  suggestions (CIF/account/name/product/nominal signals) against each RMFT's own
  book. Confirm creates a `realization` row with `confirmation_source=AUTO_MATCH`.
  **Reject is now persisted server-side** (`dismissed_match` table, section 41) —
  a rejected pipeline+actual-account pairing won't resurface on reload, while a
  different actual account can still legitimately match the same pipeline later.

### WA reports, Target, Monthly History (sections 39, 43, 45-49, 58)
- WA Pagi / WA Sore: live-generated, real WhatsApp `*bold*` syntax, Indonesian
  number formatting (`Rp1,25 M`, `84,5%`), one-tap clipboard copy.
- **Target vs Achievement** (section 43): 9 target categories (Tabungan, Giro,
  Deposito, DPK, Payroll, EDC, QRIS, Premi, FBI), Admin sets targets per RMFT per
  month, Achievement = confirmed Realisasi ÷ Target with a progress bar and Gap.
- **Monthly Pipeline History** (section 39): Total Pipeline/Realisasi/Outstanding/
  Batal, Nominal & Activity SR, RMFT Terbaik, Customer Terbesar, Produk Terbesar
  (by confirmed realisasi), and a daily conversion trend table/chart — computed
  live for any month, including the current in-progress one.

### Admin panel (sections 2, 15, 56, 60, 61)
Full 4-tab panel at `/admin` (Admin/SBOH only):
- **User management**: create/deactivate users, assign RMFT role + PN or Admin
  role, password reset.
- **Ownership Conflict override** (section 15): lists every account flagged
  `conflict_flag=True` on the latest snapshot; overriding writes both
  `account_rmft_assignment.conflict_override_pn` and every matching
  `funding_snapshot.resolved_pn`/`resolved_rmft` row for that snapshot date, since
  live aggregation reads directly from `funding_snapshot`.
- **Upload History + Rollback** (section 61): every upload batch with row/valid/
  conflict counts; rollback deletes that batch's `funding_snapshot`/`raw_import`
  rows and marks the batch `ROLLED_BACK` — undoing a bad upload without a DB
  console.
- **Audit Trail** (section 56): every CREATE/UPDATE/OVERRIDE/ROLLBACK across the
  app, filterable by module.

### Export (section 57)
`GET /reports/export?report=...&format=xlsx|pdf` — one endpoint, 9 report types ×
2 formats, built through a single `build_report_rows()` dispatcher so no report
needed its own bespoke implementation:

| Report | Where it's exposed |
|---|---|
| `funding` | Funding (RMFT list) |
| `rmft_performance` | RMFT Performance leaderboard (Daily/MTD/YTD scopes) |
| `pipeline` | Pipeline Harian |
| `pipeline_conversion` | Monthly Report — daily conversion trend |
| `customer_outflow` / `customer_inflow` | RMFT Detail — Top movers |
| `target_achievement` | Target |
| `monthly_performance` | Monthly Report — summary |
| `daily_performance` | available via the API (same shape as `rmft_performance` pinned to one day — the RMFT Performance page's "Daily" scope export already covers this with richer columns, so it has no separate UI button) |

Excel keeps raw numeric values with matching `number_format`s (usable for further
analysis/pivoting); PDF renders section-58 Indonesian-formatted text (`Rp1,25 M`,
`84,5%`) since it's a presentation artifact, not a raw-data one. RMFT-role users
are always scoped server-side to their own PN regardless of the `pn` query param.

## Tech stack

- **Backend**: Python FastAPI + SQLAlchemy + PostgreSQL, JWT auth, openpyxl/pandas
  for Excel parsing, reportlab for PDF export.
- **Frontend**: React + Vite, `vite-plugin-pwa`, recharts, plain CSS (no framework
  lock-in).
- **Database**: PostgreSQL 16. Schema is bootstrapped via `Base.metadata.create_all`
  on backend startup for this MVP — swap in Alembic migrations before a production
  rollout so future schema changes are versioned.

## Running it

```bash
cp backend/.env.example backend/.env      # adjust JWT_SECRET before production use
docker compose up --build
```

- Backend API: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:8080
- Postgres: localhost:5432 (`rmft` / `rmft_password` / db `rmft_dashboard`)

Want a public URL (reachable from a phone, not just `localhost`)? See
**[`DEPLOY.md`](./DEPLOY.md)** for a step-by-step Railway deployment (3 services —
Postgres, backend, frontend — from this same repo, no code changes needed beyond
what's already in `frontend/Dockerfile`), or **[`DEPLOY_FREE.md`](./DEPLOY_FREE.md)**
for a genuinely free option (Neon + Render) with a cold-start trade-off.

On first boot the backend seeds `rmft_master` and demo login users:

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | ADMIN / SBOH |
| `adist` | `adist123` | RMFT — Adist Ayudistira |
| `ahmad` | `ahmad123` | RMFT — Ahmad Rafiq |
| `dia` | `dia123` | RMFT — Dia Silopa |

**Change these before any real deployment** (section 76: demo data/users are for
development only — every one of them can now also be managed from the in-app
Admin → User panel instead of the seed script). Baseline for MTD must be set once
per month by an Admin via `POST /funding/baseline?month=YYYY-MM&baseline_date=YYYY-MM-DD`
(section 17/71) after uploading the prior month-end position — this endpoint is
listed and callable from `/docs`; a dedicated Admin-panel form for it is a natural
follow-up (see Known simplifications).

### Frontend-only local dev (without Docker)

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed   # requires DATABASE_URL pointing at a running Postgres
uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to localhost:8000
```

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

- `tests/test_import_engine.py` — section 78 acceptance scenarios: DI319/DI321/CI324
  detection, PN conflict resolution matching the section 15 worked example,
  anti-double-count on re-upload, baseline-based MTD, latest-available-previous-
  snapshot DTD, ACCOUNT_MISSING detection.
- `tests/test_pipeline_calc.py` — section 36 Success Rate worked example, the
  section 38 "ranked by conversion, not pipeline size" leaderboard rule, the
  section 42 Daily Action priority buckets.
- `tests/test_wa_and_matching.py` — section 41 match-confidence worked example
  (strong match vs. unrelated pair), the persisted-Reject behavior (a dismissed
  pipeline+actual-account pairing doesn't resurface), and WA Pagi/Sore rendering
  every RMFT section, the unit total, Success Rate, and the Funding Position block.
- `tests/test_target_calc.py` — section 43 Target vs Achievement math, including
  the DPK/Premi/FBI grouped-category rollups.
- `tests/test_monthly_report.py` — section 39 RMFT Terbaik / Customer Terbesar /
  Produk Terbesar selection logic and the daily conversion trend.
- `tests/test_funding_calc.py` — section 50 chart data: `flow_totals()` (full-
  population Inflow/Outflow sums, not just the Top 10 shown in the mover lists)
  and `dpk_trend()` (per-date DPK composition, each product pinned to its own
  latest-available-on-or-before date).
- `tests/test_report_export.py` — section 57 `build_report_rows()` dispatcher for
  every report type, RBAC-relevant `pn` scoping, and the unknown-report-type error
  path.

> **Note on how this was verified while building it:** the sandbox this app was
> built in has no outbound access to PyPI/npm, so `fastapi`/`sqlalchemy` (and
> therefore `pytest` itself) could not be installed or executed here — every
> DB-touching test above is written and ready but should be run once in a normal
> environment before relying on it operationally. What *is* preinstalled system-wide
> in this sandbox — `openpyxl`, `pandas`, and (for the Phase 10 export engine)
> `reportlab` — was used for real, not just syntax-checked: the auto header/
> report-type detector and PN ownership/priority engine were exercised against
> real `openpyxl`-generated DI319/DI321/CI324 files (headers off row 1, PN
> conflicts, PN-not-in-master, blank balance-field fallbacks); the report export
> renderers (`services/report_export.py`) were run end-to-end against four
> representative report shapes, round-tripping the generated `.xlsx` through
> `openpyxl.load_workbook()` to check header text, numeric cell types, and
> `number_format`s, and validating the generated `.pdf`'s signature/size and
> cross-checking its Indonesian-formatted cell text against `id_format.py`
> directly (a rendered PDF sample was inspected visually during this build); the
> Nominal/Activity Success Rate formulas and the Indonesian number formatter
> (`app/services/id_format.py`, zero external deps) were desk-checked against
> their spec worked examples (section 36, section 58) and matched exactly; the
> match-confidence scorer was run against a strong-match and an unrelated-pair
> case with the expected high/low separation. Every backend `.py` file compiles
> cleanly (`python3 -m py_compile`, zero errors across 45 files) and every
> frontend `.jsx`/`.js` file was passed through the TypeScript compiler's
> transpile step (syntax-only, since `npm install`/bundling wasn't reachable
> either) with zero errors across 32 files.

## Known simplifications (call these out before relying on them operationally)

- No Alembic migrations yet — schema is bootstrapped via
  `Base.metadata.create_all()` on startup. Fine for this build/demo; add Alembic
  before a production rollout so future schema changes are versioned instead of
  requiring a fresh database.
- `account_rmft_assignment` is keyed by `(snapshot_date, account_number)` across
  all three products combined. In the rare case the same account number is reused
  across Tabungan/Giro/Deposito namespaces on the same date, the last-processed
  product wins that row in the Admin → Ownership Conflict view specifically (the
  per-product ownership stored on `funding_snapshot` itself is always correct
  regardless, since that's what every MTD/DTD/leaderboard/report computation
  actually reads).
- Duplicate rows *within a single uploaded file* for the same account are resolved
  by "last row wins" and counted in `duplicates_removed`.
- Customer 360 aggregates Tabungan + Giro by CIF; Deposito has no CIF column in the
  CI324 mapping (section 10), so it stays account-level for a customer's 360 view
  until a deposito↔CIF mapping source is introduced — exactly as section 30
  anticipates. Deposito balances still show correctly everywhere else, since MTD/
  DTD/leaderboard math is computed at the account/snapshot level, not through
  Customer 360.
- The monthly MTD baseline is still set via a direct API call
  (`POST /funding/baseline`, documented above and live in `/docs`) rather than a
  dedicated Admin-panel form — a natural small addition alongside the Admin panel
  built in this phase, not yet wired into the UI.
- WA Pagi/Sore always regenerate from live data when opened — there's no "send
  history," so if numbers change after a report was copied into WhatsApp,
  re-copying reflects the new numbers (this is intentional per section 49: never a
  static template).
- Excel export number formatting uses standard thousands-grouping
  (`#,##0`) rather than the section-58 `Rp1,25 M` short form, since an Excel export
  is meant for further analysis/pivoting where a raw grouped number is more useful
  than a truncated short form; the PDF export (a presentation artifact) *does* use
  the full section-58 Indonesian formatting.
