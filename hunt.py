#!/usr/bin/env python3
"""
Auction Hunter - Find profitable deals across multiple sources

Usage:
    python hunt.py "laptop"
    python hunt.py "iphone 14" --min-profit 50 --min-margin 30
    python hunt.py "thinkpad" --sources ebay,propertyroom
    python hunt.py "thinkpad" --telegram  # Send results to Telegram
"""

import sys
import asyncio
from dataclasses import dataclass
from typing import List, Optional
from scrapers.browser import BrowserScraper, AuctionItem
from scrapers.propertyroom import PropertyRoomScraper
from utils.price_checker import analyze_deal, ProfitAnalysis
from notifications.clawdbot_integration import ClawdbotNotifier, send_summary_alert


@dataclass
class DealResult:
    """A deal with its analysis"""
    item: AuctionItem
    analysis: ProfitAnalysis
    source: str


async def hunt_deals(
    query: str,
    max_results: int = 20,
    min_profit: float = 30,
    min_margin: float = 25,
    max_margin: float = 100,
    sources: List[str] = None
) -> dict:
    """
    Search for auction deals and analyze profitability.
    
    Args:
        query: Search term
        max_results: Max items per source
        min_profit: Minimum profit in dollars
        min_margin: Minimum profit margin % (default 25%)
        max_margin: Maximum margin % to filter outliers (default 100%)
        sources: List of sources to search ['ebay', 'propertyroom']
    """
    
    if sources is None:
        sources = ['ebay', 'propertyroom']
    
    all_items = []
    deals = []
    source_stats = {}
    
    # Initialize scrapers
    browser_scraper = BrowserScraper() if 'ebay' in sources else None
    pr_scraper = PropertyRoomScraper() if 'propertyroom' in sources else None
    
    try:
        # Start browser if needed
        if browser_scraper:
            await browser_scraper.start()
        
        # Search eBay
        if 'ebay' in sources and browser_scraper:
            print(f"🔍 Searching eBay for: {query}")
            try:
                ebay_items = await browser_scraper.search_ebay(query, max_results)
                print(f"📦 eBay: Found {len(ebay_items)} items")
                source_stats['ebay'] = len(ebay_items)
                
                for item in ebay_items:
                    item.source = 'ebay'
                    all_items.append(item)
                    
                    analysis = analyze_deal(
                        title=item.title,
                        auction_price=item.price,
                        shipping=item.shipping,
                        condition=item.condition
                    )
                    
                    if analysis and _is_good_deal(analysis, min_profit, min_margin, max_margin):
                        deals.append(DealResult(item=item, analysis=analysis, source='ebay'))
                        
            except Exception as e:
                print(f"eBay error: {e}")
                source_stats['ebay'] = 0
        
        # Search PropertyRoom
        if 'propertyroom' in sources and pr_scraper:
            print(f"🚔 Searching PropertyRoom for: {query}")
            try:
                pr_items = await pr_scraper.search(query, max_results)
                print(f"📦 PropertyRoom: Found {len(pr_items)} items")
                source_stats['propertyroom'] = len(pr_items)
                
                for item in pr_items:
                    all_items.append(item)
                    
                    # PropertyRoom items are police auction - assume "used" condition
                    analysis = analyze_deal(
                        title=item.title,
                        auction_price=item.price,
                        shipping=item.shipping,
                        condition="Pre-Owned"  # Most PropertyRoom items are recovered
                    )
                    
                    if analysis and _is_good_deal(analysis, min_profit, min_margin, max_margin):
                        deals.append(DealResult(item=item, analysis=analysis, source='propertyroom'))
                        
            except Exception as e:
                print(f"PropertyRoom error: {e}")
                source_stats['propertyroom'] = 0
        
        # Sort by profit margin (best deals first)
        deals.sort(key=lambda x: x.analysis.profit_margin_percent, reverse=True)
        
    finally:
        if browser_scraper:
            await browser_scraper.stop()
    
    return {
        'query': query,
        'total_items': len(all_items),
        'deals_found': len(deals),
        'min_profit': min_profit,
        'min_margin': min_margin,
        'source_stats': source_stats,
        'deals': deals,
        'all_items': all_items
    }


def _is_good_deal(analysis: ProfitAnalysis, min_profit: float, min_margin: float, max_margin: float) -> bool:
    """Check if deal meets criteria"""
    return (
        analysis.profit >= min_profit and
        analysis.profit_margin_percent >= min_margin and
        analysis.profit_margin_percent <= max_margin  # Filter unrealistic margins
    )


def print_results(results: dict):
    """Print hunt results to console"""
    
    print(f"\n{'='*60}")
    print(f"🎯 Auction Hunt Results: {results['query']}")
    print(f"{'='*60}")
    
    # Source breakdown
    print(f"\n📊 Sources searched:")
    for source, count in results.get('source_stats', {}).items():
        emoji = "📦" if source == 'ebay' else "🚔"
        print(f"   {emoji} {source}: {count} items")
    
    print(f"\nTotal items scanned: {results['total_items']}")
    print(f"Filters: >${results['min_profit']} profit, >{results['min_margin']}% margin")
    print(f"Profitable deals found: {results['deals_found']}")
    
    if not results['deals']:
        print("\n😔 No deals matching criteria found.")
        print("\nSample items found:")
        for item in results['all_items'][:5]:
            print(f"  • ${item.price:.2f} - {item.title[:50]}...")
        return
    
    print(f"\n🔥 Top Deals (sorted by margin):")
    print("-" * 60)
    
    for i, deal in enumerate(results['deals'][:10], 1):
        item = deal.item
        analysis = deal.analysis
        source_emoji = "📦" if deal.source == 'ebay' else "🚔"
        deal_emoji = "🔥" if analysis.is_great_deal else "💰"
        
        print(f"\n{deal_emoji} {i}. [{source_emoji} {deal.source}] {item.title[:50]}...")
        print(f"   💵 Auction: ${item.price:.2f} + ${item.shipping:.2f} ship = ${analysis.total_cost:.2f}")
        print(f"   📈 Est. Retail: ${analysis.estimated_retail:.2f} → Profit: ${analysis.profit:.2f} ({analysis.profit_margin_percent:.0f}%)")
        print(f"   ⏰ {item.time_left}")
        print(f"   🔗 {item.url[:70]}...")


