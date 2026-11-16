# PostCare AI - Windows equivalent of the Makefile (no GNU Make needed).
# File is ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI.
# Examples:
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 setup
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 simulate -Bed A01 -Scenario bed-exit -Speed 1
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'setup', 'dev-api', 'dev-web', 'seed', 'simulate', 'test', 'lint',
        'format', 'format-check', 'typecheck', 'build', 'gen-api-types', 'check')]
    [string]$Task = 'help',
    [string]$Bed = 'A01',
    [string]$Scenario = 'bed-exit',
    [double]$Speed = 1,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Server = Join-Path $Root 'server'
$Web = Join-Path $Root 'web'

function Invoke-Step {
    param([string]$Exe, [string[]]$ArgList)
    Write-Host ">> $Exe $($ArgList -join ' ')" -ForegroundColor Cyan
    & $Exe @ArgList
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Exe $($ArgList -join ' ')" }
}

function Invoke-Uv([string[]]$ArgList) { Invoke-Step 'uv' (@('--directory', $Server) + $ArgList) }
function Invoke-Npm([string[]]$ArgList) { Invoke-Step 'npm' (@('--prefix', $Web) + $ArgList) }

switch ($Task) {
    'setup' { Invoke-Uv @('sync'); Invoke-Npm @('ci') }
    'dev-api' { Invoke-Uv @('run', 'uvicorn', 'postcare.api.main:app', '--host', '0.0.0.0', '--port', "$Port", '--reload') }
    'dev-web' { Invoke-Npm @('run', 'dev') }
    'seed' { Invoke-Uv @('run', 'postcare', 'seed') }
    'simulate' { Invoke-Uv @('run', 'postcare', 'simulate', '--bed', $Bed, '--scenario', $Scenario, '--speed', "$Speed") }
    'test' { Invoke-Uv @('run', 'pytest'); Invoke-Npm @('run', 'test') }
    'lint' { Invoke-Uv @('run', 'ruff', 'check', '.'); Invoke-Npm @('run', 'lint') }
    'format' { Invoke-Uv @('run', 'ruff', 'check', '--fix', '.'); Invoke-Uv @('run', 'ruff', 'format', '.'); Invoke-Npm @('run', 'format') }
    'format-check' { Invoke-Uv @('run', 'ruff', 'format', '--check', '.'); Invoke-Npm @('run', 'format:check') }
    'typecheck' { Invoke-Npm @('run', 'typecheck') }
    'build' { Invoke-Npm @('run', 'build') }
    'gen-api-types' {
        Invoke-Uv @('run', 'postcare', 'openapi', '--out', '../web/src/api/openapi.json')
        Invoke-Npm @('run', 'gen-api-types')
    }
    'check' {
        Invoke-Uv @('run', 'ruff', 'format', '--check', '.'); Invoke-Npm @('run', 'format:check')
        Invoke-Uv @('run', 'ruff', 'check', '.'); Invoke-Npm @('run', 'lint')
        Invoke-Npm @('run', 'typecheck')
        Invoke-Uv @('run', 'pytest'); Invoke-Npm @('run', 'test')
        Invoke-Npm @('run', 'build')
    }
    default {
        Write-Host 'Usage: scripts\dev.ps1 <setup|dev-api|dev-web|seed|simulate|test|lint|format|format-check|typecheck|build|gen-api-types|check> [-Bed A01] [-Scenario bed-exit] [-Speed 1]'
    }
}
