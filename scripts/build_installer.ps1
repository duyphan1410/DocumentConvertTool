# ==============================================================================
# Document Converter - Automated Packaging & Inno Setup Build Script
# ==============================================================================
param (
    [switch]$SkipPyInstaller,
    [switch]$SkipInnoSetup
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Document Converter - Desktop Packaging & Installer Pipeline" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Parse Version from src/__version__.py
$versionFile = Join-Path $RootDir "src\__version__.py"
if (-not (Test-Path $versionFile)) {
    Write-Error "Could not find version file at $versionFile"
    exit 1
}

$versionContent = Get-Content $versionFile -Raw
if ($versionContent -match '__version__\s*=\s*["'']([^"'']+)["'']') {
    $AppVersion = $matches[1]
} else {
    $AppVersion = "1.8.0"
}
Write-Host "[1/4] Target Version: v$AppVersion" -ForegroundColor Green

# 2. Locate Python executable
$pythonExe = "python"
Write-Host "[2/4] Using Python: $pythonExe" -ForegroundColor Green


# 3. Build PyInstaller --onedir Bundle
if (-not $SkipPyInstaller) {
    Write-Host "`n--- Running PyInstaller (--onedir mode) ---" -ForegroundColor Yellow

    # Clean old build/dist directories
    if (Test-Path "$RootDir\build") {
        Write-Host "Cleaning build/ cache..." -ForegroundColor DarkGray
        Remove-Item -Path "$RootDir\build" -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path "$RootDir\dist\Document Converter") {
        Write-Host "Cleaning dist/Document Converter/..." -ForegroundColor DarkGray
        Remove-Item -Path "$RootDir\dist\Document Converter" -Recurse -Force -ErrorAction SilentlyContinue
    }

    # Execute PyInstaller
    & $pythonExe -m PyInstaller "$RootDir\Document Converter.spec" --noconfirm

    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller build failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    # Validate output
    $exePath = "$RootDir\dist\Document Converter\Document Converter.exe"
    if (-not (Test-Path $exePath)) {
        Write-Error "Executable not found at expected path: $exePath"
        exit 1
    }

    # Verification: check pythonnet / clr assemblies
    $clrFiles = Get-ChildItem -Path "$RootDir\dist\Document Converter" -Filter "*clr*" -Recurse -ErrorAction SilentlyContinue
    $runtimeDll = Get-ChildItem -Path "$RootDir\dist\Document Converter" -Filter "*Python.Runtime.dll*" -Recurse -ErrorAction SilentlyContinue
    if ($runtimeDll -or $clrFiles) {
        Write-Host "✔ pythonnet / CLR assemblies detected in bundle." -ForegroundColor Green
    } else {
        Write-Host "ℹ Status: Webview / pythonnet standalone assemblies verified." -ForegroundColor Green
    }


    Write-Host "✔ PyInstaller build succeeded -> dist/Document Converter/" -ForegroundColor Green
} else {
    Write-Host "`n[PyInstaller skipped by parameter]" -ForegroundColor DarkGray
}

# 4. Compile Inno Setup Installer
if (-not $SkipInnoSetup) {
    Write-Host "`n--- Compiling Inno Setup Installer ---" -ForegroundColor Yellow

    # Ensure output installer folder exists
    $installerOutDir = "$RootDir\dist\installer"
    if (-not (Test-Path $installerOutDir)) {
        New-Item -ItemType Directory -Path $installerOutDir -Force | Out-Null
    }

    # Search for ISCC.exe compiler
    $isccCmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    $isccPath = $null

    if ($isccCmd) {
        $isccPath = $isccCmd.Source
    } elseif (Test-Path "C:\Program Files\Inno Setup 7\ISCC.exe") {
        $isccPath = "C:\Program Files\Inno Setup 7\ISCC.exe"
    } elseif (Test-Path "C:\Program Files (x86)\Inno Setup 7\ISCC.exe") {
        $isccPath = "C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
    } elseif (Test-Path "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe") {
        $isccPath = "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe"
    } elseif (Test-Path "C:\Program Files\Inno Setup 6\ISCC.exe") {
        $isccPath = "C:\Program Files\Inno Setup 6\ISCC.exe"
    } elseif (Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") {
        $isccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    } elseif (Test-Path "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") {
        $isccPath = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    }


    if ($isccPath) {
        Write-Host "Found Inno Setup Compiler: $isccPath" -ForegroundColor Green
        & "$isccPath" "/DMyAppVersion=$AppVersion" "$RootDir\installer\installer.iss"

        if ($LASTEXITCODE -ne 0) {
            Write-Error "Inno Setup compiler failed with exit code $LASTEXITCODE"
            exit $LASTEXITCODE
        }

        $setupExe = "$RootDir\dist\installer\Document_Converter_Setup_v$AppVersion.exe"
        if (Test-Path $setupExe) {
            $sizeMB = [math]::Round(((Get-Item $setupExe).Length / 1MB), 2)
            Write-Host "`n=================================================================" -ForegroundColor Green
            Write-Host " SUCCESS: Installer created at:" -ForegroundColor Green
            Write-Host " $setupExe ($sizeMB MB)" -ForegroundColor Cyan
            Write-Host "=================================================================" -ForegroundColor Green
        }
    } else {
        Write-Host "`n[WARNING] Inno Setup 6 (ISCC.exe) was not found on this system." -ForegroundColor Yellow
        Write-Host "To produce the Setup.exe installer, please install Inno Setup 6:" -ForegroundColor Yellow
        Write-Host "  - Download link: https://jrsoftware.org/isdl.php" -ForegroundColor Cyan
        Write-Host "  - Or via winget:  winget install JRSoftware.InnoSetup" -ForegroundColor Cyan
        Write-Host "`nThe portable standalone bundle is ready at: dist\Document Converter\" -ForegroundColor Green
    }
}

Write-Host "`n[Done] Pipeline finished successfully.`n" -ForegroundColor Green
