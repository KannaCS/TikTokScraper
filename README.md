# TikTok Video Metadata Scraper (requests-only)

This small script scrapes metadata from a TikTok video page using only the `requests` library by parsing embedded JSON within the HTML.

It extracts:
- Caption
- Views (playCount)
- Likes (diggCount)
- Shares (shareCount)
- Comments (commentCount)
- Hashtags (extracted from caption)

Results are printed as JSON to stdout.

## Quick Start

1) Install dependencies:

```bash
pip install -r requirements.txt
```

2) Run the scraper using one of several methods:

**Direct URL:**
```bash
python scraper.py https://www.tiktok.com/@someuser/video/1234567890123456789
```

**Auto-discovery options:**

```bash
# Latest video from a username
python scraper.py --latest-from @someuser

# Auto-detect from clipboard (copy a TikTok URL first)
python scraper.py --clipboard

# Intelligent auto-search (NEW!) - Discovers trending content automatically
python scraper.py --auto-search 5    # Get 5 videos using smart keyword search
python scraper.py --auto-search 100  # Large batch: Get 100 videos efficiently!

# Hashtag-based discovery (NEW!) - Uses popular hashtags
python scraper.py --hashtag-search 3   # Get 3 videos from trending hashtags
python scraper.py --hashtag-search 50  # Large batch: Get 50 videos from hashtags

# Manual search for videos by keyword
python scraper.py --search "mrbeast" --search-count 2

# Legacy trending discovery (may not work in all regions)
python scraper.py --trending 3  # Get 3 trending videos
```

**Large Batch Support**: Both `--auto-search` and `--hashtag-search` are optimized for large batches (100+ videos) with:
- Smart batching and progress tracking
- Automatic rate limiting
- Duplicate removal
- Success rate statistics
- Unicode encoding fixes for Windows

**Easy Batch Processing**:
```bash
# PowerShell script (recommended for Windows)
.\scrape_large.ps1 -Count 100 -Method "auto-search"

# Batch file
batch_scrape.bat 100 auto-search

# Direct command with proper encoding
python scraper.py --auto-search 100 --cookie-file cookies.txt > results.json
```

**Note**: Some discovery methods may be blocked in certain regions. Direct URLs are most reliable.

If successful, you'll see a JSON blob like:

```json
{
  "caption": "A nice caption with #hashtag and #trending",
  "views": 12345,
  "likes": 678,
  "shares": 9,
  "comments": 10,
  "hashtags": ["#hashtag", "#trending"]
}
```

## Cookies and Reliability

TikTok can sometimes block requests or hide data depending on region, rate limits, or if content is private. If you receive parsing errors or non-200 responses, you can supply a `Cookie` header to increase reliability.

There are two ways, and they work for both direct URLs and `--latest-from` resolution:

- Inline:

```bash
python scraper.py "https://www.tiktok.com/@user/video/123..." --cookie "tt_sessionid=...; sessionid=...; other=..."
```

- From file:

```bash
# With direct URL
python scraper.py "https://www.tiktok.com/@user/video/123..." --cookie-file cookies.txt

# With automatic latest video resolution
python scraper.py --latest-from @user --cookie-file cookies.txt
```

Where `cookies.txt` contains a single line representing the Cookie header value.

## Notes

- This script relies on embedded JSON blocks (SIGI_STATE or __NEXT_DATA__) in the HTML response. TikTok may change their structure at any time.
- Short share URLs will be followed via redirects.
- If a field is missing, the value may be `null` in the output JSON.

## Programmatic Usage

```python
from scraper import (
    scrape_tiktok_video, get_clipboard_url, search_videos,
    intelligent_auto_search, smart_hashtag_search
)

# Direct scraping
stats = scrape_tiktok_video("https://www.tiktok.com/@user/video/123...")
print(stats.as_dict())

# Auto-discovery functions
clipboard_url = get_clipboard_url()  # Get URL from clipboard
auto_urls = intelligent_auto_search(cookie="...", count=5)  # Smart trending search
hashtag_urls = smart_hashtag_search(cookie="...", count=3)  # Popular hashtag search
search_urls = search_videos("mrbeast", cookie="...", count=3)  # Manual search

# Process multiple URLs from intelligent search
for url in auto_urls:
    try:
        stats = scrape_tiktok_video(url, cookie="tt_sessionid=...;")
        print(f"Video: {url}")
        print(f"Caption: {stats.caption}")
        print(f"Views: {stats.views}, Likes: {stats.likes}")
        print(f"Hashtags: {stats.hashtags}")
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
```

## Troubleshooting

- If you see `Failed to parse TikTok metadata`, try providing cookies and confirm the video is public and accessible in your region.
- If you get `HTTP 403/404/5xx` errors, the content may be blocked, removed, private, or you may need to wait and try later.
- When using `--latest-from`, if the profile is empty/private or region-blocked, the script may not be able to determine the latest video without cookies.
- **Updated 2025**: The scraper now supports TikTok's latest `__UNIVERSAL_DATA_FOR_REHYDRATION__` structure for video pages.
- **Large Batch Optimization**: Efficiently handles 100+ video searches with smart batching, progress tracking, and statistics.
- **Unicode Support**: Fixed encoding issues for emojis and international characters in captions.
- **Batch Processing Tools**: Includes PowerShell script (`scrape_large.ps1`) and batch file (`batch_scrape.bat`) for easy large-scale scraping.
- If automatic username resolution fails, copy a video URL directly from the browser instead.
