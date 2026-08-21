param(
    [string] $EnvironmentRoot = 'C:\Users\konra\anaconda3\envs\ats-stack-research'
)

$ErrorActionPreference = 'Stop'

$kernelPath = Join-Path $EnvironmentRoot 'share\jupyter\kernels\python3\kernel.json'
$runtimeRoot = 'D:\Stock\ATS\RESEARCH\.tmp\ats-env'
$projectSource = 'D:\Stock\ATS\source\python\src'
$ipythonRoot = Join-Path $runtimeRoot 'ipython'
$jupyterRoot = Join-Path $runtimeRoot 'jupyter'
$matplotlibRoot = Join-Path $runtimeRoot 'matplotlib'
$numbaRoot = Join-Path $runtimeRoot 'numba'

if (-not (Test-Path -LiteralPath $kernelPath)) {
    throw "Python kernelspec not found: $kernelPath"
}

New-Item -ItemType Directory -Force -Path $ipythonRoot, $jupyterRoot, $matplotlibRoot, $numbaRoot | Out-Null

$kernel = Get-Content -LiteralPath $kernelPath -Raw | ConvertFrom-Json
$kernelEnvironment = [ordered]@{
    PATH = "$EnvironmentRoot;$EnvironmentRoot\Scripts;$EnvironmentRoot\Library\bin;" + '${PATH}'
    PYTHONPATH = $projectSource
    PYTHONDONTWRITEBYTECODE = '1'
    IPYTHONDIR = $ipythonRoot
    JUPYTER_RUNTIME_DIR = $jupyterRoot
    MPLCONFIGDIR = $matplotlibRoot
    NUMBA_CACHE_DIR = $numbaRoot
}

$kernel | Add-Member -NotePropertyName env -NotePropertyValue $kernelEnvironment -Force
$temporaryPath = "$kernelPath.tmp"
$kernel | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $temporaryPath -Encoding utf8
Move-Item -LiteralPath $temporaryPath -Destination $kernelPath -Force

Write-Output "Repaired Jupyter kernelspec environment: $kernelPath"
