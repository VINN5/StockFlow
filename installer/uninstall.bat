@echo off
title StockFlow Uninstaller
color 0C

echo.
echo  ================================================
echo   StockFlow Uninstaller
echo  ================================================
echo.
echo  WARNING: This will remove StockFlow and all its data.
echo.
set /p CONFIRM="Type YES to confirm uninstall: "
if /i not "%CONFIRM%"=="YES" (
    echo  Uninstall cancelled.
    pause
    exit /b 0
)

echo.
echo  [1/4] Stopping StockFlow...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im mongod.exe >nul 2>&1
echo  [OK] Processes stopped.

echo.
echo  [2/4] Removing StockFlow files...
rd /s /q "%USERPROFILE%\StockFlow" >nul 2>&1
echo  [OK] App files removed.

echo.
set /p DELDATA="Delete database and all business data? (y/n): "
if /i "%DELDATA%"=="y" (
    rd /s /q "%USERPROFILE%\StockFlow-data" >nul 2>&1
    echo  [OK] Database removed.
) else (
    echo  [SKIP] Database kept at %USERPROFILE%\StockFlow-data
)

echo.
echo  [4/4] Removing desktop shortcut...
del "%USERPROFILE%\Desktop\StockFlow.bat" >nul 2>&1
echo  [OK] Shortcut removed.

echo.
echo  ================================================
echo   StockFlow has been uninstalled.
echo  ================================================
echo.
pause