# ATS

ATS is a correctness-first research and backtesting project for point-in-time
equity research, immutable analytical data, and auditable portfolio simulation.
The current implementation is centered on the Warsaw Stock Exchange (GPW), with
U.S. daily data used in the canonical-data work.

The project is deliberately not a live trading system yet. Its present goal is
to determine whether a small number of research hypotheses—including a bounded
pooled-ML swing-opportunity experiment—justify further engineering.

## Current checkpoint

Status as of 2026-08-30:

- The architecture study and local storage/query/backtester benchmarks are
  complete.
- Phase A established the point-in-time TOP60 research contracts and preserved
  the accepted historical diagnostic evidence.
- A research-grade GPW panel now combines source/native Bossa, Investing.com and
  explicitly approved Yahoo observations, then applies bounded split
  normalization. It retains exactly 60 official PIT members per session from
  2019-12-23, but it is not a canonical Phase B or total-return publication.
- Phase A v2 found that proximity to the strict trailing high deserved one
  bounded economic falsification test. The repaired long-only Q5 test reported a
  15.02% after-cost price-only CAGR versus 12.39% for its same-eligibility
  benchmark over the controlling common period. This is hypothesis evidence,
  not untouched validation or deployable alpha.
- Phase B implements immutable Arrow/Parquet data contracts, transactional
  publication, lineage, DuckDB/Polars readers, and pinned GPW/U.S. versions.
- Phase C implements and independently validates a deterministic daily portfolio
  ledger with next-open timing, explicit costs, cash scaling, missing-price
  states, and corporate/security-event hooks.
- The repaired pre-Phase-D market-state diagnostic is complete. Its 12-variable
  numerical context block is ready with caveats; historical association is
  mixed, pairwise correlation is the only frozen block variable meeting the
  descriptive heterogeneity flag, and no market ON/OFF rule is authorized.
- The Phase D charter and roadmap are the frozen planning baseline. No Phase D
  model has been trained and no real predictive result has been inspected.

The next gate is **Phase D0/D1 only**: freeze the complete experimental contract
and prove the minimal ML workbench on fixtures. Phase D2 may inspect real model
performance only after a separate owner review.

Authoritative current documents:

- [implementation roadmap](RESEARCH/IMPLEMENTATION_ROADMAP.md)
- [Phase D pooled-ML charter](RESEARCH/PHASE_D_POOLED_ML_RESEARCH_CHARTER.md)
- [controlling market-state checkpoint](RESEARCH/PRE_PHASE_D_MARKET_STATE_DIAGNOSTIC.md)
- [recommended architecture](RESEARCH/RECOMMENDED_ARCHITECTURE.md)

## How the system fits together

```mermaid
flowchart LR
    R["Immutable vendor/source evidence"] --> I["Identity, membership and ingestion validation"]
    I --> B["Versioned Arrow/Parquet facts\nPhase B"]
    I --> P["Pinned research-grade GPW panel"]
    B --> A["Point-in-time research tables\nPhase A"]
    P --> A
    A --> F["Features, labels and diagnostics"]
    F --> S["Signals / target intents"]
    S --> C["Deterministic daily ledger\nPhase C"]
    F --> D["Bounded chronological pooled ML\nPhase D"]
    D --> O["Selective swing opportunities\nor explicit abstention"]
    O --> C
    A --> M["Immutable configs, manifests, hashes and reports"]
    B --> M
    C --> M
    D --> M
```

The boundaries matter:

- Vendor files are evidence, not silently cleaned truth.
- Stable `security_id` values own identity; tickers and vendor symbols are
  validity-dated aliases.
- Official universe membership and the expected denominator remain visible. A
  calculation using 57 priced members of an official TOP60 records `57/60` and
  the three exclusion states.
- Features use only information available by their decision timestamp. Forward
  outcomes live under the label boundary and are inaccessible to feature code.
- Research statistics are not portfolio returns. Executable evidence requires
  explicit intents, next-open timing, orders, fills, costs, cash and valuation.
- Every accepted run pins inputs, code/environment state and logical/physical
  artifacts. Existing accepted runs are never edited in place.

## Repository guide

| Path | Purpose |
|---|---|
| [`source/python/src/ats_contracts`](source/python/src/ats_contracts) | Shared Pydantic/Arrow contracts and semantic validation. |
| [`source/python/src/ats_research`](source/python/src/ats_research) | Phase A identity, PIT membership, panels, features, labels and diagnostics. |
| [`source/python/src/ats_data`](source/python/src/ats_data) | Phase B ingestion, immutable publication, manifests and reconciliation. |
| [`source/python/src/ats_portfolio`](source/python/src/ats_portfolio) | Phase C deterministic event/ledger engine and independent validation. |
| [`source/python/tests`](source/python/tests) | Main contract, research, data and portfolio regression suites. |
| [`source/python/configs`](source/python/configs) | Retained reference configurations and intent fixtures. |
| [`source/python/notebooks`](source/python/notebooks) | Executable orientation notebooks explaining data, research and ledger flow. |
| [`RESEARCH`](RESEARCH) | Architecture decisions, phase reports, research findings and retained evidence. |
| [`RESEARCH/prototypes`](RESEARCH/prototypes) | Bounded benchmark/research implementations; not a second production package. |
| [`RESEARCH/environment`](RESEARCH/environment) | Stable Windows/Conda invocation helpers used by current validation commands. |

The Python package metadata and CLI entry points are in
[`source/python/pyproject.toml`](source/python/pyproject.toml). The installed
commands are `ats-research`, `ats-data`, and `ats-portfolio`.

## Data and artifact locations

Large or private data is intentionally outside Git:

