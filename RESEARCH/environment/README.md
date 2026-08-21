# ATS research Conda environment

`environment.yml` is the canonical, fully pinned Windows Conda specification
for the ATS research stack. It records exact Conda versions and build strings,
plus the pip-managed packages retained by the verified environment.

Create the canonical environment from scratch:

```powershell
& 'D:\Stock\ATS\RESEARCH\environment\recreate_environment.ps1'
```

To deliberately replace an existing copy, pass `-Replace`. This removes the
existing `ats-stack-research` environment before recreating it.

Create it under a temporary validation name instead:

```powershell
& 'C:\Users\konra\anaconda3\Scripts\conda.exe' env create `
  --name ats-stack-research-validation `
  --file 'D:\Stock\ATS\RESEARCH\environment\environment.yml'
```

Verification performed before promoting the repaired clone:

- 366 Conda package records matched the previous environment exactly by name,
  version, build string, and channel.
- 203 `pip freeze --all` records matched exactly.
- The scientific/native-library smoke test passed.
- The complete ATS test suite passed: 47 tests.

The file deliberately omits a `prefix:` so it is portable across user profiles.
It is platform-specific to Windows because exact Conda build strings are pinned.
The recreation script also applies `repair_opencl_hook.ps1`, replacing a broken
upstream Windows activation hook that attempts to write a temporary file inside
the environment prefix. That post-create repair is required for warning-free
`conda run` under restricted process permissions.

It also applies `repair_jupyter_kernel.ps1`. The generated Python kernelspec
must prepend the environment root, `Scripts`, and `Library\bin` to `PATH`;
otherwise delayed NumPy/SciPy native-library loading can terminate a fresh
Windows kernel with `0xC06D007F`. The repair also sends IPython, Jupyter,
Matplotlib, and Numba runtime files to the ignored `RESEARCH\.tmp\ats-env`
root. It is idempotent and does not change package versions.

For ATS work, invoke Python through the canonical wrapper to isolate temporary
and cache paths and avoid Conda activation-hook defects:

```powershell
& 'D:\Stock\ATS\RESEARCH\environment\invoke_ats_python.ps1' `
  -PythonArgs @('--version')
```

The wrapper also provides `D:\Stock\ATS\source\python\src` through
`PYTHONPATH`; pass Python arguments using the explicit `-PythonArgs` array so
PowerShell does not interpret Python flags as wrapper parameters.
