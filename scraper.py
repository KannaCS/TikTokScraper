#!/usr/bin/env python3
"""
TikTok video metadata scraper using requests only.
Extracts: caption, views, likes, shares, comments.

Usage:
  python scraper.py <tiktok_video_url> [--cookie "sessionid=...; ..."] [--cookie-file cookies.txt]

You can also import and call: scrape_tiktok_video(url, cookie=None)

Note: TikTok may geo-block or require cookies in some regions. Supplying a valid session cookie can improve reliability.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import requests

# Desktop user agent helps receive the desktop HTML that contains embedded JSON
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

SIGI_STATE_RE = re.compile(r"<script[^>]*id=\"SIGI_STATE\"[^>]*>(.*?)</script>", re.DOTALL)
NEXT_DATA_RE = re.compile(r"<script[^>]*id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>", re.DOTALL)
UNIVERSAL_DATA_RE = re.compile(r"<script[^>]*id=\"__UNIVERSAL_DATA_FOR_REHYDRATION__\"[^>]*>(.*?)</script>", re.DOTALL)


@dataclass
class TikTokVideoStats:
    caption: Optional[str]
    views: Optional[int]
    likes: Optional[int]
    shares: Optional[int]
    comments: Optional[int]
    hashtags: Optional[List[str]]

    def as_dict(self) -> Dict[str, Optional[int]]:
        return {
            "caption": self.caption,
            "views": self.views,
            "likes": self.likes,
            "shares": self.shares,
            "comments": self.comments,
            "hashtags": self.hashtags,
        }


def _parse_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        if isinstance(value, (int,)):
            return int(value)
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            # Remove commas and spaces
            v = value.replace(",", "").strip()
            if v.isdigit():
                return int(v)
        return None
    except Exception:
        return None


def _extract_hashtags(caption: Optional[str]) -> List[str]:
    """Extract hashtags from a caption string."""
    if not caption or not isinstance(caption, str):
        return []
    
    # Find all hashtags using regex
    # Matches # followed by word characters, numbers, and underscores
    hashtag_pattern = r'#[\w\u00c0-\u024f\u1e00-\u1eff\u0100-\u017f\u0180-\u024f\u1e00-\u1eff]+'
    hashtags = re.findall(hashtag_pattern, caption, re.IGNORECASE)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_hashtags = []
    for tag in hashtags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            unique_hashtags.append(tag)
    
    return unique_hashtags


def _extract_from_sigi_state(html: str) -> Optional[TikTokVideoStats]:
    m = SIGI_STATE_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    # Common location: ItemModule contains a dict keyed by item id
    item_module = data.get("ItemModule") or {}
    if isinstance(item_module, dict) and item_module:
        first_item = next(iter(item_module.values()))
        if isinstance(first_item, dict):
            desc = first_item.get("desc")
            stats = first_item.get("stats") or {}
            return TikTokVideoStats(
                caption=desc,
                views=_parse_int(stats.get("playCount")),
                likes=_parse_int(stats.get("diggCount")),
                shares=_parse_int(stats.get("shareCount")),
                comments=_parse_int(stats.get("commentCount")),
                hashtags=_extract_hashtags(desc),
            )

    # Alternate: SEOState or other fields sometimes contain counts
    return None


def _extract_from_universal_data(html: str) -> Optional[TikTokVideoStats]:
    m = UNIVERSAL_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    # __UNIVERSAL_DATA_FOR_REHYDRATION__ -> __DEFAULT_SCOPE__.webapp.video-detail.itemInfo.itemStruct
    try:
        item = (
            data.get("__DEFAULT_SCOPE__", {})
            .get("webapp.video-detail", {})
            .get("itemInfo", {})
            .get("itemStruct", {})
        )
        if not isinstance(item, dict) or not item:
            return None
        desc = item.get("desc")
        stats = item.get("stats", {})
        return TikTokVideoStats(
            caption=desc,
            views=_parse_int(stats.get("playCount")),
            likes=_parse_int(stats.get("diggCount")),
            shares=_parse_int(stats.get("shareCount")),
            comments=_parse_int(stats.get("commentCount")),
            hashtags=_extract_hashtags(desc),
        )
    except Exception:
        return None


def _extract_from_next_data(html: str) -> Optional[TikTokVideoStats]:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    # __NEXT_DATA__ -> props.pageProps.itemInfo.itemStruct
    try:
        item = (
            data.get("props", {})
            .get("pageProps", {})
            .get("itemInfo", {})
            .get("itemStruct", {})
        )
        if not isinstance(item, dict) or not item:
            return None
        desc = item.get("desc")
        stats = item.get("stats", {})
        return TikTokVideoStats(
            caption=desc,
            views=_parse_int(stats.get("playCount")),
            likes=_parse_int(stats.get("diggCount")),
            shares=_parse_int(stats.get("shareCount")),
            comments=_parse_int(stats.get("commentCount")),
            hashtags=_extract_hashtags(desc),
        )
    except Exception:
        return None


def scrape_tiktok_video(url: str, cookie: Optional[str] = None, timeout: int = 15, save_html_path: Optional[str] = None) -> TikTokVideoStats:
    """Fetch a TikTok video page and extract metadata using embedded JSON.

    Args:
        url: TikTok video URL (share link or canonical link)
        cookie: Optional Cookie header string: e.g. "tt_sessionid=...; sessionid=..."
        timeout: request timeout in seconds

    Returns:
        TikTokVideoStats with possible None values if not available

    Raises:
        requests.HTTPError for non-200 responses
        RuntimeError if parsing fails
    """
    session = requests.Session()
    headers = DEFAULT_HEADERS.copy()
    if cookie:
        headers["Cookie"] = cookie

    # Allow redirects to resolve short/share URLs
    resp = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    if resp.status_code != 200:
        # Some regions respond with 4xx/5xx when blocked
        resp.raise_for_status()

    html = resp.text

    # Save HTML for debugging if requested
    if save_html_path:
        try:
            with open(save_html_path, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception:
            pass

    # Try __UNIVERSAL_DATA_FOR_REHYDRATION__ first (current TikTok structure)
    stats = _extract_from_universal_data(html)
    if stats:
        return stats

    # Fallback to SIGI_STATE (older structure)
    stats = _extract_from_sigi_state(html)
    if stats:
        return stats

    # Fallback to __NEXT_DATA__ (oldest structure)
    stats = _extract_from_next_data(html)
    if stats:
        return stats

    # If nothing found, provide hints
    raise RuntimeError(
        "Failed to parse TikTok metadata. The page may be geo-blocked, private, or requires cookies."
    )


def get_clipboard_url() -> Optional[str]:
    """Try to get a TikTok URL from the clipboard."""
    try:
        # Windows clipboard access
        result = subprocess.run(['powershell', '-command', 'Get-Clipboard'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            clipboard_text = result.stdout.strip()
            # Check if it's a TikTok URL
            if 'tiktok.com' in clipboard_text and ('/video/' in clipboard_text or '/t/' in clipboard_text):
                return clipboard_text
    except Exception:
        pass
    return None


def discover_trending_videos(cookie: Optional[str] = None, count: int = 5, timeout: int = 15) -> List[str]:
    """Discover trending TikTok videos from the For You page."""
    headers = DEFAULT_HEADERS.copy()
    headers.setdefault("Referer", "https://www.tiktok.com/")
    if cookie:
        headers["Cookie"] = cookie
    
    try:
        # Try the main TikTok page
        resp = requests.get("https://www.tiktok.com/foryou", headers=headers, timeout=timeout)
        if resp.status_code != 200:
            resp = requests.get("https://www.tiktok.com/", headers=headers, timeout=timeout)
        
        if resp.status_code == 200:
            html = resp.text
            
            # Try to extract video URLs from __UNIVERSAL_DATA_FOR_REHYDRATION__
            m = UNIVERSAL_DATA_RE.search(html)
            if m:
                try:
                    data = json.loads(m.group(1))
                    # Look for video items in various locations
                    scope = data.get("__DEFAULT_SCOPE__", {})
                    
                    video_urls = []
                    
                    # Check webapp.video-detail if present
                    video_detail = scope.get("webapp.video-detail", {})
                    if video_detail:
                        item_info = video_detail.get("itemInfo", {})
                        item_struct = item_info.get("itemStruct", {})
                        if item_struct.get("id"):
                            author_id = item_struct.get("author", {}).get("uniqueId", "user")
                            video_id = item_struct.get("id")
                            video_urls.append(f"https://www.tiktok.com/@{author_id}/video/{video_id}")
                    
                    # Check for ItemModule (multiple videos)
                    item_module = scope.get("ItemModule", {})
                    if isinstance(item_module, dict):
                        for item in item_module.values():
                            if isinstance(item, dict) and item.get("id"):
                                author_id = item.get("author", {}).get("uniqueId", "user")
                                video_id = item.get("id")
                                video_urls.append(f"https://www.tiktok.com/@{author_id}/video/{video_id}")
                                if len(video_urls) >= count:
                                    break
                    
                    return video_urls[:count]
                except Exception:
                    pass
    except Exception:
        pass
    
    return []


def search_videos(query: str, cookie: Optional[str] = None, count: int = 5, timeout: int = 15) -> List[str]:
    """Search for TikTok videos by keyword."""
    headers = DEFAULT_HEADERS.copy()
    headers.setdefault("Referer", "https://www.tiktok.com/")
    if cookie:
        headers["Cookie"] = cookie
    
    try:
        # Use TikTok search API
        search_url = "https://www.tiktok.com/api/search/general/full/"
        params = {
            "keyword": query,
            "offset": 0,
            "count": count,
            "search_source": "normal_search"
        }
        
        resp = requests.get(search_url, headers=headers, params=params, timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json()
                video_urls = []
                
                # Extract video URLs from search results
                data_list = data.get("data", [])
                for item in data_list:
                    if item.get("type") == 1:  # Video type
                        item_info = item.get("item", {})
                        if item_info.get("id"):
                            author_id = item_info.get("author", {}).get("unique_id", "user")
                            video_id = item_info.get("id")
                            video_urls.append(f"https://www.tiktok.com/@{author_id}/video/{video_id}")
                
                return video_urls[:count]
            except Exception:
                pass
    except Exception:
        pass
    
    return []


def resolve_latest_video_url(username: str, cookie: Optional[str] = None, timeout: int = 15, save_html_path: Optional[str] = None, save_json_path: Optional[str] = None) -> str:
    """Resolve the latest video URL for a given TikTok username by scraping their profile page.

    Strategy:
    - Request https://www.tiktok.com/@{username}
    - Parse SIGI_STATE.
    - Prefer ItemList['user-post']['list'] which contains ordered video IDs; take the first.
    - Fallback to ItemModule: pick the item with the largest createTime.
    - Construct canonical URL: https://www.tiktok.com/@{username}/video/{video_id}
    """
    uname = username.strip().lstrip('@')
    if not uname:
        raise ValueError("Username cannot be empty for --latest-from")

    headers = DEFAULT_HEADERS.copy()
    headers.setdefault("Referer", "https://www.tiktok.com/")
    if cookie:
        headers["Cookie"] = cookie

    # Try multiple profile URL variants to improve odds of receiving parseable HTML
    profile_urls = [
        f"https://www.tiktok.com/@{uname}",
        f"https://www.tiktok.com/@{uname}?lang=en",
        f"https://www.tiktok.com/@{uname}?lang=en-US",
        f"https://m.tiktok.com/@{uname}",
    ]

    last_html: Optional[str] = None
    for profile_url in profile_urls:
        resp = requests.get(profile_url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            # try next variation
            last_html = resp.text
            continue

        html = resp.text
        last_html = html

        # a) Try __UNIVERSAL_DATA_FOR_REHYDRATION__ first (current structure)
        m_universal = UNIVERSAL_DATA_RE.search(html)
        if m_universal:
            try:
                universal_data = json.loads(m_universal.group(1))
                # Try to extract from webapp.user-detail.userInfo
                user_detail = universal_data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
                if user_detail:
                    # Look for itemList in user-detail
                    item_list = user_detail.get("itemList", [])
                    if isinstance(item_list, list) and item_list:
                        # Get the first (latest) video ID
                        vid = str(item_list[0].get("id", ""))
                        if vid:
                            return f"https://www.tiktok.com/@{uname}/video/{vid}"
            except Exception:
                pass

        # b) SIGI_STATE fallback
        m = SIGI_STATE_RE.search(html)
        data: Optional[Dict[str, Any]] = None
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                data = None

        if data:
            # 1) Try ItemList user-post list (often ordered newest first)
            item_list = (data.get("ItemList") or {}).get("user-post") or {}
            video_ids = item_list.get("list") if isinstance(item_list, dict) else None
            if isinstance(video_ids, list) and video_ids:
                vid = str(video_ids[0])
                return f"https://www.tiktok.com/@{uname}/video/{vid}"

            # 2) Fallback: use ItemModule and pick newest by createTime
            item_module = data.get("ItemModule") or {}
            if isinstance(item_module, dict) and item_module:
                def _created(item: Dict[str, Any]) -> int:
                    try:
                        return int(item.get("createTime") or 0)
                    except Exception:
                        return 0

                # Ensure dict of items
                items = [v for v in item_module.values() if isinstance(v, dict)]
                if items:
                    newest = max(items, key=_created)
                    vid = str(newest.get("id")) if newest.get("id") is not None else None
                    if vid:
                        return f"https://www.tiktok.com/@{uname}/video/{vid}"

        # c) __NEXT_DATA__ on profile page
        m_next = NEXT_DATA_RE.search(html)
        if m_next:
            try:
                nd = json.loads(m_next.group(1))
            except json.JSONDecodeError:
                nd = None
            if isinstance(nd, dict):
                # Try common paths within __NEXT_DATA__
                props = nd.get("props", {}) if isinstance(nd.get("props", {}), dict) else {}
                page_props = props.get("pageProps", {}) if isinstance(props.get("pageProps", {}), dict) else {}

                # a) itemList -> user-post -> list (IDs)
                item_list = page_props.get("itemList", {}) if isinstance(page_props.get("itemList", {}), dict) else {}
                up = item_list.get("user-post", {}) if isinstance(item_list.get("user-post", {}), dict) else {}
                ids = up.get("list")
                if isinstance(ids, list) and ids:
                    return f"https://www.tiktok.com/@{uname}/video/{ids[0]}"

                # b) items: list of itemStructs
                items = page_props.get("items")
                if isinstance(items, list) and items:
                    # choose newest by createTime
                    def _ctime(it: Dict[str, Any]) -> int:
                        try:
                            return int(it.get("createTime") or it.get("stats", {}).get("createTime") or 0)
                        except Exception:
                            return 0
                    newest = max([i for i in items if isinstance(i, dict)], key=_ctime)
                    vid = newest.get("id") or newest.get("itemId") or newest.get("aweme_id")
                    if vid:
                        return f"https://www.tiktok.com/@{uname}/video/{vid}"

                # c) itemInfo.itemStruct if only one
                item_info = page_props.get("itemInfo", {}) if isinstance(page_props.get("itemInfo", {}), dict) else {}
                item_struct = item_info.get("itemStruct", {}) if isinstance(item_info.get("itemStruct", {}), dict) else {}
                vid = item_struct.get("id")
                if vid:
                    return f"https://www.tiktok.com/@{uname}/video/{vid}"

    # Save last HTML for debugging if requested
    if save_html_path and last_html is not None:
        try:
            with open(save_html_path, "w", encoding="utf-8") as f:
                f.write(last_html)
        except Exception:
            pass

    # Final fallback: TikTok web APIs (requires cookies in many regions)
    try:
        # 1) Resolve secUid from username
        user_detail_url = "https://www.tiktok.com/api/user/detail/"
        params = {"aid": "1988", "uniqueId": uname}
        r = requests.get(user_detail_url, headers=headers, params=params, timeout=timeout)
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("application/json"):
            user_json = r.json()
        else:
            try:
                user_json = r.json()
            except Exception:
                user_json = None

        if isinstance(user_json, dict):
            # Optionally save json for debugging
            if save_json_path:
                try:
                    with open(save_json_path, "w", encoding="utf-8") as f:
                        json.dump({"user_detail": user_json}, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            user_info = user_json.get("userInfo") or user_json.get("user") or {}
            sec_uid = None
            if isinstance(user_info, dict):
                sec_uid = user_info.get("user", {}).get("secUid") if isinstance(user_info.get("user"), dict) else user_info.get("secUid")
            if not sec_uid:
                sec_uid = user_json.get("secUid")

            if sec_uid:
                # 2) Fetch recent posts via item_list
                item_list_url = "https://www.tiktok.com/api/post/item_list/"
                params2 = {"aid": "1988", "count": "30", "secUid": sec_uid}
                r2 = requests.get(item_list_url, headers=headers, params=params2, timeout=timeout)
                items_json = None
                if r2.status_code == 200:
                    try:
                        items_json = r2.json()
                    except Exception:
                        items_json = None
                # Save JSON if requested
                if save_json_path and items_json is not None:
                    try:
                        with open(save_json_path, "a", encoding="utf-8") as f:
                            f.write("\n\n")
                            json.dump({"item_list": items_json}, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

                # Extract latest video id
                if isinstance(items_json, dict):
                    item_list = items_json.get("itemList") or items_json.get("items")
                    if isinstance(item_list, list) and item_list:
                        def _ctime(it: Dict[str, Any]) -> int:
                            try:
                                return int(it.get("createTime") or 0)
                            except Exception:
                                return 0
                        newest = max([i for i in item_list if isinstance(i, dict)], key=_ctime)
                        vid = newest.get("id") or newest.get("itemId") or newest.get("aweme_id")
                        if vid:
                            return f"https://www.tiktok.com/@{uname}/video/{vid}"
    except Exception:
        # Swallow and fall through to final error
        pass

    raise RuntimeError("Could not determine latest video from profile. The profile may be empty or blocked.")


def _read_cookie_file(path: str) -> Optional[str]:
    if not path:
        return None
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cookie file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Scrape TikTok video metadata using requests only.")
    parser.add_argument("url", nargs="?", help="TikTok video URL (optional if using discovery options)")
    parser.add_argument("--latest-from", dest="latest_from", help="Username to auto-resolve latest video URL (e.g., @user or user)", default=None)
    parser.add_argument("--clipboard", action="store_true", help="Auto-detect TikTok URL from clipboard")
    parser.add_argument("--trending", type=int, metavar="N", help="Discover N trending videos (default: 1)", default=None)
    parser.add_argument("--search", dest="search_query", help="Search for videos by keyword", default=None)
    parser.add_argument("--search-count", type=int, default=1, help="Number of search results to process (default: 1)")
    parser.add_argument("--cookie", dest="cookie", help="Cookie header string", default=None)
    parser.add_argument("--cookie-file", dest="cookie_file", help="Path to a file containing Cookie header", default=None)
    parser.add_argument("--save-html-profile", dest="save_html_profile", help="Path to save the fetched profile HTML for debugging", default=None)
    parser.add_argument("--save-json-profile", dest="save_json_profile", help="Path to save the fetched profile JSON for debugging (API fallback)", default=None)
    parser.add_argument("--save-html-video", dest="save_html_video", help="Path to save the fetched video HTML for debugging", default=None)
    args = parser.parse_args(argv)

    cookie = args.cookie
    if args.cookie_file and not cookie:
        cookie = _read_cookie_file(args.cookie_file)

    # Auto-discovery logic
    target_urls = []
    
    # 1. Direct URL provided
    if args.url:
        target_urls = [args.url]
    
    # 2. Latest from username
    elif args.latest_from:
        try:
            target_url = resolve_latest_video_url(
                args.latest_from,
                cookie=cookie,
                save_html_path=args.save_html_profile,
                save_json_path=args.save_json_profile,
            )
            target_urls = [target_url]
            print(f"Resolved latest video URL: {target_url}", file=sys.stderr)
        except Exception as e:
            print(f"Error resolving latest video: {e}", file=sys.stderr)
            return 1
    
    # 3. Clipboard detection
    elif args.clipboard:
        clipboard_url = get_clipboard_url()
        if clipboard_url:
            target_urls = [clipboard_url]
            print(f"Found TikTok URL in clipboard: {clipboard_url}", file=sys.stderr)
        else:
            print("No TikTok URL found in clipboard", file=sys.stderr)
            return 1
    
    # 4. Trending videos
    elif args.trending is not None:
        count = args.trending if args.trending > 0 else 1
        trending_urls = discover_trending_videos(cookie=cookie, count=count)
        if trending_urls:
            target_urls = trending_urls
            print(f"Found {len(trending_urls)} trending video(s)", file=sys.stderr)
        else:
            print("No trending videos found", file=sys.stderr)
            return 1
    
    # 5. Search videos
    elif args.search_query:
        search_urls = search_videos(args.search_query, cookie=cookie, count=args.search_count)
        if search_urls:
            target_urls = search_urls
            print(f"Found {len(search_urls)} video(s) for '{args.search_query}'", file=sys.stderr)
        else:
            print(f"No videos found for '{args.search_query}'", file=sys.stderr)
            return 1
    
    # No discovery method specified
    else:
        parser.print_usage(sys.stderr)
        print("error: provide a video URL or use a discovery option (--latest-from, --clipboard, --trending, --search)", file=sys.stderr)
        return 2
    
    # Process all discovered URLs
    results = []
    for i, target_url in enumerate(target_urls):
        try:
            if len(target_urls) > 1:
                print(f"\n--- Video {i+1}/{len(target_urls)}: {target_url} ---", file=sys.stderr)
            
            stats = scrape_tiktok_video(target_url, cookie=cookie, save_html_path=args.save_html_video)
            result = stats.as_dict()
            result["url"] = target_url
            results.append(result)
            
        except requests.HTTPError as e:
            print(f"HTTP error for {target_url}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Error for {target_url}: {e}", file=sys.stderr)
            continue
    
    if not results:
        print("No videos could be scraped", file=sys.stderr)
        return 1
    
    # Output results
    if len(results) == 1:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    
    return 0

    # This section is now handled above in the discovery logic


if __name__ == "__main__":
    raise SystemExit(main())
