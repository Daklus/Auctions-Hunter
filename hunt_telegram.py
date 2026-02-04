#!/usr/bin/env python3
"""
Hunt with Telegram Notifications

Sends deal alerts directly to your personal Telegram when profitable
auctions are found.

Usage:
    python hunt_telegram.py "macbook pro" --min-profit 50
    python hunt_telegram.py "thinkpad" --notify-all
"""

import sys
import asyncio
import argparse
from scrapers.browser import BrowserScraper
from utils.price_checker import analyze_deal
from notifications.telegram import TelegramNotifier


async def hunt_with_notifications(
    query: str,
    max_results: int = 20,
    min_profit: float = 30,
    notify_threshold: int = 5,  # Only send if we find at least N deals
    notify_individual: bool = False,  # Send individual alerts for each deal
    silent: bool = False  # Don't print to console
) -> dict:
    """
    Hunt for deals and send Telegram notifications
    
    Returns results dict for further processing
    """
    
    notifier = TelegramNotifier()
    scraper = BrowserScraper()
    
    deals = []
    all_items = []
    
    try:
        await scraper.start()
        if not silent:
            print(f"🔍 Searching eBay for: {query}")
        
        items = await scraper.search_ebay(query, max_results)
        if not silent:
            print(f"📦 Found {len(items)} items")
        
        for item in items:
            all_items.append(item)
            
            analysis = analyze_deal(
                title=item.title,
                auction_price=item.price,
                shipping=item.shipping,
                condition=item.condition
            )
            
            if analysis and analysis.profit >= min_profit:
                deal_data = {
                    'item': item,
                    'analysis': analysis
                }
                deals.append(deal_data)
                
                # Send individual notification if requested
                if notify_individual and notifier.should_notify(item.url):
                    message = notifier.format_deal_message(
                        title=item.title,
                        price=item.price,
                        shipping=item.shipping,
                        profit=analysis.profit,
                        margin=analysis.profit_margin_percent,
                        condition=item.condition,
                        time_left=item.time_left,
                        url=item.url,
                        source="eBay",
                        image_url=item.image_url
                    )
                    
                    # Print the message for Clawdbot to pick up
                    print(f"\n{'='*60}")
                    print("📱 TELEGRAM NOTIFICATION:")
                    print(f"{'='*60}")
                    print(message)
                    print(f"{'='*60}\n")
                    
                    notifier.mark_sent(item.url)
        
        # Sort by profit
        deals.sort(key=lambda x: x['analysis'].profit, reverse=True)
        
        # Send summary notification if we found enough deals
        if len(deals) >= notify_threshold or (deals and notify_individual):
            deal_dicts = []
            for d in deals:
                deal_dicts.append({
                    'title': d['item'].title,
                    'profit': d['analysis'].profit,
                    'margin': d['analysis'].profit_margin_percent,
                    'url': d['item'].url
                })
            
            summary = notifier.format_summary(query, deal_dicts, len(all_items))
            
            if not notify_individual:  # Only print summary if we didn't send individuals
                print(f"\n{'='*60}")
                print("📱 TELEGRAM SUMMARY:")
                print(f"{'='*60}")
                print(summary)
                print(f"{'='*60}\n")
        
    finally:
        await scraper.stop()
    
    return {
        'query': query,
        'total_items': len(all_items),
        'deals_found': len(deals),
        'deals': deals
    }


def print_results(results: dict, min_profit: float):
    """Print hunt results to console"""
    
    print(f"\n{'='*60}")
    print(f"🎯 Auction Hunt Results: {results['query']}")
    print(f"{'='*60}")
    print(f"Total items scanned: {results['total_items']}")
    print(f"Profitable deals (>${min_profit} profit): {results['deals_found']}")
    
    if not results['deals']:
        print("\n😔 No deals matching criteria found.")
        return
    
    print(f"\n🔥 Top Deals:")
    print("-" * 60)
    
    for i, deal in enumerate(results['deals'][:10], 1):
        item = deal['item']
        analysis = deal['analysis']
        
        emoji = "🔥" if analysis.is_great_deal else "💰"
        print(f"\n{i}. {item.title[:55]}...")
        print(f"   {emoji} Profit: ${analysis.profit:.2f} ({analysis.profit_margin_percent:.0f}%)")
        print(f"   💵 ${item.price:.2f} + ${item.shipping:.2f} ship")
        print(f"   ⏰ {item.time_left}")


def main():
    parser = argparse.ArgumentParser(
        description='Hunt for auction deals with Telegram notifications'
    )
    parser.add_argument('query', help='Search query (e.g., "macbook pro")')
    parser.add_argument('--min-profit', type=float, default=30,
                       help='Minimum profit threshold (default: 30)')
    parser.add_argument('--max-results', type=int, default=20,
                       help='Max items to scan (default: 20)')
    parser.add_argument('--notify-threshold', type=int, default=1,
                       help='Only notify if we find at least N deals (default: 1)')
    parser.add_argument('--notify-all', action='store_true',
                       help='Send individual notification for each deal')
    parser.add_argument('--silent', action='store_true',
                       help='Minimal console output')
    
    args = parser.parse_args()
    
    print(f"🚀 Starting hunt with Telegram notifications...")
    print(f"   Query: {args.query}")
    print(f"   Min profit: ${args.min_profit}")
    print(f"   Notifications: {'Individual' if args.notify_all else 'Summary'}")
    
    results = asyncio.run(hunt_with_notifications(
        query=args.query,
        max_results=args.max_results,
        min_profit=args.min_profit,
        notify_threshold=args.notify_threshold,
        notify_individual=args.notify_all,
        silent=args.silent
    ))
    
    if not args.silent:
        print_results(results, args.min_profit)
    
    # Exit code based on results
    sys.exit(0 if results['deals_found'] > 0 else 1)


if __name__ == "__main__":
    main()