def format_whatsapp_summary(results: dict) -> str:
    """Format results for WhatsApp/Telegram message"""
    
    if not results['deals']:
        return f"🔍 *{results['query']}*\n\nScanned {results['total_items']} items across {len(results.get('source_stats', {}))} sources.\nNo deals >${results['min_profit']} profit found."
    
    lines = [
        f"🎯 *Auction Hunt: {results['query']}*",
        f"Found *{results['deals_found']}* profitable deals from {results['total_items']} items\n"
    ]
    
    for i, deal in enumerate(results['deals'][:5], 1):
        item = deal.item
        analysis = deal.analysis
        source_emoji = "📦" if deal.source == 'ebay' else "🚔"
        deal_emoji = "🔥" if analysis.is_great_deal else "💰"
        
        lines.append(
            f"{deal_emoji} *${analysis.profit:.0f} profit ({analysis.profit_margin_percent:.0f}%)*\n"
            f"   {source_emoji} {item.title[:40]}...\n"
            f"   ${item.price:.0f} → ${analysis.expected_sell_price:.0f} resale"
        )
    
    if results['deals_found'] > 5:
        lines.append(f"\n...and {results['deals_found'] - 5} more deals")
    
    return "\n".join(lines)


def format_telegram_deals(results: dict) -> str:
    """Format top deals for Telegram with clickable links"""
    
    if not results['deals']:
        return f"🔍 *{results['query']}*\n\nNo profitable deals found."
    
    lines = [f"🎯 *{results['query']}* — {results['deals_found']} deals\n"]
    
    for i, deal in enumerate(results['deals'][:5], 1):
        item = deal.item
        analysis = deal.analysis
        emoji = "🔥" if analysis.profit_margin_percent >= 40 else "💰"
        
        lines.append(
            f"{emoji} *${analysis.profit:.0f}* profit ({analysis.profit_margin_percent:.0f}%)\n"
            f"[{item.title[:35]}...]({item.url})\n"
            f"Bid: ${item.price:.0f} → Sell: ${analysis.expected_sell_price:.0f}\n"
        )
    
    return "\n".join(lines)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python hunt.py <query> [options]")
        print("\nOptions:")
        print("  --min-profit N     Minimum profit in dollars (default: 30)")
        print("  --min-margin N     Minimum profit margin % (default: 25)")
        print("  --max-margin N     Maximum margin % filter (default: 100)")
        print("  --sources X,Y      Sources to search (ebay,propertyroom)")
        print("  --telegram         Send formatted output for Telegram")
        print("\nExamples:")
        print("  python hunt.py 'macbook pro' --min-profit 100")
        print("  python hunt.py 'thinkpad' --min-margin 30 --max-margin 50")
        print("  python hunt.py 'laptop' --sources propertyroom")
        print("  python hunt.py 'laptop' --telegram")
        sys.exit(1)
    
    query = sys.argv[1]
    min_profit = 30
    min_margin = 25
    max_margin = 100
    sources = ['ebay', 'propertyroom']
    send_telegram = '--telegram' in sys.argv or '--notify' in sys.argv
    
    # Parse arguments
    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == '--min-profit' and i + 1 < len(args):
            min_profit = float(args[i + 1])
        elif arg == '--min-margin' and i + 1 < len(args):
            min_margin = float(args[i + 1])
        elif arg == '--max-margin' and i + 1 < len(args):
            max_margin = float(args[i + 1])
        elif arg == '--sources' and i + 1 < len(args):
            sources = [s.strip() for s in args[i + 1].split(',')]
    
    print(f"Hunting for: {query}")
    print(f"Criteria: >${min_profit} profit, {min_margin}-{max_margin}% margin")
    print(f"Sources: {', '.join(sources)}\n")
    
    results = await hunt_deals(
        query, 
        min_profit=min_profit, 
        min_margin=min_margin,
        max_margin=max_margin,
        sources=sources
    )
    
    print_results(results)
    
    # Print messaging formats
    print(f"\n{'='*60}")
    print("📱 Telegram Format:")
    print("-" * 60)
    print(format_telegram_deals(results))
    
    # Print Telegram format if requested
    if send_telegram:
        print(f"\n{'='*60}")
        print("📱 Telegram Notification Format:")
        print("-" * 60)
        
        # Format deals for summary
        deal_dicts = []
        for deal in results['deals']:
            deal_dicts.append({
                'title': deal.item.title,
                'profit': deal.analysis.profit,
                'margin_percent': deal.analysis.profit_margin_percent,
                'url': deal.item.url
            })
        
        telegram_msg = send_summary_alert(
            query=results['query'],
            deals=deal_dicts,
            total_scanned=results['total_items']
        )
        print(telegram_msg)
        print(f"\n✅ Send this to Daniel's Telegram (ID: 493895844)")


if __name__ == "__main__":
    asyncio.run(main())
