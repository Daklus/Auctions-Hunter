from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from scrapers import GovDealsScraper, EbayScraper, LiquidationScraper
from scrapers.base import AuctionItem
from utils.price_checker import PriceChecker

app = FastAPI(
    title="Auction Hunter",
    description="Find profitable auction deals",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize scrapers
scrapers = {
    'govdeals': GovDealsScraper(),
    'ebay': EbayScraper(),
    'liquidation': LiquidationScraper()
}
price_checker = PriceChecker()


class SearchRequest(BaseModel):
    query: str
    sources: List[str] = ['govdeals', 'ebay', 'liquidation']
    max_results: int = 20
    check_prices: bool = True
    min_profit: float = 50


class SearchResult(BaseModel):
    items: List[dict]
    total: int
    good_deals: int


@app.get("/")
async def root():
    return {"status": "running", "app": "Auction Hunter"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/search", response_model=SearchResult)
async def search_auctions(request: SearchRequest):
    """Search multiple auction sites"""
    all_items = []
    
    # Run scrapers in parallel
    tasks = []
    for source in request.sources:
        if source in scrapers:
            tasks.append(scrapers[source].search(request.query, request.max_results))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, list):
            all_items.extend(result)
    
    # Check prices and calculate profits if requested
    if request.check_prices and all_items:
        price_result = await price_checker.check_price(request.query)
        retail_estimate = price_result.get_best_estimate()
        
        if retail_estimate:
            for item in all_items:
                item.retail_price = retail_estimate
                item.calculate_profit(retail_estimate)
    
    # Convert to dicts and count good deals
    items_dict = []
    good_deals = 0
    
    for item in all_items:
        item_data = {
            'id': item.id,
            'title': item.title,
            'price': item.current_price,
            'retail_price': item.retail_price,
            'profit': item.profit_margin,
            'condition': item.condition.value,
            'source': item.source,
            'url': item.url,
            'image': item.image_url,
            'end_time': item.end_time,
            'is_good_deal': item.is_good_deal(request.min_profit)
        }
        items_dict.append(item_data)
        if item_data['is_good_deal']:
            good_deals += 1
    
    # Sort by profit potential
    items_dict.sort(key=lambda x: x.get('profit') or 0, reverse=True)
    
    return SearchResult(
        items=items_dict,
        total=len(items_dict),
        good_deals=good_deals
    )


@app.get("/item/{source}/{item_id}")
async def get_item(source: str, item_id: str):
    """Get details for a specific item"""
    if source not in scrapers:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
    
    item = await scrapers[source].get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Check retail price
    price_result = await price_checker.check_price(item.title)
    retail_estimate = price_result.get_best_estimate()
    
    if retail_estimate:
        item.retail_price = retail_estimate
        profit_info = price_checker.calculate_profit_potential(
            item.current_price,
            retail_estimate,
            item.shipping or 0
        )
    else:
        profit_info = None
    
    return {
        'item': {
            'id': item.id,
            'title': item.title,
            'price': item.current_price,
            'condition': item.condition.value,
            'source': item.source,
            'url': item.url,
            'image': item.image_url,
            'shipping': item.shipping,
            'end_time': item.end_time
        },
        'retail_estimate': retail_estimate,
        'profit_analysis': profit_info
    }


@app.get("/check-price")
async def check_price(query: str):
    """Check retail price for an item"""
    result = await price_checker.check_price(query)
    return {
        'query': query,
        'amazon_price': result.amazon_price,
        'google_price': result.google_price,
        'best_estimate': result.get_best_estimate()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
