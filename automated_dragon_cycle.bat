@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Dragon Automated Cycle Monitor
echo ========================================
echo.

:START_CYCLE
echo [INFO] Starting new cycle...
echo [INFO] Step 1: Starting Coin Transaction Monitor
echo.

REM Clear wallets.txt to start fresh
echo. > "Dragon\data\Solana\BulkWallet\wallets.txt"

REM Start the coin transaction monitor in background
start "Coin Monitor" /min node coin-transaction-monitor.js

echo [INFO] Monitoring wallets.txt for 4000 lines...
echo [INFO] Current wallet count: 0

:MONITOR_WALLETS
REM Check if wallets.txt exists and count lines
if exist "Dragon\data\Solana\BulkWallet\wallets.txt" (
    for /f %%i in ('type "Dragon\data\Solana\BulkWallet\wallets.txt" ^| find /c /v ""') do set WALLET_COUNT=%%i
) else (
    set WALLET_COUNT=0
)

REM Display progress every 100 wallets
set /a PROGRESS_CHECK=!WALLET_COUNT! %% 100
if !PROGRESS_CHECK! equ 0 (
    echo [INFO] Current wallet count: !WALLET_COUNT! / 4000
)

REM Check if we have reached 4000 wallets
if !WALLET_COUNT! geq 4000 (
    echo [INFO] Target reached! Stopping coin monitor and starting Dragon...
    echo.
    
    REM Kill the coin monitor process
    taskkill /f /im node.exe 2>nul
    
    REM Wait a moment for the monitor to close
    timeout /t 3 /nobreak >nul
    
    echo [INFO] Step 2: Starting Dragon Wallet Checker
    echo [INFO] Automated sequence: 1 -> 2 -> 2 -> 7 -> n -> n -> 10
    echo.
    
    REM Create input file for automated Dragon interaction
    echo 1 > dragon_input.txt
    echo 2 >> dragon_input.txt
    echo 2 >> dragon_input.txt
    echo 7 >> dragon_input.txt
    echo n >> dragon_input.txt
    echo n >> dragon_input.txt
    echo 10 >> dragon_input.txt
    
    REM Run Dragon with automated input
    python dragon.py < dragon_input.txt
    
    REM Clean up input file
    del dragon_input.txt 2>nul
    
    echo.
    echo [INFO] Dragon cycle completed. Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
    
    echo [INFO] Starting new cycle...
    echo.
    goto START_CYCLE
) else (
    REM Wait 10 seconds before checking again
    timeout /t 10 /nobreak >nul
    goto MONITOR_WALLETS
)

:END
echo [INFO] Automated cycle completed.
pause
