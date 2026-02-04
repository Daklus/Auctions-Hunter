"""
Auction Hunter Web Dashboard

FastAPI app to search and view deals across multiple auction sources.
"""

from fastapi import FastAPI, Request, Query, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
import secrets
import asyncio
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.browser import BrowserScraper
from scrapers.propertyroom import PropertyRoomScraper
from utils.price_checker import analyze_deal
from db.database import (
    init_db, is_deal_seen, mark_deal_seen, log_search,
    get_recent_searches, get_stats, save_deal, get_saved_deals
)

app = FastAPI(title="Auction Hunter", version="2.0")
security = HTTPBasic()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database initialized")

# Credentials - set via environment or defaults
USERNAME = os.getenv("AUCTION_USER", "hunter")
PASSWORD = os.getenv("AUCTION_PASS", "deals2026")


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic auth credentials"""
    correct_username = secrets.compare_digest(credentials.username, USERNAME)
    correct_password = secrets.compare_digest(credentials.password, PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <title>Auction Hunter 🎯</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {{
            --bg-dark: #0f0f1a;
            --bg-card: #1a1a2e;
            --accent: #00d9ff;
            --accent-hover: #00b4d8;
            --profit-great: #ff6b6b;
            --profit-good: #4ecdc4;
            --text: #eee;
            --text-muted: #888;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }}
        h1 {{
            color: var(--accent);
            font-size: 28px;
        }}
        .search-form {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            width: 100%;
            max-width: 700px;
        }}
        .search-input {{
            flex: 1;
            min-width: 200px;
            padding: 14px 18px;
            font-size: 16px;
            border: 2px solid #333;
            border-radius: 10px;
            background: var(--bg-card);
            color: var(--text);
            transition: border-color 0.2s;
        }}
        .search-input:focus {{
            border-color: var(--accent);
            outline: none;
        }}
        .search-btn {{
            padding: 14px 28px;
            font-size: 16px;
            background: var(--accent);
            color: #000;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.2s;
        }}
        .search-btn:hover {{ background: var(--accent-hover); }}
        .search-btn:disabled {{
            background: #555;
            cursor: wait;
        }}
        .options {{
            display: flex;
            gap: 20px;
            margin: 15px 0;
            flex-wrap: wrap;
        }}
        .option {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: var(--text-muted);
        }}
        .option input[type="number"] {{
            width: 70px;
            padding: 6px;
            border: 1px solid #444;
            border-radius: 5px;
            background: var(--bg-card);
            color: var(--text);
        }}
        .option label {{
            display: flex;
            align-items: center;
            gap: 5px;
            cursor: pointer;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 15px;
            margin: 25px 0;
        }}
        .stat {{
            background: var(--bg-card);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: var(--accent);
        }}
        .stat-label {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 5px;
        }}
        .source-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .source-ebay {{ background: #e53238; color: white; }}
        .source-propertyroom {{ background: #2563eb; color: white; }}
        .deals {{
            display: grid;
            gap: 15px;
        }}
        .deal {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 20px;
            border-left: 4px solid #444;
            transition: transform 0.2s;
        }}
        .deal:hover {{ transform: translateX(5px); }}
        .deal.great {{ border-left-color: var(--profit-great); }}
        .deal.good {{ border-left-color: var(--profit-good); }}
        .deal-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 15px;
            margin-bottom: 12px;
        }}
        .deal-title {{
            font-size: 16px;
            line-height: 1.4;
        }}
        .deal-title a {{
            color: var(--text);
            text-decoration: none;
        }}
        .deal-title a:hover {{ color: var(--accent); }}
        .deal-profit {{
            font-size: 22px;
            font-weight: bold;
            color: var(--profit-good);
            white-space: nowrap;
        }}
        .deal.great .deal-profit {{ color: var(--profit-great); }}
        .deal-meta {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            font-size: 14px;
            color: var(--text-muted);
        }}
        .deal-meta span {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .time-urgent {{ color: #ffd93d; }}
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }}
        .empty-state h2 {{ margin-bottom: 15px; color: var(--text); }}
        .loading {{
            text-align: center;
            padding: 40px;
        }}
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid #333;
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            border-top: 1px solid #333;
            color: var(--text-muted);
            font-size: 14px;
        }}
        @media (max-width: 600px) {{
            .deal-header {{ flex-direction: column; }}
            .deal-profit {{ align-self: flex-start; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 Auction Hunter</h1>
        </header>
        
        <form class="search-form" method="get" action="/search" id="searchForm">
            <input type="text" name="q" class="search-input" 
                   placeholder="Search for deals (e.g., thinkpad, iphone 14, macbook)" 
                   value="{query}" required>
            <button type="submit" class="search-btn" id="searchBtn">🔍 Hunt Deals</button>
        </form>
        
        <div class="options">
            <div class="option">
                <label>Min Profit: $</label>
                <input type="number" name="min_profit" value="{min_profit}" min="0" form="searchForm">
            </div>
            <div class="option">
                <label>Min Margin: </label>
                <input type="number" name="min_margin" value="{min_margin}" min="0" max="100" form="searchForm">%
            </div>
            <div class="option">
                <label>
                    <input type="checkbox" name="ebay" value="1" {ebay_checked} form="searchForm">
                    📦 eBay
                </label>
            </div>
            <div class="option">
                <label>
                    <input type="checkbox" name="propertyroom" value="1" {pr_checked} form="searchForm">
                    🚔 PropertyRoom
                </label>
            </div>
        </div>
        
        {content}
        
        <footer>
            Auction Hunter v2.0 — Built by Daklus ⚡
        </footer>
    </div>
</body>
</html>"""


