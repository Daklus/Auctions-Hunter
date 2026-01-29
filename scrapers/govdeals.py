import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
from .base import BaseScraper, AuctionItem, ItemCondition
import re


class GovDealsScraper(BaseScraper):
    """Scraper for GovDeals.com - government surplus auctions"""
    
    def __init__(self):
        super().__init__()
        self.name = "govdeals"
        self.base_url = "https://www.govdeals.com"
        self.search_url = f"{self.base_url}/index.cfm"
    
    async def search(self, query: str, max_results: int = 50) -> List[AuctionItem]:
        """Search GovDeals for items"""
        items = []
        
        params = {
            'fa': 'Main.AdvSearchResultsNew',
            'searchPg': 'Main',
            'kession': 'keyword',
            'keywords': query,
            'rowCount': max_results,
            'sortOption': 'ad'  # Sort by date added
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.search_url, params=params, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Parse auction listings
                listings = soup.select('.ad-tile, .listing-item, [class*="auction"]')
                
                for listing in listings[:max_results]:
                    item = self._parse_listing(listing)
                    if item:
                        items.append(item)
                        
            except Exception as e:
                print(f"GovDeals search error: {e}")
        
        return items
    
    async def get_item(self, item_id: str) -> Optional[AuctionItem]:
        """Get specific item details from GovDeals"""
        url = f"{self.base_url}/index.cfm?fa=Main.Item&itemID={item_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                return self._parse_detail_page(soup, item_id, url)
            except Exception as e:
                print(f"GovDeals item fetch error: {e}")
                return None
    
    def _parse_listing(self, listing) -> Optional[AuctionItem]:
        """Parse a listing element into AuctionItem"""
        try:
            # Extract title
            title_elem = listing.select_one('a[href*="itemID"], .title, h3, h4')
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            
            # Extract URL and ID
            link = listing.select_one('a[href*="itemID"]')
            if link:
                url = link.get('href', '')
                if not url.startswith('http'):
                    url = f"{self.base_url}/{url}"
                # Extract item ID from URL
                match = re.search(r'itemID=(\d+)', url)
                item_id = match.group(1) if match else title[:20]
            else:
                return None
            
            # Extract price
            price_elem = listing.select_one('.price, [class*="price"], [class*="bid"]')
            price = 0.0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'[\$]?([\d,]+\.?\d*)', price_text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            # Extract condition
            condition_elem = listing.select_one('[class*="condition"], .condition')
            condition = ItemCondition.UNKNOWN
            if condition_elem:
                condition = self.parse_condition(condition_elem.get_text())
            
            # Extract image
            img_elem = listing.select_one('img')
            image_url = img_elem.get('src', '') if img_elem else None
            
            # Extract location
            location_elem = listing.select_one('[class*="location"], .location')
            location = location_elem.get_text(strip=True) if location_elem else None
            
            return AuctionItem(
                id=item_id,
                title=title,
                current_price=price,
                source=self.name,
                url=url,
                condition=condition,
                image_url=image_url,
                location=location
            )
        except Exception as e:
            print(f"Parse error: {e}")
            return None
    
    def _parse_detail_page(self, soup, item_id: str, url: str) -> Optional[AuctionItem]:
        """Parse item detail page"""
        try:
            title = soup.select_one('h1, .item-title')
            title = title.get_text(strip=True) if title else "Unknown Item"
            
            price_elem = soup.select_one('[class*="current-bid"], [class*="price"]')
            price = 0.0
            if price_elem:
                price_match = re.search(r'[\$]?([\d,]+\.?\d*)', price_elem.get_text())
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            return AuctionItem(
                id=item_id,
                title=title,
                current_price=price,
                source=self.name,
                url=url,
                condition=ItemCondition.UNKNOWN
            )
        except Exception as e:
            print(f"Detail parse error: {e}")
            return None
