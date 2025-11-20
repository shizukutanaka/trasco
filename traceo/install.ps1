# Traceo Windows Installation Script
# Run as Administrator

param(
    [switch]$NoWait = $false
)

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

Write-Host "========================================"
Write-Host "  Traceo - 1-Click Installation (Windows)"
Write-Host "========================================"
Write-Host ""

# Step 1: Check Docker
Write-Warning "[1/4] Checking Docker installation..."
$dockerCheck = docker --version 2>$null
if ($null -eq $dockerCheck) {
    Write-Error "Docker not found. Please install Docker Desktop from https://www.docker.com"
    exit 1
}
Write-Success "Docker found: $dockerCheck"

# Step 2: Check Docker Compose
Write-Warning "[2/4] Checking Docker Compose installation..."
$composeCheck = docker-compose --version 2>$null
if ($null -eq $composeCheck) {
    Write-Error "Docker Compose not found. Please install Docker Desktop with Compose"
    exit 1
}
Write-Success "Docker Compose found: $composeCheck"

# Step 3: Start Docker Compose
Write-Warning "[3/4] Starting Traceo services..."
docker-compose up -d
if ($LASTEXITCODE -eq 0) {
    Write-Success "Services started"
} else {
    Write-Error "Failed to start services"
    exit 1
}

# Step 4: Wait for services
Write-Warning "[4/4] Waiting for services to be ready..."
Start-Sleep -Seconds 10

$backendHealth = $null
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction SilentlyContinue
    $backendHealth = $response.Content
} catch {
    $backendHealth = "error"
}

if ($backendHealth -match "ok") {
    Write-Success "All services are running"
} else {
    Write-Warning "Services are starting, this may take a moment..."
    Start-Sleep -Seconds 5
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Installation Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Open your browser and go to: http://localhost:3000" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop services, run: docker-compose down"
Write-Host "To view logs, run: docker-compose logs -f"
Write-Host ""

if (-not $NoWait) {
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
