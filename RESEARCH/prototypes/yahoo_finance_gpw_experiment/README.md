# Yahoo Finance GPW experiment

This isolated module acquires Yahoo Finance daily observations with yfinance,
preserves the source-native yfinance table, creates a loss-minimizing normalized
projection, validates OHLCV, and records provenance. It is experimental and is
not connected to accepted Phase A/B/C paths.

Required history settings are fixed in `YahooSettings`:

- `auto_adjust=False`
- `back_adjust=False`
- `repair=False`
- `actions=True`

Run the retained experiment:

```powershell
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  'D:\Stock\ATS\RESEARCH\prototypes\yahoo_finance_gpw_experiment\run_experiment.py'
```

Run focused, network-free tests:

```powershell
$env:PYTHONPATH = 'D:\Stock\ATS\RESEARCH\prototypes\yahoo_finance_gpw_experiment'
& 'D:\Stock\ATS\RESEARCH\prototypes\environment_repair\invoke_repaired_python.ps1' `
  -m pytest -p no:cacheprovider `
  'D:\Stock\ATS\RESEARCH\prototypes\yahoo_finance_gpw_experiment\tests'
```