def render_page(query: str = "", content: str = "", min_profit: int = 30, 
                min_margin: int = 25, ebay: bool = True, propertyroom: bool = True) -> str:
    return HTML_TEMPLATE.format(
        query=query,
        content=content,
        min_profit=min_profit,
        min_margin=min_margin,
        ebay_checked="checked" if ebay else "",
        pr_checked="checked" if propertyroom else ""
    )


def deal_card(source: str, url: str, title: str, profit: float, price: float, 
              shipping: float, time_left: str, condition: str, 
              margin: float, is_great: bool, is_good: bool) -> str:
    deal_class = "great" if is_great else "good" if is_good else ""
    source_class = f"source-{source}"
    source_label = "eBay" if source == "ebay" else "PropertyRoom"
    
    # Check if time is urgent (less than 1 hour)
    time_class = "time-urgent" if any(x in time_left.lower() for x in ['m ', 'min', ':']) and 'h' not in time_left.lower() else ""
    
    return f"""<div class="deal {deal_class}">
    <div class="deal-header">
        <div class="deal-title">
            <span class="source-badge {source_class}">{source_label}</span>
            <a href="{url}" target="_blank" rel="noopener">{title}</a>
        </div>
        <div class="deal-profit">${profit:.0f} ({margin:.0f}%)</div>
    </div>
    <div class="deal-meta">
        <span>💵 ${price:.2f} + ${shipping:.2f} ship</span>
        <span class="{time_class}">⏰ {time_left}</span>
        <span>📦 {condition}</span>
    </div>
</div>"""


@app.get("/", response_class=HTMLResponse)
async def home(username: str = Depends(verify_credentials)):
    content = """
    <div class="empty-state">
        <h2>👆 Enter a search term to find deals</h2>
        <p>Try searching for: laptop, iphone 14, macbook pro, nintendo switch, thinkpad</p>
        <p style="margin-top: 20px; font-size: 13px;">
            Sources: eBay auctions + PropertyRoom police auctions
        </p>
    </div>
    """
    return render_page(content=content)


