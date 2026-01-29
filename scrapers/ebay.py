import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
from .base import BaseScraper, AuctionItem, ItemCondition
import re
import subprocess
import json


class EbayScraper(BaseScraper):
    """Scraper for eBay auctions - uses curl for better success rate"""
    
    def __init__(self):
        super().__init__()
        self.name = "ebay"
        self.base_url = "https://www.ebay.com"
    
    async def search(self, query: str, max_results: int = 50, auction_only: bool = True) -> List[AuctionItem]:
        """Search eBay for auction items"""
        items = []
        
        # Build URL
        params = f"_nkw={query.replace(' ', '+')}&_sop=1&LH_Auction=1&_ipg={min(max_results, 100)}"
        url = f"{self.base_url}/sch/i.html?{params}"
        
        # Use curl for better success (mimics browser)
        try:
            result = subprocess.run(
                ['curl', '-s', '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', url],
                capture_output=True,
                text=True,
                timeout=30
            )
            html = result.stdout
            soup = BeautifulSoup(html, 'lxml')
            
            # Parse listings
            listings = soup.select('.s-item')
            
            for listing in listings[:max_results]:
                item = self._parse_listing(listing)
                if item:
                    items.append(item)
                    
        except Exception as e:
            print(f"eBay search error: {e}")
        
        return items
    
    async def get_item(self, item_id: str) -> Optional[AuctionItem]:
        """Get specific eBay item details"""
        url = f"{self.base_url}/itm/{item_id}"
        
        try:
            result = subprocess.run(
                ['curl', '-s', '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', url],
                capture_output=True,
                text=True,
                timeout=30
            )
            soup = BeautifulSoup(result.stdout, 'lxml')
            return self._parse_detail_page(soup, item_id, url)
        except Exception as e:
            print(f"eBay item fetch error: {e}")
            return None
    
    def _parse_listing(self, listing) -> Optional[AuctionItem]:
        """Parse eBay listing element"""
        try:
            # Skip promotional items
            text = listing.get_text()
            if 'Shop on eBay' in text or not text.strip():
                return None
            
            # Title
            title_elem = listing.select_one('.s-item__title')
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            if not title or title == 'Shop on eBay':
                return None
            
            # URL and ID
            link = listing.select_one('a.s-item__link')
            if not link:
                return None
            url = link.get('href', '')
            
            # Extract item ID
            match = re.search(r'/itm/(\d+)', url)
            item_id = match.group(1) if match else None
            if not item_id:
                match = re.search(r'itm=(\d+)', url)
                item_id = match.group(1) if match else str(hash(title))[:12]
            
            # Price
            price_elem = listing.select_one('.s-item__price')
            price = 0.0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'[\$]?([\d,]+\.?\d*)', price_text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            # Condition
            condition_elem = listing.select_one('.SECONDARY_INFO')
            condition = ItemCondition.UNKNOWN
            if condition_elem:
                condition = self.parse_condition(condition_elem.get_text())
            
            # Image
            img_elem = listing.select_one('img.s-item__image-img')
            image_url = img_elem.get('src', '') if img_elem else None
            
            # Shipping
            shipping_elem = listing.select_one('.s-item__shipping, .s-item__freeXDays')
            shipping = 0.0
            if shipping_elem:
                shipping_text = shipping_elem.get_text(strip=True).lower()
                if 'free' in shipping_text:
                    shipping = 0.0
                else:
                    ship_match = re.search(r'[\$]?([\d,]+\.?\d*)', shipping_text)
                    if ship_match:
                        shipping = float(ship_match.group(1).replace(',', ''))
            
            # Time left
            time_elem = listing.select_one('.s-item__time-left')
            end_time = time_elem.get_text(strip=True) if time_elem else None
            
            # Bids
            bids_elem = listing.select_one('.s-item__bids')
            bids = 0
            if bids_elem:
                bids_match = re.search(r'(\d+)', bids_elem.get_text())
                if bids_match:
                    bids = int(bids_match.group(1))
            
            return AuctionItem(
                id=item_id,
                title=title,
                current_price=price,
                source=self.name,
                url=url,
                condition=condition,
                image_url=image_url,
                shipping=shipping,
                end_time=end_time
            )
        except Exception as e:
            print(f"eBay parse error: {e}")
            return None
    
    def _parse_detail_page(self, soup, item_id: str, url: str) -> Optional[AuctionItem]:
        """Parse eBay item detail page"""
        try:
            title = soup.select_one('h1.x-item-title__mainTitle, h1[itemprop="name"]')
            title = title.get_text(strip=True) if title else "Unknown Item"
            
            price_elem = soup.select_one('.x-price-primary, [itemprop="price"]')
            price = 0.0
            if price_elem:
                price_match = re.search(r'[\$]?([\d,]+\.?\d*)', price_elem.get_text())
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            condition_elem = soup.select_one('[class*="condition"], [itemprop="itemCondition"]')
            condition = ItemCondition.UNKNOWN
            if condition_elem:
                condition = self.parse_condition(condition_elem.get_text())
            
            return AuctionItem(
                id=item_id,
                title=title,
                current_price=price,
                source=self.name,
                url=url,
                condition=condition
            )
        except Exception as e:
            print(f"eBay detail parse error: {e}")
            return None


# Standalone function for quick searches
def search_ebay_sync(query: str, max_results: int = 20) -> List[dict]:
    """Synchronous eBay search for CLI usage"""
    import asyncio
    scraper = EbayScraper()
    items = asyncio.run(scraper.search(query, max_results))
    return [
        {
            'id': item.id,
            'title': item.title,
            'price': item.current_price,
            'condition': item.condition.value,
            'shipping': item.shipping,
            'end_time': item.end_time,
            'url': item.url
        }
        for item in items
    ]
