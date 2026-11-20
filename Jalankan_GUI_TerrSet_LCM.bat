@echo off
setlocal EnableDelayedExpansion
title TerrSet LCM Studio — Validator, Aligner ^& .RST/.RDC Converter
echo ============================================================================
echo Membuka TerrSet LCM Studio (GUI Validator ^& Konverter .TIF ke .RST/.RDC)...
echo ============================================================================

set "SCRIPT_DIR=%~dp0"
set "PYTHON_LAUNCHER="

:: 1. Cari otomatis instalasi QGIS versi berapa pun di C:\Program Files\QGIS*
for /f "delims=" %%D in ('dir /b /ad /o-n "C:\Program Files\QGIS*" 2^>nul') do (
    if not defined PYTHON_LAUNCHER (
        if exist "C:\Program Files\%%D\bin\python-qgis-ltr.bat" (
            set "PYTHON_LAUNCHER=C:\Program Files\%%D\bin\python-qgis-ltr.bat"
        ) else if exist "C:\Program Files\%%D\bin\python-qgis.bat" (
            set "PYTHON_LAUNCHER=C:\Program Files\%%D\bin\python-qgis.bat"
        )
    )
)

:: 2. Cek jika terinstal melalui OSGeo4W (C:\OSGeo4W64 atau C:\OSGeo4W)
if not defined PYTHON_LAUNCHER (
    if exist "C:\OSGeo4W64\bin\python-qgis-ltr.bat" set "PYTHON_LAUNCHER=C:\OSGeo4W64\bin\python-qgis-ltr.bat"
    if exist "C:\OSGeo4W64\bin\python-qgis.bat" set "PYTHON_LAUNCHER=C:\OSGeo4W64\bin\python-qgis.bat"
    if exist "C:\OSGeo4W\bin\python-qgis-ltr.bat" set "PYTHON_LAUNCHER=C:\OSGeo4W\bin\python-qgis-ltr.bat"
    if exist "C:\OSGeo4W\bin\python-qgis.bat" set "PYTHON_LAUNCHER=C:\OSGeo4W\bin\python-qgis.bat"
)

:: 3. Jalankan menggunakan Python QGIS jika ditemukan, atau fallback ke Python sistem
if defined PYTHON_LAUNCHER (
    echo Menggunakan Python GIS dari: "!PYTHON_LAUNCHER!"
    call "!PYTHON_LAUNCHER!" "%SCRIPT_DIR%lcm_tif_to_rst_gui.py"
) else (
    echo QGIS tidak terdeteksi di folder standar. Mencoba menggunakan Python sistem...
    python "%SCRIPT_DIR%lcm_tif_to_rst_gui.py"
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [PERHATIAN] Gagal membuka aplikasi.
    echo Pastikan komputer ini memiliki QGIS terinstal, ATAU Python 3 dengan pustaka:
    echo   pip install PyQt5 rasterio numpy pyproj
    pause
)