@app.get("/search", response_class=HTMLResponse)
async def search(
    q: str = Query(..., min_length=2),
    min_profit: int = Query(30, ge=0),
    min_margin: int = Query(25, ge=0, le=100),
    ebay: int = Query(1),
    propertyroom: int = Query(1),
    username: str = Depends(verify_credentials)
):
    """Search for deals across sources"""
    
    all_items = []
    deals = []
    source_counts = {}
    
    # Search eBay
    if ebay:
        try:
            scraper = BrowserScraper()
            await scraper.start()
            ebay_items = await scraper.search_ebay(q, max_results=20)
            await scraper.stop()
            
            source_counts['ebay'] = len(ebay_items)
            
            for item in ebay_items:
                item.source = 'ebay'
                all_items.append(item)
                
                analysis = analyze_deal(
                    title=item.title,
                    auction_price=item.price,
                    shipping=item.shipping,
                    condition=item.condition
                )
                
                if analysis and analysis.profit >= min_profit and analysis.profit_margin_percent >= min_margin:
                    deals.append({'item': item, 'analysis': analysis, 'source': 'ebay'})
                    
        except Exception as e:
            print(f"eBay error: {e}")
            source_counts['ebay'] = 0
    
    # Search PropertyRoom
    if propertyroom:
        try:
            pr_scraper = PropertyRoomScraper()
            pr_items = await pr_scraper.search(q, max_results=20)
            
            source_counts['propertyroom'] = len(pr_items)
            
            for item in pr_items:
                all_items.append(item)
                
                analysis = analyze_deal(
                    title=item.title,
                    auction_price=item.price,
                    shipping=item.shipping,
                    condition="Pre-Owned"
                )
                
                if analysis and analysis.profit >= min_profit and analysis.profit_margin_percent >= min_margin:
                    deals.append({'item': item, 'analysis': analysis, 'source': 'propertyroom'})
                    
        except Exception as e:
            print(f"PropertyRoom error: {e}")
            source_counts['propertyroom'] = 0
    
    # Sort by margin
    deals.sort(key=lambda x: x['analysis'].profit_margin_percent, reverse=True)
    
    # Log search and mark deals as seen
    total_sources = ', '.join(source_counts.keys())
    log_search(q, total_sources, len(all_items), len(deals))
    
    # Mark profitable deals as seen
    for d in deals:
        mark_deal_seen(
            source=d['source'],
            item_url=d['item'].url,
            title=d['item'].title,
            price=d['item'].price,
            profit=d['analysis'].profit,
            margin=d['analysis'].profit_margin_percent
        )
    
    # Build stats
    great_count = len([d for d in deals if d['analysis'].is_great_deal])
    good_count = len([d for d in deals if d['analysis'].is_good_deal])
    
    stats_html = f"""
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(all_items)}</div>
            <div class="stat-label">Items Scanned</div>
        </div>
        <div class="stat">
            <div class="stat-value">{len(deals)}</div>
            <div class="stat-label">Profitable Deals</div>
        </div>
        <div class="stat">
            <div class="stat-value">{great_count}</div>
            <div class="stat-label">🔥 Great Deals</div>
        </div>
        <div class="stat">
            <div class="stat-value">{good_count}</div>
            <div class="stat-label">💰 Good Deals</div>
        </div>
    </div>
    """
    
    # Build source breakdown
    sources_html = "<p style='color: #888; font-size: 13px; margin-bottom: 20px;'>Sources: "
    sources_html += " • ".join([f"{k}: {v} items" for k, v in source_counts.items()])
    sources_html += "</p>"
    
    if not deals:
        content = stats_html + sources_html + """
        <div class="empty-state">
            <h2>No profitable deals found</h2>
            <p>Try lowering the minimum profit/margin or searching for something else.</p>
        </div>
        """
    else:
        cards = []
        for d in deals[:25]:
            item = d['item']
            a = d['analysis']
            
            cards.append(deal_card(
                source=d['source'],
                url=item.url,
                title=item.title[:80],
                profit=a.profit,
                price=item.price,
                shipping=item.shipping,
                time_left=item.time_left[:30] if item.time_left else "—",
                condition=item.condition[:25] if item.condition else "Unknown",
                margin=a.profit_margin_percent,
                is_great=a.is_great_deal,
                is_good=a.is_good_deal
            ))
        
        content = stats_html + sources_html + '<div class="deals">' + '\n'.join(cards) + '</div>'
    
    return render_page(
        query=q, 
        content=content,
        min_profit=min_profit,
        min_margin=min_margin,
        ebay=bool(ebay),
        propertyroom=bool(propertyroom)
    )


