param(
    [switch] $Replace
)

$ErrorActionPreference = 'Stop'

$conda = 'C:\Users\konra\anaconda3\Scripts\conda.exe'
$environmentName = 'ats-stack-research'
$environmentRoot = 'C:\Users\konra\anaconda3\envs\ats-stack-research'
$specification = Join-Path $PSScriptRoot 'environment.yml'
$repairHook = Join-Path $PSScriptRoot 'repair_opencl_hook.ps1'
$repairKernel = Join-Path $PSScriptRoot 'repair_jupyter_kernel.ps1'

if (Test-Path -LiteralPath $environmentRoot) {
    if (-not $Replace) {
        throw "Environment already exists. Re-run with -Replace to recreate it."
    }
    & $conda env remove --name $environmentName --yes
    if ($LASTEXITCODE -ne 0) {
        throw "Conda failed to remove $environmentName."
    }
}

& $conda env create --file $specification
if ($LASTEXITCODE -ne 0) {
    throw "Conda failed to create $environmentName."
}

& $repairHook -EnvironmentName $environmentName
if ($LASTEXITCODE -ne 0) {
    throw "Failed to repair the OpenCL activation hook."
}

& $repairKernel -EnvironmentRoot $environmentRoot
if ($LASTEXITCODE -ne 0) {
    throw "Failed to repair the Jupyter kernelspec environment."
}

& $conda run --name $environmentName --no-capture-output python --version
if ($LASTEXITCODE -ne 0) {
    throw "Canonical environment verification failed."
}

Write-Output "Recreated and verified $environmentName."
