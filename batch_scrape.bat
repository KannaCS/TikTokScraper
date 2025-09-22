@echo off
REM TikTok Batch Scraper - Easy large batch processing
REM Usage: batch_scrape.bat [count] [method]
REM Example: batch_scrape.bat 100 auto-search

setlocal enabledelayedexpansion

REM Default values
set COUNT=50
set METHOD=auto-search
set TIMESTAMP=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%

REM Parse command line arguments
if not "%1"=="" set COUNT=%1
if not "%2"=="" set METHOD=%2

REM Create output filename with timestamp
set OUTPUT_FILE=tiktok_results_%COUNT%_%METHOD%_%TIMESTAMP%.json

echo ========================================
echo TikTok Batch Scraper
echo ========================================
echo Count: %COUNT% videos
echo Method: %METHOD%
echo Output: %OUTPUT_FILE%
echo ========================================
echo.

REM Set UTF-8 encoding for proper Unicode support
chcp 65001 >nul

REM Run the scraper with proper encoding
python scraper.py --%METHOD% %COUNT% --cookie-file cookies.txt > "%OUTPUT_FILE%" 2>scrape_log.txt

REM Check if successful
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ SUCCESS! Scraped %COUNT% videos
    echo ✓ Results saved to: %OUTPUT_FILE%
    echo ✓ Log saved to: scrape_log.txt
    echo.
    
    REM Show file size
    for %%A in ("%OUTPUT_FILE%") do (
        echo File size: %%~zA bytes
    )
    
    REM Show first few lines of results
    echo.
    echo Preview of results:
    echo ----------------------------------------
    head -n 10 "%OUTPUT_FILE%" 2>nul || (
        REM Fallback if head command not available
        powershell "Get-Content '%OUTPUT_FILE%' | Select-Object -First 10"
    )
    echo ----------------------------------------
    
) else (
    echo.
    echo ❌ ERROR occurred during scraping
    echo Check scrape_log.txt for details
    type scrape_log.txt
)

echo.
echo Press any key to exit...
pause >nul
