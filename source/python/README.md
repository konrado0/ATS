# ATS Research Phase A and Canonical Data Phase B

This package implements the minimum trustworthy GPW research slice over the existing local inputs. It deliberately stops before canonical-lake automation, MLflow, machine learning, portfolio simulation, vectorbt integration, or distributed infrastructure.

## Contracts

- `security_id` is a deterministic UUIDv5 over `XWAR:<official ISIN>`. Tickers, ISINs, venue values, official names, and Stooq symbols remain validity-dated alias records with raw values, source provenance, and resolution status. Ticker is never the primary identity.
- WIG20 and mWIG40 snapshots are independently validity-dated and expanded over the WIG session calendar. Every retained decision session must contain exactly 60 unique official members or the pipeline fails.
- Each panel row represents one official member at the pre-open `decision_ts`. Security and WIG close inputs come from the immediately preceding WIG session and have a conservative `available_ts` five minutes after that prior close. The pipeline enforces `available_ts <= decision_ts`.
- The five established benign exits—LOTOS, PGNiG, STS Holding, CIECH, and TIM—remain official member rows while applicable. Their missing Stooq aliases, membership exit dates, suspension/trading dates, and researched treatment remain explicit. No bar is synthesized.
- Feature functions live only under `ats_research.features`; label functions live only under `ats_research.labels`. Feature code does not import the label namespace.
- Eligibility has four distinct contracts: price/member eligibility, per-feature eligibility, feature-label usability, and complete-feature-matrix eligibility. Cross-sectional ranks use only the named feature's denominator; missing 252-session momentum cannot suppress a valid five-session return or volume observation.
- WIG trend is a market regime variable, never a cross-sectional rank. Annual and positive/non-positive WIG-trend splits are emitted separately.

## Feature definitions

All features are version 1, daily, calculated on a complete WIG-session grid, and joined to the next session's pre-open decision. Registry fingerprints combine the expression with the shared session-grid, sorting, membership, joining, and availability pipeline:

- `momentum_12_1`: close at `t-21` divided by close at `t-252`, minus one.
- `return_5`: close at `t` divided by close at `t-5`, minus one.
- `realized_volatility_20`: sample standard deviation of 20 consecutive close-to-close returns.
- `relative_volume_20`: current volume divided by its 20-session mean, minus one.
- `wig_trend_200`: WIG close divided by its 200-session mean, minus one.

Missing exact session endpoints remain null. Rolling windows require their stated non-null observations. Values are derived/cacheable artifacts, not canonical facts.

## Label convention

For a decision session `t`, `forward_return_h_v1` is `close[t+h] / close[t] - 1`, where `h` is counted on the official WIG market-session calendar and the decision session is session zero. The start and end prices must both exist for that security on the exact calendar sessions; otherwise the label is null. Intermediate non-trading sessions do not change horizon counting and are not forward-filled. Final sessions without an exact future endpoint are null.

These labels are close-to-close diagnostic outcomes. They are not executable portfolio returns: the start close occurs after the pre-open decision, and Phase A contains no order, fill, cost, cash, or portfolio model.

## Run and verify

Use the existing environment directly; no installation is required:

```powershell
$python = 'C:\Users\konra\anaconda3\envs\ats-stack-research\python.exe'
$env:PYTHONPATH = 'D:\Stock\ATS\source\python\src'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $python -m pytest -p no:cacheprovider D:\Stock\ATS\source\python\tests
& $python -m ats_research run --config D:\Stock\ATS\source\python\configs\phase_a_reference.yaml
& $python -m ats_research validate --run-dir D:\Stock\data\ATS\phase_a\runs\<run_id>
& $python -m ats_research reproduce --run-dir D:\Stock\data\ATS\phase_a\runs\<run_id>
```

The authoritative run directory contains `config.yaml`, `metrics.json`, `manifest.json`, and `artifacts/`. The manifest pins code and input hashes, feature fingerprints, label/timestamp semantics, environment versions, row counts, coverage, and physical/logical artifact hashes. Reproduction writes a separately validated copy beneath `phase_a/cache/reproductions` and compares metrics plus logical hashes.

Every run also contains a deterministic `source_snapshot.zip` and full `environment_lock.json`. The run identity includes the environment-lock hash, Git commit, Git dirty-state hash, configuration, source inputs, and all implementation/test/documentation hashes. Validation requires the exact manifest-declared file set, validates physical and logical hashes for `config.yaml`, `metrics.json`, and every artifact, checks the archived source against code hashes, and requires the recorded Git commit to be locally reconstructable.

## Research-correctness diagnostics

Phase A emits session-level rank IC and quantile results plus:

- annual rank-IC stability;
- positive versus non-positive WIG-trend regime results;
- Newey-West/HAC mean-IC intervals using the label horizon as the lag;
- deterministic moving-block-bootstrap intervals;
- non-overlapping offset sensitivities for each horizon;
- Benjamini-Hochberg adjustment across feature/horizon tests;
- price-coverage and unresolved-exit-count sensitivities;
- before/during comparisons for each of the five unresolved corporate-exit membership periods.

Overlapping labels, incomplete historical prices, regime selection, and multiple testing still prevent these summaries from being treated as deployable alpha evidence.

## Known Phase A limitations

Stooq adjustment semantics are not independently documented, so the validated bar artifact records them as vendor-adjusted but unverified. The five missing post-start series are not reconstructed; sensitivity tables quantify observed-sample dependence on their membership periods but cannot recreate their absent ranks or returns. IC, rank, quantile, uncertainty, turnover, and missing-state outputs remain hypothesis-generation diagnostics only. Phase B formalizes the canonical contracts without changing those limitations.

## Phase B

Phase B is implemented by `ats_contracts` and `ats_data`. Exact Arrow schemas and semantic validators cover identity, aliases, bars, universe membership, security events, corporate actions, macro series, lineage, manifests, and visible ingestion issues. See `PHASE_B.md` for the contracts, timestamp semantics, publication protocol, and reference commands.

Canonical data lives beneath `D:/Stock/data/ATS/phase_b/versions`. A catalog `*.current.json` is discovery-only. Research code must pass an explicit `versions/<version_id>/manifest.json`; Polars and DuckDB readers reject mutable pointers.
