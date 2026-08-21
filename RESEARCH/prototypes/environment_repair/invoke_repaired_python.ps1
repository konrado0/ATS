param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PythonArgs
)

$ErrorActionPreference = 'Stop'

$environmentRoot = 'C:\Users\konra\anaconda3\envs\ats-stack-research'
$python = Join-Path $environmentRoot 'python.exe'
$runtimeRoot = 'D:\Stock\ATS\RESEARCH\.tmp\ats-env'
$tempRoot = Join-Path $runtimeRoot ('t-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$matplotlibRoot = Join-Path $runtimeRoot 'matplotlib'
$numbaRoot = Join-Path $runtimeRoot 'numba'
$ipythonRoot = Join-Path $runtimeRoot 'ipython'
$jupyterRoot = Join-Path $runtimeRoot 'jupyter'
$projectSource = 'D:\Stock\ATS\source\python\src'

New-Item -ItemType Directory -Force -Path $tempRoot, $matplotlibRoot, $numbaRoot, $ipythonRoot, $jupyterRoot | Out-Null

$env:TEMP = $tempRoot
$env:TMP = $tempRoot
$env:MPLCONFIGDIR = $matplotlibRoot
$env:NUMBA_CACHE_DIR = $numbaRoot
$env:IPYTHONDIR = $ipythonRoot
$env:JUPYTER_RUNTIME_DIR = $jupyterRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PATH = "$environmentRoot;$environmentRoot\Scripts;$environmentRoot\Library\bin;$env:PATH"
if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $projectSource
} else {
    $env:PYTHONPATH = "$projectSource;$env:PYTHONPATH"
}

& $python @PythonArgs
exit $LASTEXITCODE
