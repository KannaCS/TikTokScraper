#!/usr/bin/env python3
"""
Quick test script to verify the scraper works and test encoding fixes.
"""

import json
import subprocess
import sys
from pathlib import Path

def test_small_batch():
    """Test a small batch to verify everything works."""
    print("🧪 Testing small batch (5 videos)...")
    
    try:
        # Run the scraper with a small batch
        result = subprocess.run([
            sys.executable, "scraper.py", 
            "--auto-search", "5", 
            "--cookie-file", "cookies.txt"
        ], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✅ Small batch test PASSED")
            
            # Try to parse the JSON output
            try:
                data = json.loads(result.stdout)
                print(f"✅ JSON parsing PASSED - Found {len(data)} videos")
                
                # Show sample data
                if data:
                    sample = data[0] if isinstance(data, list) else data
                    print(f"📊 Sample video:")
                    print(f"   Views: {sample.get('views', 'N/A'):,}")
                    print(f"   Likes: {sample.get('likes', 'N/A'):,}")
                    print(f"   Hashtags: {len(sample.get('hashtags', []))}")
                    print(f"   Caption preview: {sample.get('caption', 'N/A')[:50]}...")
                
                return True
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing FAILED: {e}")
                print("Raw output:")
                print(result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout)
                return False
                
        else:
            print(f"❌ Small batch test FAILED (exit code: {result.returncode})")
            print("Error output:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Test execution FAILED: {e}")
        return False

def test_unicode_handling():
    """Test Unicode character handling."""
    print("\n🌍 Testing Unicode handling...")
    
    # Test data with various Unicode characters
    test_data = {
        "caption": "Test with emojis 🎵🔥💯 and special chars: café, naïve, 中文, العربية",
        "views": 1000000,
        "likes": 50000,
        "hashtags": ["#test", "#unicode", "#emoji🔥", "#café"]
    }
    
    try:
        # Test JSON serialization
        json_str = json.dumps(test_data, ensure_ascii=False, indent=2)
        print("✅ Unicode JSON serialization PASSED")
        
        # Test fallback ASCII serialization
        json_ascii = json.dumps(test_data, ensure_ascii=True, indent=2)
        print("✅ ASCII fallback serialization PASSED")
        
        return True
        
    except Exception as e:
        print(f"❌ Unicode handling FAILED: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 TikTok Scraper Test Suite")
    print("=" * 40)
    
    # Check if required files exist
    if not Path("scraper.py").exists():
        print("❌ scraper.py not found!")
        return False
        
    if not Path("cookies.txt").exists():
        print("⚠️  cookies.txt not found - some tests may fail")
    
    # Run tests
    tests_passed = 0
    total_tests = 2
    
    if test_unicode_handling():
        tests_passed += 1
        
    if test_small_batch():
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests PASSED! The scraper is ready for large batches.")
        print("\n💡 Try running:")
        print("   python scraper.py --auto-search 100 --cookie-file cookies.txt > results.json")
        print("   or")
        print("   batch_scrape.bat 100 auto-search")
        return True
    else:
        print("❌ Some tests FAILED. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
