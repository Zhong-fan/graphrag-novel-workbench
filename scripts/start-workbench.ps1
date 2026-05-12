Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    docker compose up -d mysql

    Push-Location frontend
    try {
        if (-not (Test-Path node_modules)) {
            npm install
        }
        npm run build
    }
    finally {
        Pop-Location
    }

    python -m app.api
}
finally {
    Pop-Location
}
