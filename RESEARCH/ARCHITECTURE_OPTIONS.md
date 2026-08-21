# Architecture Options and Decision Matrix

Scores are specific to the audited workstation, data and solo-research workflow. Criteria use the requested weights and a 1–5 rating. Weighted totals are out of 100.

## Separate component scorecards

### Physical layouts

| Layout | Broad scans | Selective dates | Security retrieval | Update behavior | Small-file risk | Decision |
|---|---:|---:|---:|---:|---:|---|
| Existing ticker-only monolith | 5 | 3 | 5 | 1 | 5 | Performance control only |
| Normalized sorted monolith | 5 | 3 | 5 | 2 | 5 | Basis for the compact MVP snapshot |
| `market/frequency/year` Hive, uncompacted | 3 | 5 | 2 | 3 | 2 | Future candidate only when file size/update evidence requires it |
| Add fixed 16-way security bucket | 1 | 2 | 1 | 2 | 1 | Reject: 3,477 files and 0.65-s pruned security read |
| Intraday `market/frequency/year/month` | 3 | 4 | 2 | 4 | 1 at current density | Defer month: 26 roughly 1-MB files gave no 30-day gain |
| Few compact market/frequency files | 5 | 3 | 5 | 4 | 5 | Selected MVP; benchmark time partitioning only on a measured trigger |
| Automatic size-triggered periods | 4 | 5 | 4 | 5 | 3 | Evolvable later optimization, not MVP infrastructure |

### Data engines

| Engine | Correctness surface | Local speed | Interoperability | Complexity | Decision |
|---|---:|---:|---:|---:|---|
| pandas | 4 | 3 | 5 | 5 | Compatibility boundary |
| PyArrow | 5 | 4 | 5 | 4 | Schema and IO contract |
| Polars lazy | 4 | 5 | 5 | 4 | Feature pipelines |
| DuckDB | 5 | 5 | 5 | 4 | SQL/query facade |
| Dask/Modin/Vaex | 3 | not locally proven | 3 | 2 | Defer |
| Spark | 4 | wrong scale locally | 5 | 1 | Reject for MVP |

### Research backtesters

| Candidate | Cross-sectional fit | Transparency | Local evidence | Complexity | Decision |
|---|---:|---:|---:|---:|---|
| NumPy/Numba reference | 5 | 5 | 5 | 4 | Core |
| vectorbt | 5 | 3 | 1 (cold guard exceeded) | 3 | Optional after pin/retest |
| bt | 4 | 4 | 2 (installed only) | 3 | Challenger only |
| backtesting.py | 2 | 4 | comparison only | 4 | Not for cross-sectional core |

### Event engines

| Candidate | Timing/accounting fit | Auditability | Local evidence | Operational cost | Decision |
|---|---:|---:|---:|---:|---|
| Narrow custom daily | 5 | 5 | 5 | 4 | MVP |
| PyBroker | 4 | 4 | 1 (cold guard exceeded) | 3 | Defer/pin |
| Zipline-reloaded | 4 | 3 | 2 (import smoke) | 2 | Best packaged challenger |
| Backtrader/QSTrader | 3 | 3 | 2/comparison | 3 | Defer |
| LEAN | 5 | 3 | official research only | 1 | Future live candidate |
| NautilusTrader | 5 | 4 | official research only | 1 | Future intraday/live candidate |

## Three complete MVP stacks

| Criterion (weight) | 1. pandas/Arrow + vectorbt + custom | 2. DuckDB/Polars/Arrow + reference/vectorbt + custom | 3. Hybrid data/research + packaged event engine |
|---|---:|---:|---:|
| Point-in-time correctness (18) | 4 | 5 | 4 |
| Research velocity (12) | 4 | 5 | 4 |
| Testability/debugging (10) | 4 | 5 | 3 |
| Local performance/hardware fit (10) | 3 | 5 | 4 |
| Cross-sectional support (8) | 4 | 5 | 4 |
| Execution realism (8) | 3 | 4 | 5 |
| Data/event extensibility (7) | 4 | 5 | 4 |
| ML interoperability (7) | 5 | 5 | 4 |
| Maintenance/ecosystem (6) | 4 | 5 | 4 |
| Future live path (5) | 2 | 3 | 4 |
| Solo-operability/complexity (5) | 4 | 4 | 2 |
| Cost/licensing/lock-in (4) | 5 | 5 | 4 |
| **Weighted total / 100** | **76.6** | **95.4** | **77.6** |

### Option 1: pandas/PyArrow + vectorbt + custom simulator

This is familiar and ecosystem-rich, but it concentrates the cross-sectional research path in pandas/vectorbt. Local evidence showed Polars faster on features and vectorbt failed the bounded cold guard. It also lacks DuckDB's concise SQL/query-plan surface for point-in-time dataset construction.

### Option 2: DuckDB/Polars/Arrow + transparent research + custom simulator

This is selected. Arrow prevents engine lock-in; DuckDB and Polars address different workloads; transparent NumPy/Numba analytics preserve auditability; and the custom daily simulator is narrow enough to reconcile. The implementation begins with the GPW point-in-time factor/label slice and a few compact files; the event ledger follows after research correctness is demonstrated. pandas and vectorbt remain boundary tools, and neither owns the canonical contracts.

### Option 3: hybrid data/research + packaged event engine

This could provide more ready-made order/event behavior, but no packaged candidate completed the local golden-ledger workload. Adapter, calendar, bundle and dependency work would slow the MVP while weakening auditability. Zipline-reloaded should be used as the first later challenger.

## Sensitivity and non-goals

Option 2 remains first if execution realism rises from 8 to 15 points unless the packaged event adapter achieves golden-ledger parity and a clean environment. LEAN or NautilusTrader should not displace it merely because live trading is a future aspiration. They become justified only when a concrete broker, intraday latency, exchange-calendar, order-state, or always-on service requirement cannot be met economically by the neutral interfaces.

This matrix does not rank financial returns. It ranks correctness, development behavior and operational fit.
