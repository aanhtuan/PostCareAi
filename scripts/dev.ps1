# PostCare AI - Windows equivalent of the Makefile (no GNU Make needed).
# Keep the task list identical to .PHONY in the Makefile (checked by server/tests/test_tooling.py).
# File is ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less files as ANSI.
# Examples:
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 setup
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 simulate -Bed A01 -Scenario bed-exit -Speed 1
#   powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 worker -Camera 1
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'setup', 'dev', 'dev-api', 'dev-web', 'worker', 'seed', 'simulate',
        'format', 'format-check', 'lint', 'typecheck', 'lint-imports', 'check-api-types', 'test',
        'test-vision', 'build-web', 'build', 'check', 'db-upgrade', 'db-seed', 'models',
        'gen-api-types')]
    [string]$Task = 'help',
    [string]$Bed = 'A01',
    [string]$Scenario = 'bed-exit',
    [double]$Speed = 1,
    [string]$Camera = '',
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

function Stop-Placeholder([string]$Message) {
    Write-Host $Message -ForegroundColor Yellow
    exit 1
}

function Invoke-FormatCheck {
    Invoke-Uv @('run', 'ruff', 'format', '--check', '.'); Invoke-Npm @('run', 'format:check')
}
function Invoke-Lint { Invoke-Uv @('run', 'ruff', 'check', '.'); Invoke-Npm @('run', 'lint') }
function Invoke-Typecheck { Invoke-Uv @('run', 'mypy'); Invoke-Npm @('run', 'typecheck') }
function Invoke-LintImports { Invoke-Uv @('run', 'lint-imports') }
function Invoke-CheckApiTypes {
    Invoke-Uv @('run', 'postcare', 'openapi', '--out', '../web/src/api/openapi.json', '--check')
    Invoke-Npm @('run', 'check-api-types')
}
function Invoke-Test { Invoke-Uv @('run', 'pytest', '-m', 'not vision'); Invoke-Npm @('run', 'test') }
function Invoke-BuildWeb { Invoke-Npm @('run', 'build') }

switch ($Task) {
    'setup' {
        Invoke-Uv @('sync'); Invoke-Npm @('ci')
        Invoke-Uv @('run', 'pre-commit', 'install', '--hook-type', 'pre-commit', '--hook-type', 'pre-push')
    }
    'dev' {
        Push-Location $Root
        try { Invoke-Step 'uv' @('run', '--project', 'server', 'honcho', '-f', 'Procfile.dev', 'start') }
        finally { Pop-Location }
    }
    'dev-api' { Invoke-Uv @('run', 'uvicorn', 'postcare.api.main:app', '--host', '0.0.0.0', '--port', "$Port", '--reload') }
    'dev-web' { Invoke-Npm @('run', 'dev') }
    'worker' { Stop-Placeholder "worker -Camera ${Camera}: not implemented yet - see F06. Use simulate meanwhile." }
    'seed' { Invoke-Uv @('run', 'postcare', 'seed', '--reset') }
    'simulate' { Invoke-Uv @('run', 'postcare', 'simulate', '--bed', $Bed, '--scenario', $Scenario, '--speed', "$Speed") }
    'format' { Invoke-Uv @('run', 'ruff', 'check', '--fix', '.'); Invoke-Uv @('run', 'ruff', 'format', '.'); Invoke-Npm @('run', 'format') }
    'format-check' { Invoke-FormatCheck }
    'lint' { Invoke-Lint }
    'typecheck' { Invoke-Typecheck }
    'lint-imports' { Invoke-LintImports }
    'check-api-types' { Invoke-CheckApiTypes }
    'test' { Invoke-Test }
    'test-vision' { Invoke-Uv @('run', 'pytest', '-m', 'vision') }
    'build-web' { Invoke-BuildWeb }
    'build' { Invoke-BuildWeb }
    'check' {
        Invoke-FormatCheck
        Invoke-Lint
        Invoke-Typecheck
        Invoke-LintImports
        Invoke-CheckApiTypes
        Invoke-Test
        Invoke-BuildWeb
    }
    'db-upgrade' { Invoke-Uv @('run', 'alembic', 'upgrade', 'head') }
    'db-seed' { Invoke-Uv @('run', 'postcare', 'seed') }
    'models' { Invoke-Uv @('run', 'postcare', 'models') }
    'gen-api-types' {
        Invoke-Uv @('run', 'postcare', 'openapi', '--out', '../web/src/api/openapi.json')
        Invoke-Npm @('run', 'gen-api-types')
    }
    default {
        Write-Host 'Usage: scripts\dev.ps1 <task> [-Bed A01] [-Scenario bed-exit] [-Speed 1] [-Camera 1] [-Port 8000]'
        Write-Host 'Tasks: setup dev dev-api dev-web worker seed simulate format format-check lint typecheck'
        Write-Host '       lint-imports check-api-types test test-vision build-web build check'
        Write-Host '       db-upgrade db-seed models gen-api-types  (same as make targets; see make help)'
    }
}
