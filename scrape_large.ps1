# TikTok Large Batch Scraper with proper UTF-8 encoding
# Usage: .\scrape_large.ps1 -Count 100 -Method "auto-search"

param(
    [int]$Count = 50,
    [string]$Method = "auto-search",
    [string]$OutputFile = ""
)

# Set UTF-8 encoding for proper Unicode support
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Generate output filename if not provided
if ($OutputFile -eq "") {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputFile = "tiktok_results_${Count}_${Method}_${timestamp}.json"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TikTok Large Batch Scraper" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Count: $Count videos" -ForegroundColor Yellow
Write-Host "Method: $Method" -ForegroundColor Yellow
Write-Host "Output: $OutputFile" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if cookies.txt exists
if (-not (Test-Path "cookies.txt")) {
    Write-Host "⚠️  Warning: cookies.txt not found. Some regions may require cookies." -ForegroundColor Yellow
    Write-Host ""
}

# Run the scraper with proper UTF-8 encoding
Write-Host "🚀 Starting scraper..." -ForegroundColor Green

try {
    # Capture both stdout and stderr
    $process = Start-Process -FilePath "python" -ArgumentList "scraper.py", "--$Method", $Count, "--cookie-file", "cookies.txt" -RedirectStandardOutput $OutputFile -RedirectStandardError "scrape_log.txt" -Wait -PassThru -NoNewWindow
    
    if ($process.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "✅ SUCCESS! Scraped $Count videos" -ForegroundColor Green
        Write-Host "✅ Results saved to: $OutputFile" -ForegroundColor Green
        Write-Host "✅ Log saved to: scrape_log.txt" -ForegroundColor Green
        Write-Host ""
        
        # Show file info
        if (Test-Path $OutputFile) {
            $fileInfo = Get-Item $OutputFile
            Write-Host "File size: $($fileInfo.Length) bytes" -ForegroundColor Cyan
            
            # Try to parse and show summary
            try {
                $jsonContent = Get-Content $OutputFile -Raw -Encoding UTF8 | ConvertFrom-Json
                if ($jsonContent -is [Array]) {
                    $totalViews = ($jsonContent | Measure-Object -Property views -Sum).Sum
                    $totalLikes = ($jsonContent | Measure-Object -Property likes -Sum).Sum
                    Write-Host "Total Views: $($totalViews.ToString('N0'))" -ForegroundColor Cyan
                    Write-Host "Total Likes: $($totalLikes.ToString('N0'))" -ForegroundColor Cyan
                } else {
                    Write-Host "Single video result" -ForegroundColor Cyan
                }
            } catch {
                Write-Host "JSON parsing completed (summary unavailable)" -ForegroundColor Yellow
            }
        }
        
        # Show log summary
        if (Test-Path "scrape_log.txt") {
            Write-Host ""
            Write-Host "Recent log entries:" -ForegroundColor Cyan
            Write-Host "----------------------------------------" -ForegroundColor DarkGray
            Get-Content "scrape_log.txt" | Select-Object -Last 5 | ForEach-Object {
                Write-Host $_ -ForegroundColor Gray
            }
            Write-Host "----------------------------------------" -ForegroundColor DarkGray
        }
        
    } else {
        Write-Host ""
        Write-Host "❌ ERROR occurred during scraping (Exit code: $($process.ExitCode))" -ForegroundColor Red
        Write-Host "Check scrape_log.txt for details:" -ForegroundColor Yellow
        
        if (Test-Path "scrape_log.txt") {
            Get-Content "scrape_log.txt" | ForEach-Object {
                Write-Host $_ -ForegroundColor Red
            }
        }
    }
    
} catch {
    Write-Host "❌ Failed to start scraper: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Scraping complete!" -ForegroundColor Green
