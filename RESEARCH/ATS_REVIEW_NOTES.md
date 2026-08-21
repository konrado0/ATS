# ATS Phase A/B/C review checkpoint notes

## Purpose and navigation

This checkpoint pauses implementation and makes the completed ATS work understandable, reproducible, and safely retained. It does not begin Phase D, alter accounting semantics, modify production source/tests/configurations, or regenerate canonical publications.

The executable owner walkthrough is under `D:\Stock\ATS\source\python\notebooks`:

1. `00_orientation_and_system_map.ipynb` — phase boundaries, system map, artifact classes, provenance, implemented/deferred status.
2. `01_data_identity_and_point_in_time.ipynb` — pinned GPW publication, identity/membership trace, explicit 60→57→56 populations, time visibility, bounded readers, measured layout.
3. `02_research_findings_and_diagnostics.ipynb` — production feature/label calculations, independent derivations, ranks/IC/quantiles, coverage/stability, retained classifications.
4. `03_portfolio_ledger_and_end_to_end_flow.ipynb` — Phase C contracts, next-open execution, costs/cash/positions/valuation, invariants, reproduction, and missing orchestration.

See `source\python\notebooks\README.md` for purpose, inputs, overrides, and execution commands. Each notebook is independently configured but the intended reading order is 00→03.

## Exact execution instructions

