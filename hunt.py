#!/usr/bin/env python3
"""
Auction Hunter - Find profitable deals

Usage:
    python hunt.py "laptop"
    python hunt.py "iphone 14" --min-profit 50
"""

import sys
import asyncio
from scrapers.browser import BrowserScraper, AuctionItem
from utils.price_checker import analyze_deal, format_deal_alert


async def hunt_deals(
    query: str,
    max_results: int = 20,
    min_profit: float = 30
) -> dict:
    """Search for auction deals and analyze profitability"""
    
    scraper = BrowserScraper()
    deals = []
    all_items = []
    
    try:
        await scraper.start()
        print(f"🔍 Searching eBay for: {query}")
        
        items = await scraper.search_ebay(query, max_results)
        print(f"📦 Found {len(items)} items")
        
        for item in items:
            all_items.append(item)
            
            # Analyze deal
            analysis = analyze_deal(
                title=item.title,
                auction_price=item.price,
                shipping=item.shipping,
                condition=item.condition
            )
            
            if analysis:
                if analysis.profit >= min_profit:
                    deals.append({
                        'item': item,
                        'analysis': analysis
                    })
        
        # Sort by profit
        deals.sort(key=lambda x: x['analysis'].profit, reverse=True)
        
    finally:
        await scraper.stop()
    
    return {
        'query': query,
        'total_items': len(all_items),
        'deals_found': len(deals),
        'min_profit': min_profit,
        'deals': deals,
        'all_items': all_items
    }


def print_results(results: dict):
    """Print hunt results to console"""
    
    print(f"\n{'='*60}")
    print(f"🎯 Auction Hunt Results: {results['query']}")
    print(f"{'='*60}")
    print(f"Total items scanned: {results['total_items']}")
    print(f"Profitable deals (>${results['min_profit']} profit): {results['deals_found']}")
    
    if not results['deals']:
        print("\n😔 No deals matching criteria found.")
        print("\nAll items found:")
        for item in results['all_items'][:5]:
            print(f"  • ${item.price:.2f} - {item.title[:50]}...")
        return
    
    print(f"\n🔥 Top Deals:")
    print("-" * 60)
    
    for i, deal in enumerate(results['deals'][:10], 1):
        item = deal['item']
        analysis = deal['analysis']
        
        print(f"\n{i}. {item.title[:55]}...")
        print(f"   💵 Auction: ${item.price:.2f} + ${item.shipping:.2f} ship = ${analysis.total_cost:.2f}")
        print(f"   📈 Est. Profit: ${analysis.profit:.2f} ({analysis.profit_margin_percent:.0f}% margin)")
        print(f"   ⏰ {item.time_left} | Condition: {item.condition[:20]}")
        print(f"   🔗 {item.url[:70]}...")


def format_whatsapp_summary(results: dict) -> str:
    """Format results for WhatsApp message"""
    
    if not results['deals']:
        return f"🔍 *{results['query']}*\n\nScanned {results['total_items']} items. No deals >${results['min_profit']} profit found."
    
    lines = [
        f"🎯 *Auction Hunt: {results['query']}*",
        f"Found *{results['deals_found']}* profitable deals from {results['total_items']} items\n"
    ]
    
    for i, deal in enumerate(results['deals'][:5], 1):
        item = deal['item']
        analysis = deal['analysis']
        
        emoji = "🔥" if analysis.is_great_deal else "💰"
        lines.append(
            f"{emoji} *${analysis.profit:.0f} profit* - {item.title[:40]}...\n"
            f"   ${item.price:.0f} + ${item.shipping:.0f} ship → {item.time_left}"
        )
    
    if results['deals_found'] > 5:
        lines.append(f"\n...and {results['deals_found'] - 5} more deals")
    
    return "\n".join(lines)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python hunt.py <query> [--min-profit N]")
        print("Example: python hunt.py 'macbook pro' --min-profit 100")
        sys.exit(1)
    
    query = sys.argv[1]
    min_profit = 30
    
    if '--min-profit' in sys.argv:
        idx = sys.argv.index('--min-profit')
        if idx + 1 < len(sys.argv):
            min_profit = float(sys.argv[idx + 1])
    
    results = await hunt_deals(query, min_profit=min_profit)
    print_results(results)
    
    # Print WhatsApp format
    print(f"\n{'='*60}")
    print("📱 WhatsApp Message Format:")
    print("-" * 60)
    print(format_whatsapp_summary(results))


if __name__ == "__main__":
    asyncio.run(main())