```text
D:\Stock\data\
  ... vendor/source archives ...       immutable input evidence
  ATS\
    phase_a\runs\                      accepted research runs
    phase_b\versions\                  immutable canonical versions
    phase_c\runs\                      immutable portfolio ledgers
    gpw_split_normalization\runs\      research-grade candidate panels
    phase_a_v2_research\runs\          Phase A v2 evidence
    phase_a_v2_strategy_test\runs\     bounded strategy translations
    pre_phase_d_market_state\runs\     market-state diagnostic evidence
    phase_d_ml\                         reserved for future Phase D outputs
```

Do not modify vendor observations or accepted run/version directories. New data,
corrections and experiments create new versioned directories. Discovery pointers
such as `*.current.json` are convenience only; research and validation must pin an
explicit manifest.

Generated caches and temporary runtime files belong under the documented cache
or `.tmp` roots and are excluded from Git. Commit code, small fixtures,
configuration, plans and concise reports—not downloaded market history or large
generated tables.

## Reproduce and test

The supported Windows entry point activates the isolated Conda runtime, required
DLL paths, `PYTHONPATH`, and writable temporary/cache directories:

```powershell
$atsPython = 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1'
```

Run the main Python suite from the package directory:

```powershell
Set-Location 'D:\Stock\ATS\source\python'
& $atsPython -m pytest -q
```

Run the controlling pre-Phase-D regression suite from the repository root:

```powershell
Set-Location 'D:\Stock\ATS'
& $atsPython -m pytest -q 'D:\Stock\ATS\RESEARCH\prototypes\pre_phase_d_market_state\tests'
```

Inspect the available CLIs:

```powershell
& $atsPython -m ats_research --help
& $atsPython -m ats_data --help
& $atsPython -m ats_portfolio --help
```

Reference run/validation commands and accepted manifest conventions are kept in:

- [Python implementation guide](source/python/README.md)
- [Phase B canonical-data contract](source/python/PHASE_B.md)
- [Phase C portfolio-ledger contract](source/python/PHASE_C.md)
- [notebook guide](source/python/notebooks/README.md)

## Roadmap

| Phase | State | Purpose / next gate |
|---|---|---|
| Architecture study | Complete | Local technology, Parquet-layout and engine evidence; measured defaults rather than permanent rules. |
| Phase A | Accepted and preserved | Correct PIT research slice, denominator/missingness discipline, features and forward diagnostics. |
| Phase B | Implemented | Immutable canonical analytical facts and transactional publication; the newer split-normalized research panel is deliberately not promoted yet. |
| Phase C | Implemented and repaired | Deterministic daily portfolio accounting and independent ledger reconstruction. |
| Phase A v2 / proximity | Bounded test passed its frozen hurdles | Retained conventional benchmark only; one later bounded validation remains, with no parameter optimization. |
| Pre-Phase D market state | Complete | Carry the compact numerical block as context; do not turn it into a timing strategy. |
| Phase D0 | Next | Freeze exact features, folds, purge/embargo, models, opportunity gate, evaluation thresholds and stop rule before real predictions. |
| Phase D1 | Not started | Build `ats_ml` minimally and validate it on synthetic/hand-calculated fixtures without inspecting real predictive performance. |
| Phase D2/D3 | Not authorized | Execute the locked study once, then stop or authorize only one bounded portfolio translation. |
| Phase E/F | Trigger-driven / later | Optimize measured pain and add richer reporting only when the completed vertical slice demonstrates a need. |

Phase D is a pooled learner but not an always-invested portfolio. It evaluates
eligible security-sessions while cash/no position remains the default. The core
question is whether a compact rich-state representation adds stable and
economically meaningful selective swing-opportunity information beyond the
strongest conventional representation. Approximately tying the conventional
baseline is failure, not success.

## Research interpretation

The following distinctions should survive every future report:

- `split_adjusted_price_return` removes known split mechanics but excludes cash
  distributions and preserves dividend price gaps. It is not total return.
- Stooq-adjusted historical evidence, source/native observations and the newer
  split-adjusted price-only panel are different bases and must not be merged
  semantically.
- Historical outcomes through 2026-08-18 have influenced this research program.
  A later segment may be called a locked historical test, but genuinely forward
  evidence begins only after that boundary.
- Rank IC, quantile spreads and approximate cost screens are diagnostics. They do
  not establish fillability, portfolio economics or deployable alpha.
- LEAN and NautilusTrader remain optional future adapters. They are justified
  only by a concrete live/intraday requirement and must first reproduce the
  neutral ATS contracts and golden ledger.

## Working rules

1. Read this README, the current roadmap and the relevant controlling report
   before changing code.
2. Freeze and hash research plans/configuration before inspecting new outcomes.
3. Preserve accepted runs, prior versions and unfavorable results.
4. Fail closed on identity, timing, schema, adjustment, denominator or accounting
   ambiguity that could materially invalidate a result.
5. Keep bounded documented imperfections as caveats when they cannot materially
   change the decision; infrastructure work must be pulled by demonstrated need.
6. Reuse existing contracts and reproducibility machinery before adding a new
   subsystem.
7. Keep unrelated dirty work untouched and commit scoped paths explicitly.
8. Never optimize a hypothesis after viewing the result unless a new,
   independently frozen experiment explicitly authorizes it.

## Documentation maintenance

This file is the project entry point, not the full evidence archive. Update its
**Current checkpoint**, **Roadmap**, authoritative links and supported commands
whenever a phase gate or repository boundary changes. Put detailed methodology,
hashes, metrics and caveats in the phase report, then link that report here. Do
not silently rewrite the meaning of an earlier accepted artifact to make the
summary look current.
