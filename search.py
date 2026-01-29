#!/usr/bin/env python3
"""
Auction Hunter - eBay Search CLI

Usage:
    python search.py "iphone 15"
    python search.py "laptop" --max-price 300
"""

import sys
import subprocess
import json
from scrapers.ebay_parser import parse_ebay_markdown, summarize_listings, filter_good_deals


def fetch_ebay(query: str, max_chars: int = 10000) -> str:
    """Fetch eBay search results using clawdbot's web_fetch"""
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=1&LH_Auction=1"
    
    # Use node to call web_fetch via clawdbot
    # This is a workaround - in production, integrate properly
    cmd = [
        'curl', '-s',
        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        '-H', 'Accept: text/html,application/xhtml+xml',
        '-H', 'Accept-Language: en-US,en;q=0.9',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout
    except Exception as e:
        return f"Error: {e}"


def search_ebay(query: str, max_price: float = None) -> dict:
    """
    Search eBay and return parsed results.
    
    Note: This function is designed to be called by Daklus,
    who has access to web_fetch. Pass the markdown text directly.
    """
    return {
        "query": query,
        "url": f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=1&LH_Auction=1",
        "note": "Use web_fetch to get results, then parse with parse_ebay_markdown()"
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python search.py <query> [--max-price N]")
        print("Example: python search.py 'macbook pro' --max-price 500")
        sys.exit(1)
    
    query = sys.argv[1]
    max_price = None
    
    if '--max-price' in sys.argv:
        idx = sys.argv.index('--max-price')
        if idx + 1 < len(sys.argv):
            max_price = float(sys.argv[idx + 1])
    
    print(f"🔍 Searching eBay for: {query}")
    print(f"URL: https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=1&LH_Auction=1")
    print()
    print("Note: Run via Daklus for best results (uses web_fetch)")
    print("      Direct curl may be blocked by eBay bot protection")


if __name__ == "__main__":
    main()