Use the existing repaired research environment; do not install packages:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  -PythonArgs @('D:\Stock\ATS\source\python\notebooks\execute_notebooks.py')
```

The driver starts a fresh kernel for each notebook, executes in documented order, retains small outputs, stops on errors, and writes `execution_report.json`. To run one notebook, append its filename as the second Python argument. The notebooks add `D:\Stock\ATS\source\python\src` to `sys.path`, and the repaired wrapper also supplies it through `PYTHONPATH` for module commands.

Path overrides are explicit environment variables: `ATS_REPO_ROOT`, `ATS_DATA_ROOT`, `ATS_GPW_MANIFEST`, `ATS_US_MANIFEST`, `ATS_PHASE_A_RUN`, `ATS_PHASE_A_EXTENDED_RUN`, `ATS_PHASE_C_RUN`, and `ATS_PHASE_C_REPRODUCTION`.

## Environment and kernel

- Wrapper: `D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1`.
- Environment: `C:\Users\konra\anaconda3\envs\ats-stack-research`.
- Kernel: `python3`, Python 3.12.13.
- Packages observed live: NumPy 1.26.4, pandas 3.0.5, Polars 1.43.2, PyArrow 25.0.0, DuckDB 1.5.5, SciPy 1.17.1, Pydantic 2.13.4, nbformat 5.11.1, nbclient 0.11.0, ipykernel 7.3.0.
- No packages were installed, removed, or upgraded. The vectorbt environment was not touched.
- Crash diagnosis: direct scientific Python startup without the Conda native DLL directories reproduced an immediate Windows exit `-1066598273` (`0xC06D007F`, delayed-load procedure resolution failure). The installed Jupyter `python3` kernelspec had no `env` block, so GUI/fresh-kernel launches did not guarantee `Library\bin`.
- Fix: `repair_jupyter_kernel.ps1` now idempotently prepends the environment root, `Scripts`, and `Library\bin`, adds the ATS source path, and redirects IPython/Jupyter/Matplotlib/Numba state to `RESEARCH\.tmp\ats-env`. Both wrappers apply the same runtime settings, and recreation reapplies the kernelspec repair.
- Post-fix proof: notebook 00's fresh kernel reports the native-library path present and passes NumPy SVD plus SciPy Spearman smoke tests. Installed kernelspec SHA-256: `6BE831FF2B0B32E7871C369A45637C52AF49493B0D1F805A0B904B94F0BDD661`.

## Repository and evidence baseline

### Git

- Review baseline HEAD: `00e35d98a49492a7913a1e862117c5ae19757d06` (`Document Phase C repair audit`).
- Recent phase commits examined:
  - `caf76ee9b7da77829cdc1b32c982a7b895e2c743` — Phase A implementation;
  - `44f753f`, `f09aebc`, `bb82e25`, `94a0e6e0792937a4b6ec8dc69c66fca85908a877` — Phase B implementation/hardening;
  - `e96d78af3a261dc15eb4e3e11598553c44a6c157`, `aebae2538a7aad83133ead00c7c752951a064914`, `00e35d98a49492a7913a1e862117c5ae19757d06` — Phase C implementation, repair, and audit.
- Baseline working tree: pre-existing `M source/python/README.md` plus untracked `RESEARCH`. The README edit was preserved and was never staged by this checkpoint.

### Accepted Phase A evidence

- Trusted archive: `D:\Stock\data\ATS\phase_a\runs\phasea-2a2b3898aba37814`.
  - 30 artifacts, 76,320 panel rows, 1,272 sessions, 145,937 validated equity bars.
  - Manifest logical hash `3abbab5961c9d6e27760167fc17eb8e15dc67335590e11c1d5ca63b22121062d`.
  - Archive-integrity validation passed against the retained source snapshot.
- Accepted extended diagnostic panel: `D:\Stock\data\ATS\decision_oriented_phase_a\runs\extension-20260820T163347Z`, internal ID `phasea-9a50dcdb3a4538d7`.
  - 85,800 official rows, 1,430 sessions, 2020-11-27 through 2026-08-18.
  - Physical manifest SHA-256 `1A68F010125B625CA55A21EFD4299D9A744B16BE11979810A71180ABEB813A7F`.
- Decision analysis: `analysis_runs\decision-20260820T164218Z`; reproduction `decision-20260820T170000Z-reproduction`; verification retained 20/20 byte-identical tables and matching logical metrics.
- Final classification report: `RESEARCH\PHASE_A_DECISION_ORIENTED_REPORT.md`, verified SHA-256 `C80998B674ECE20F24D33D62B4C347674E20A5139AC465BA89EBBEEC30D94770`.
- Earlier post-Phase-A report/run remains retained as audit history, not silently discarded.

### Accepted Phase B evidence

- GPW: `D:\Stock\data\ATS\phase_b\versions\phaseb-f88fc2d38e9811ed1573\manifest.json`.
  - Physical manifest SHA-256 `a3ef82c6aad77b99b5ff77f672475a45ad844b446ce1558eff22b51df9f29183`.
  - Clean implementation provenance at `94a0e6e0792937a4b6ec8dc69c66fca85908a877`.
  - 147,687 bars total (145,937 Phase-A-compatible equities plus 1,750 WIG), 2,039 aliases, 93 master rows, 1,760 membership rows.
  - Exact GPW reconciliation passed: semantic-key, numeric, identity, and membership hashes matched; official denominator and usable counts preserved at zero numeric tolerance.
- U.S.: `D:\Stock\data\ATS\phase_b\versions\phaseb-5d7086751156ac48cef3\manifest.json`.
  - Physical manifest SHA-256 `6deb73bf74d85357f4584542a7119eb86373604103e2e4b1b5b4d4f5e1a95618`.
  - 30,937,812 bars, 137 ingestion issues, 76,775 aliases, 15,355 provisional security identities.
  - Every issuer ID remains unresolved; U.S. notebook use is metadata/profile-only.
- Reports examined: `reference_validation.json`, `gpw_reconciliation.json`, `gpw_profile.json`, `us_reference.json`, `us_profile.json`, `transactional_publication_demo.json`, and `handoff.json` under `D:\Stock\data\ATS\phase_b\reports`.

### Accepted Phase C evidence

- Final run inferred from clean documentation-complete provenance: `D:\Stock\data\ATS\phase_c\runs\phasec-fa439d650410376aae9e`.
- Separate reproduction: `D:\Stock\data\ATS\phase_c\reproductions\00e35d9\phasec-fa439d650410376aae9e`.
- Implementation commit: `00e35d98a49492a7913a1e862117c5ae19757d06`; pinned GPW manifest SHA above.
- Accepted manifest file SHA-256 `81B9B301E86A0BDB28304C2F05AF55A1AD0160C352EDC8178651A16CF4B7B21A`; internal manifest hash `dd31c142ef698b7c6164e3ce3de54fc67bb8aee11e1d65e032141f5fc7038ed9`.
- Validation passed 16 artifacts, 60 ledger events, five fills, five independently reconstructed orders, five canonical fill sources, eleven canonical valuation sources, and eleven sessions.
- Reconciliation passed five fills/eleven sessions; hash `5d20048cccf2e6a1ff94990fd44eca622b694192f0dd5e2f8bea4a95bf0e7136`.
- Run and reproduction have the same run ID, metrics, and all ten ledger logical hashes. Ending equity/cash `1007072.062997` is only an accounting checksum.

## Validation commands and results

Set project imports for module commands:

```powershell
$env:PYTHONPATH = 'D:\Stock\ATS\source\python\src'
```

Commands were invoked through the repaired wrapper using `-PythonArgs` arrays.

| Validation | Result | Runtime/resource observation |
|---|---|---|
| `python -m pytest -p no:cacheprovider source\python\tests -q` | PASS, 80/80 | 52.27 s after kernel repair |
| `ats_research validate --run-dir ...phasea-2a2b3898aba37814` | PASS | 30 artifacts; 76,320 rows; 1,272 sessions |
| same validation for extended Phase A run | PASS | 30 artifacts; 85,800 rows; 1,430 sessions |
| `ats_data validate --manifest ...phaseb-f88...` | PASS | 147,687 GPW bars |
| `ats_data reconcile-gpw --config ...phase_b_reference.yaml --manifest ...phaseb-f88...` | PASS | tolerance 0; denominator/usable state preserved |
| `ats_data validate --manifest ...phaseb-5d708...` | PASS | 30,937,812 U.S. bars; about 167 s; no rebuild |
| `ats_portfolio validate --run-dir ...phasec-fa439...` | PASS | 16 artifacts; five fills; eleven sessions |
| `ats_portfolio reconcile --run-dir ...phasec-fa439...` | PASS | five fills, eleven sessions |
| Phase C reproduction validation | PASS | same ten logical ledger hashes |

All validation commands were read-only with respect to retained publications. The wrapper created only ignored runtime scratch under `RESEARCH\.tmp`.

## Notebook execution results

Final ordered execution occurred at `2026-08-21T14:44:16Z`, after the kernelspec repair and first retention commit. Each notebook used a fresh kernel; no network was required; no canonical-data write occurred; all retained outputs are small.

| Notebook | Code cells | Retained outputs | Runtime | Size | Cell errors |
|---|---:|---:|---:|---:|---:|
| 00 orientation/system map | 4 | 5 | 4.426 s | 27,247 B | 0 |
| 01 identity/point-in-time | 9 | 18 | 6.076 s | 67,594 B | 0 |
| 02 findings/diagnostics | 6 | 11 | 3.641 s | 46,118 B | 0 |
| 03 ledger/end-to-end | 6 | 9 | 9.757 s | 53,512 B | 0 |

The writable runtime repair removed the earlier user `.ipython` permission and selector-helper warnings. Jupyter still emits its standard warning that the local kernel transport uses unencrypted TCP; it caused no cell error and is not a native-library crash. No secret, token, or excessive environment dump is retained.

## Discrepancies and unclear behavior

1. PowerShell Python flags must be passed through the wrapper's explicit `-PythonArgs` array. A bare `-m` is parsed as a wrapper parameter and fails before Python starts; all documented review commands use the array form.
2. The pre-existing modified `source/python/README.md` is stale in two ways: it references a prior repaired-environment invocation and describes the project as stopping before portfolio simulation. It is preserved unstaged, per instruction, and is not sole evidence of status.
3. `test_phase_b_reference.py` pins superseded GPW/U.S. publications, not accepted `f88...`/`5d708...`; final-publication status relies on live final validation, GPW reconciliation, and retained reports. The final U.S. publication has 137 issues versus the older fixture's 135.
4. The GPW profile's 87-row “recent cross-section” contains all priced GPW instruments on the date, not the official TOP60. It must not be used as the official denominator.
5. Proximity changed definitions across retained analyses: the earlier diagnostic used prior close / 252-session maximum **high**; the final decision-oriented analysis uses prior close / 252-session maximum **close**. The notebook computes and labels both; the final `PROMISING` classification belongs to the later max-close definition.
6. Corporate-action/security-event schemas exist in `ats_contracts`, but the accepted Phase B GPW/U.S. manifests publish no such tables. Schema existence is not populated-data support.
7. Phase C has no explicit accepted/latest pointer. The final run is inferred from clean exact-HEAD provenance plus a separate matching reproduction.
8. `PHASE_C.md` still says final immutable publication/reproduction “follow,” even though both retained artifacts exist.
9. Phase C retains `validation_report.json` but no standalone `reconciliation_report.json`; reconciliation is recomputed and printed.
10. Phase C “60 events” means ledger events, not 60 corporate/security events. The accepted real run has zero corporate-action applications, all `cash_scale=1`, and only complete current valuations. Event/action, scaled-cash, stale, unresolved, and replay behavior is evidenced by tests/fixtures, not the real run.
11. Canonical completed-bar availability is later than the modeled open; Phase C explicitly assumes only the open field becomes visible at modeled exchange open. This is a timing model, not a vendor assertion that a completed daily bar was available then.
12. The extended Phase A manifest records a dirty checkout because of the README and untracked research, but it retains exact implementation hashes and a valid source snapshot. Archive integrity passes; “dirty” is not silently reclassified as clean.
13. Two old pytest temporary directories were ACL-inaccessible. Their temporary classification follows names/location only; contents remain NOT PROVEN and uncommitted.

No discrepancy was fixed in production code or publications during this review. The only installed-environment mutation was the Jupyter launch metadata repair requested after the crashes; package records and versions were unchanged.

## Assumptions

- The final decision-oriented Phase A report is authoritative for current research classifications; earlier diagnostics remain retained historical evidence.
- The final Phase C run is the clean-HEAD run with a matching reproduction; lack of an explicit acceptance pointer is recorded rather than hidden.
- A representative 2022-11-04 GPW session and CD Projekt identity are pedagogical examples; they do not imply selection for investment merit.
- Existing reports/profile JSONs are accepted retained measurement evidence where repeating a full build would violate checkpoint bounds.
- Durable research is staged from an explicit whitelist. Excluded research remains on disk and is not deleted.

## Material limitations

| Area | Current state | Consequence | Blocker for GPW research? | Trigger for future work |
|---|---|---|---|---|
| Historical TOP60 coverage | Official 60 always retained; priced population 57–60; feature population may be smaller | Coverage/calendar effects can change diagnostic sign/shape | Conditional: blocks claims that ignore missing states; not bounded caveated diagnostics | New authoritative price/exit evidence or independent sample |
| Unresolved members/benign exits | Five exit identities create 1,964 missing member-sessions in trusted Phase A | Outcomes are unobserved; denominator cannot shrink | Conditional | Canonical conversion/cash/exit histories |
| Reconstruction policy | Membership intervals reconstruct between official snapshots; announcement times may be null | Point-in-time membership availability is not fully demonstrated | Conditional | More frequent official snapshots with announcement/correction lineage |
| Stooq adjustment uncertainty | Bars marked vendor-adjusted semantics unverified | Momentum/high proximity can contain action artifacts | Yes for action-sensitive claims | Independently verified raw/adjusted series plus action factors |
| U.S. identity | 15,355 source-path-scoped provisional identities | No issuer-level continuity claim | No for GPW | Authoritative security/issuer master |
| U.S. issuer mapping | All issuer IDs unresolved | Cross-listing/issuer aggregation unsafe | No for GPW | Authoritative mappings and validity intervals |
| U.S. actions/validity | No authoritative actions or inferred validity ends | Event-adjusted research unsafe | No for GPW | Trusted action/security-event sources |
| Physical layout/pruning | Compact security-first files; GPW 1/2 and U.S. 1/252 candidate row groups for one-security queries; limited time pruning | Bounded reads work; date-heavy SLO may degrade | No currently | Measured SLO failure or materially degraded maintenance |
| Experiment tracking | Immutable manifests/runs exist; no `ats_tracking` package/service | Manual orchestration and comparison discipline | No for current bounded research | Multiple concurrent experiment families need a frozen contract |
| ML pipeline | Deferred | No validated train/validation/deployment workflow | No for current diagnostics | Explicitly authorized phase with leakage/evaluation contracts |
| Intraday/live execution | Deferred | Daily modeled simulation only | No for daily GPW research | Authoritative intraday data and broker/live requirements |
| Packaged-engine integration | Absent | No vectorbt/LEAN/Nautilus adapter is production behavior | No | A concrete adapter requirement after core contracts remain stable |

## Questions before authorizing more development

1. Should Phase C gain an immutable explicit acceptance record/pointer, or is clean-commit provenance plus reproduction the desired acceptance rule?
2. Which proximity definition, if any, should be frozen for an out-of-sample test—max close or max high—and what independent adjustment/action source is required first?
3. Is incomplete TOP60 coverage acceptable for the next GPW hypothesis, or must the five exit histories be resolved before new inference?
4. Which membership announcement/correction evidence is required to call reconstructed intervals fully point-in-time?
5. Should legacy machine-prefixed environment exports remain excluded now that the canonical prefix-free bundle exists?
6. What measured query/rebuild SLO would justify revisiting physical layout? No optimization should begin without that trigger.
7. What contract should govern the external research-to-`TargetWeightIntent` decision boundary before any orchestration is implemented?
8. Which Phase C synthetic policies need a bounded real-data event integration before they are considered operationally relied upon?

## Safe to rely on now

- Retained Phase A archive integrity and exact frozen feature/label conventions.
- Pinned GPW Phase B schema, identity, membership, versioning, and exact Phase A reconciliation.
- Manifest-driven bounded DuckDB/Polars/PyArrow access.
- Phase C deterministic next-open ledger for frozen external intents, explicit costs/movements, Decimal invariants, validation, and reproduction.

## Usable with documented caveats

- GPW diagnostic findings as hypotheses with explicit coverage/calendar, temporal, dependence, multiple-testing, and adjustment caveats.
- Reconstructed membership intervals with incomplete announcement-time evidence.
- U.S. source-scoped canonical facts without issuer continuity/action claims.
- Phase C event/stale/scaling policies as synthetically tested behavior; the accepted real run does not exercise them.

## Not implemented or not safe to rely on

- Deployable alpha, strategy returns, automatic signal selection, or an end-to-end feature-to-weights orchestrator.
- `ats_features` or `ats_tracking` modules, ML pipeline, packaged-engine adapter, intraday/live/broker execution, FX/margin/shorts, or Phase D.
- Authoritative U.S. issuer/corporate-action continuity, independently verified Stooq adjustments, exact live auction availability, or unobserved missing-member returns.