@app.get("/api/search")
async def api_search(
    q: str,
    max_results: int = 20,
    min_profit: float = 0,
    min_margin: float = 0,
    username: str = Depends(verify_credentials)
):
    """API endpoint for programmatic access"""
    
    results = []
    
    # Search both sources
    try:
        scraper = BrowserScraper()
        await scraper.start()
        ebay_items = await scraper.search_ebay(q, max_results)
        await scraper.stop()
        
        for item in ebay_items:
            analysis = analyze_deal(
                title=item.title,
                auction_price=item.price,
                shipping=item.shipping,
                condition=item.condition
            )
            
            result = {
                'source': 'ebay',
                'title': item.title,
                'price': item.price,
                'shipping': item.shipping,
                'condition': item.condition,
                'time_left': item.time_left,
                'url': item.url,
                'bids': item.bids
            }
            
            if analysis:
                result['profit'] = round(analysis.profit, 2)
                result['margin'] = round(analysis.profit_margin_percent, 1)
                result['estimated_retail'] = analysis.estimated_retail
                result['is_good_deal'] = analysis.is_good_deal
                result['is_great_deal'] = analysis.is_great_deal
            
            if analysis and analysis.profit >= min_profit and analysis.profit_margin_percent >= min_margin:
                results.append(result)
                
    except Exception as e:
        print(f"eBay API error: {e}")
    
    try:
        pr_scraper = PropertyRoomScraper()
        pr_items = await pr_scraper.search(q, max_results)
        
        for item in pr_items:
            analysis = analyze_deal(
                title=item.title,
                auction_price=item.price,
                shipping=item.shipping,
                condition="Pre-Owned"
            )
            
            result = {
                'source': 'propertyroom',
                'title': item.title,
                'price': item.price,
                'shipping': item.shipping,
                'condition': item.condition,
                'time_left': item.time_left,
                'url': item.url,
            }
            
            if analysis:
                result['profit'] = round(analysis.profit, 2)
                result['margin'] = round(analysis.profit_margin_percent, 1)
                result['estimated_retail'] = analysis.estimated_retail
                result['is_good_deal'] = analysis.is_good_deal
                result['is_great_deal'] = analysis.is_great_deal
            
            if analysis and analysis.profit >= min_profit and analysis.profit_margin_percent >= min_margin:
                results.append(result)
                
    except Exception as e:
        print(f"PropertyRoom API error: {e}")
    
    # Sort by profit
    results.sort(key=lambda x: x.get('profit', 0), reverse=True)
    
    return {
        'query': q,
        'total': len(results),
        'items': results
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "version": "2.0"}


@app.get("/api/stats")
async def api_stats(username: str = Depends(verify_credentials)):
    """Get database statistics"""
    stats = get_stats()
    recent = get_recent_searches(limit=5)
    return {
        "stats": stats,
        "recent_searches": recent
    }


@app.get("/api/history")
async def api_history(limit: int = 20, username: str = Depends(verify_credentials)):
    """Get search history"""
    return {"searches": get_recent_searches(limit=limit)}


@app.post("/api/save")
async def api_save_deal(
    url: str,
    title: str,
    source: str = "unknown",
    price: float = 0,
    profit: float = 0,
    margin: float = 0,
    username: str = Depends(verify_credentials)
):
    """Save a deal to favorites"""
    save_deal(source, url, title, price, profit, margin)
    return {"status": "saved", "url": url}


@app.get("/api/saved")
async def api_get_saved(username: str = Depends(verify_credentials)):
    """Get saved deals"""
    return {"deals": get_saved_deals()}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
