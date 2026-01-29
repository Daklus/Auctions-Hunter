"""
Auction Hunter Web Dashboard

Simple FastAPI app to search and view deals.
Password protected for security.
"""

from fastapi import FastAPI, Request, Query, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import asyncio
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.browser import BrowserScraper
from utils.price_checker import analyze_deal

app = FastAPI(title="Auction Hunter", version="1.0")
security = HTTPBasic()

# Simple credentials - change these!
USERNAME = "hunter"
PASSWORD = "deals2026"


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


def get_html(query: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Auction Hunter 🎯</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        h1 {{ color: #00d9ff; }}
        .search-box {{
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }}
        input[type="text"] {{
            flex: 1;
            padding: 12px;
            font-size: 16px;
            border: 2px solid #333;
            border-radius: 8px;
            background: #16213e;
            color: #fff;
        }}
        input[type="text"]:focus {{
            border-color: #00d9ff;
            outline: none;
        }}
        button {{
            padding: 12px 24px;
            font-size: 16px;
            background: #00d9ff;
            color: #000;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
        }}
        button:hover {{ background: #00b4d8; }}
        .stats {{
            display: flex;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #16213e;
            padding: 15px 25px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #00d9ff; }}
        .stat-label {{ font-size: 12px; color: #888; }}
        .deals {{ display: grid; gap: 15px; }}
        .deal {{
            background: #16213e;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #333;
        }}
        .deal.great {{ border-left-color: #ff6b6b; }}
        .deal.good {{ border-left-color: #4ecdc4; }}
        .deal-title {{
            font-size: 16px;
            margin-bottom: 10px;
            color: #fff;
        }}
        .deal-title a {{ color: #00d9ff; text-decoration: none; }}
        .deal-title a:hover {{ text-decoration: underline; }}
        .deal-info {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            font-size: 14px;
            color: #aaa;
        }}
        .deal-profit {{
            font-size: 20px;
            font-weight: bold;
            color: #4ecdc4;
        }}
        .deal.great .deal-profit {{ color: #ff6b6b; }}
        .deal-time {{ color: #ffd93d; }}
        .no-deals {{
            text-align: center;
            padding: 40px;
            color: #888;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #333;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>🎯 Auction Hunter</h1>
    
    <form class="search-box" method="get" action="/search">
        <input type="text" name="q" placeholder="Search for deals (e.g., thinkpad, iphone 14)" 
               value="{query}" required>
        <button type="submit">🔍 Hunt Deals</button>
    </form>
    
    {content}
    
    <div class="footer">
        Built by Daklus ⚡
    </div>
</body>
</html>"""


def deal_card(url: str, title: str, profit: float, price: float, 
              shipping: float, time_left: str, condition: str, 
              margin: float, is_great: bool, is_good: bool) -> str:
    deal_class = "great" if is_great else "good" if is_good else ""
    return f"""<div class="deal {deal_class}">
    <div class="deal-title">
        <a href="{url}" target="_blank">{title}</a>
    </div>
    <div class="deal-info">
        <span class="deal-profit">${profit:.0f} profit</span>
        <span>💵 ${price:.2f} + ${shipping:.2f} ship</span>
        <span class="deal-time">⏰ {time_left}</span>
        <span>📦 {condition}</span>
        <span>📊 {margin:.0f}% margin</span>
    </div>
</div>"""


@app.get("/", response_class=HTMLResponse)
async def home(username: str = Depends(verify_credentials)):
    content = """
    <div class="no-deals">
        <h2>👆 Enter a search term above to find deals</h2>
        <p>Try: "laptop", "iphone 14", "macbook pro", "nintendo switch"</p>
    </div>
    """
    return get_html("", content)


@app.get("/search", response_class=HTMLResponse)
async def search(q: str = Query(...), username: str = Depends(verify_credentials)):
    scraper = BrowserScraper()
    
    try:
        await scraper.start()
        items = await scraper.search_ebay(q, max_results=25)
    finally:
        await scraper.stop()
    
    # Analyze deals
    deals = []
    for item in items:
        analysis = analyze_deal(
            title=item.title,
            auction_price=item.price,
            shipping=item.shipping,
            condition=item.condition
        )
        if analysis and analysis.profit > 0:
            deals.append({
                'item': item,
                'analysis': analysis
            })
    
    # Sort by profit
    deals.sort(key=lambda x: x['analysis'].profit, reverse=True)
    
    # Build stats
    great_deals = len([d for d in deals if d['analysis'].is_great_deal])
    good_deals = len([d for d in deals if d['analysis'].is_good_deal])
    
    stats_html = f"""
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(items)}</div>
            <div class="stat-label">Items Scanned</div>
        </div>
        <div class="stat">
            <div class="stat-value">{len(deals)}</div>
            <div class="stat-label">Profitable Deals</div>
        </div>
        <div class="stat">
            <div class="stat-value">{great_deals}</div>
            <div class="stat-label">🔥 Great Deals</div>
        </div>
        <div class="stat">
            <div class="stat-value">{good_deals}</div>
            <div class="stat-label">💰 Good Deals</div>
        </div>
    </div>
    """
    
    if not deals:
        content = stats_html + """
        <div class="no-deals">
            <h3>No profitable deals found</h3>
            <p>Try a different search term or check back later.</p>
        </div>
        """
    else:
        cards = []
        for d in deals[:20]:
            item = d['item']
            a = d['analysis']
            
            cards.append(deal_card(
                url=item.url,
                title=item.title[:80],
                profit=a.profit,
                price=item.price,
                shipping=item.shipping,
                time_left=item.time_left[:25] if item.time_left else "unknown",
                condition=item.condition[:25] if item.condition else "Unknown",
                margin=a.profit_margin_percent,
                is_great=a.is_great_deal,
                is_good=a.is_good_deal
            ))
        
        content = stats_html + '<div class="deals">' + ''.join(cards) + '</div>'
    
    return get_html(q, content)


@app.get("/api/search")
async def api_search(q: str, max_results: int = 20, username: str = Depends(verify_credentials)):
    """API endpoint for programmatic access"""
    scraper = BrowserScraper()
    
    try:
        await scraper.start()
        items = await scraper.search_ebay(q, max_results)
    finally:
        await scraper.stop()
    
    results = []
    for item in items:
        analysis = analyze_deal(
            title=item.title,
            auction_price=item.price,
            shipping=item.shipping,
            condition=item.condition
        )
        
        result = {
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
            result['is_good_deal'] = analysis.is_good_deal
            result['is_great_deal'] = analysis.is_great_deal
        
        results.append(result)
    
    return {
        'query': q,
        'total': len(results),
        'items': sorted(results, key=lambda x: x.get('profit', 0), reverse=True)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
