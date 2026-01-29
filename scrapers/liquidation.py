import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
from .base import BaseScraper, AuctionItem, ItemCondition
import re


class LiquidationScraper(BaseScraper):
    """Scraper for Liquidation.com"""
    
    def __init__(self):
        super().__init__()
        self.name = "liquidation"
        self.base_url = "https://www.liquidation.com"
    
    async def search(self, query: str, max_results: int = 50) -> List[AuctionItem]:
        """Search Liquidation.com for items"""
        items = []
        
        search_url = f"{self.base_url}/aucSearch/index/search"
        
        params = {
            'q': query,
            'rows': max_results,
            'sort': 'timeleft asc'  # Ending soonest
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(search_url, params=params, headers=headers, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                
                listings = soup.select('.auction-item, .search-result-item, [class*="listing"]')
                
                for listing in listings[:max_results]:
                    item = self._parse_listing(listing)
                    if item:
                        items.append(item)
                        
            except Exception as e:
                print(f"Liquidation.com search error: {e}")
        
        return items
    
    async def get_item(self, item_id: str) -> Optional[AuctionItem]:
        """Get specific item details"""
        url = f"{self.base_url}/auction/{item_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                return self._parse_detail_page(soup, item_id, url)
            except Exception as e:
                print(f"Liquidation.com item fetch error: {e}")
                return None
    
    def _parse_listing(self, listing) -> Optional[AuctionItem]:
        """Parse listing element"""
        try:
            # Title
            title_elem = listing.select_one('a[href*="auction"], .title, h3, h4')
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            
            # URL and ID
            link = listing.select_one('a[href*="auction"]')
            if link:
                url = link.get('href', '')
                if not url.startswith('http'):
                    url = f"{self.base_url}{url}"
                match = re.search(r'/auction/(\d+)', url)
                item_id = match.group(1) if match else title[:20]
            else:
                return None
            
            # Price
            price_elem = listing.select_one('[class*="price"], [class*="bid"]')
            price = 0.0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'[\$]?([\d,]+\.?\d*)', price_text)
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            # Condition - Liquidation uses manifests with condition info
            condition_elem = listing.select_one('[class*="condition"], .manifest-condition')
            condition = ItemCondition.UNKNOWN
            if condition_elem:
                condition = self.parse_condition(condition_elem.get_text())
            
            # Retail value (Liquidation often shows MSRP)
            retail_elem = listing.select_one('[class*="retail"], [class*="msrp"]')
            retail_price = None
            if retail_elem:
                retail_match = re.search(r'[\$]?([\d,]+\.?\d*)', retail_elem.get_text())
                if retail_match:
                    retail_price = float(retail_match.group(1).replace(',', ''))
            
            # Image
            img_elem = listing.select_one('img')
            image_url = img_elem.get('src', '') if img_elem else None
            
            # Location
            location_elem = listing.select_one('[class*="location"]')
            location = location_elem.get_text(strip=True) if location_elem else None
            
            return AuctionItem(
                id=item_id,
                title=title,
                current_price=price,
                source=self.name,
                url=url,
                condition=condition,
                image_url=image_url,
                location=location,
                retail_price=retail_price
            )
        except Exception as e:
            print(f"Liquidation parse error: {e}")
            return None
    
    def _parse_detail_page(self, soup, item_id: str, url: str) -> Optional[AuctionItem]:
        """Parse detail page"""
        try:
            title = soup.select_one('h1, .auction-title')
            title = title.get_text(strip=True) if title else "Unknown Item"
            
            price_elem = soup.select_one('[class*="current-bid"], [class*="price"]')
            price = 0.0
            if price_elem:
                price_match = re.search(r'[\$]?([\d,]+\.?\d*)', price_elem.get_text())
                if price_match:
                    price = float(price_match.group(1).replace(',', ''))
            
            # Manifest/condition details
            condition_elem = soup.select_one('[class*="condition"]')
            condition = ItemCondition.UNKNOWN
            if condition_elem:
                condition = self.parse_condition(condition_elem.get_text())
            
            # Retail/MSRP
            retail_elem = soup.select_one('[class*="retail"], [class*="msrp"]')
            retail_price = None
            if retail_elem:
                retail_match = re.search(r'[\$]?([\d,]+\.?\d*)', retail_elem.get_text())
                if retail_match:
                    retail_price = float(retail_match.group(1).replace(',', ''))
            
            return AuctionItem(
                id=item_id,
                title=title,
                current_price=price,
                source=self.name,
                url=url,
                condition=condition,
                retail_price=retail_price
            )
        except Exception as e:
            print(f"Liquidation detail parse error: {e}")
            return None
