@echo off
title Build TerrSet_LCM_Studio.exe (PyInstaller Standalone)
echo ============================================================================
echo Memulai proses pembuatan aplikasi mandiri TerrSet_LCM_Studio.exe...
echo ============================================================================

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PYTHON_BAT=C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat"

echo [1/2] Memastikan PyInstaller terpasang...
call "%PYTHON_BAT%" -m pip install --user pyinstaller

echo.
echo [2/2] Membungkus aplikasi menjadi TerrSet_LCM_Studio.exe...
call "%PYTHON_BAT%" -m PyInstaller --noconfirm --noconsole --onedir --name "TerrSet_LCM_Studio" --collect-data osgeo "%SCRIPT_DIR%lcm_tif_to_rst_gui.py"

echo.
echo ============================================================================
echo Selesai! File aplikasi .EXE tersedia di folder:
echo   %SCRIPT_DIR%dist\TerrSet_LCM_Studio\TerrSet_LCM_Studio.exe
echo ============================================================================
pause
