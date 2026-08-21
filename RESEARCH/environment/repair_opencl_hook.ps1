param(
    [string] $EnvironmentName = 'ats-stack-research'
)

$ErrorActionPreference = 'Stop'

$environmentRoot = Join-Path 'C:\Users\konra\anaconda3\envs' $EnvironmentName
$hook = Join-Path $environmentRoot 'etc\conda\activate.d\khronos-opencl-icd-loader_activate.bat'

if (-not (Test-Path -LiteralPath $hook)) {
    throw "OpenCL activation hook not found: $hook"
}

$replacement = @'
@echo off
set "OCL_ICD_FILENAMES_CONDA_BACKUP=%OCL_ICD_FILENAMES%"
for %%f in ("%CONDA_PREFIX%\Library\etc\OpenCL\vendors\*.icd") do if exist "%%~f" for /f "usebackq delims=" %%d in ("%%~f") do call set "OCL_ICD_FILENAMES=%%OCL_ICD_FILENAMES%%;%%d"
'@

[System.IO.File]::WriteAllText($hook, $replacement + "`r`n", [System.Text.Encoding]::ASCII)
Write-Output "Repaired OpenCL activation hook: $hook"

