"""
PropertyRoom.com Scraper

Police/government surplus auctions. HTTP-based, no browser needed.
Similar niche to GovDeals but without bot protection.
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
import re
from dataclasses import dataclass


@dataclass
class AuctionItem:
    """Scraped auction item"""
    title: str
    price: float
    bids: int
    time_left: str
    shipping: float
    condition: str
    url: str
    image_url: Optional[str] = None
    source: str = "propertyroom"
    
    @property
    def total_cost(self) -> float:
        return self.price + self.shipping


class PropertyRoomScraper:
    """HTTP-based scraper for PropertyRoom.com"""
    
    def __init__(self):
        self.base_url = "https://www.propertyroom.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    
    async def search(self, query: str, max_results: int = 20) -> List[AuctionItem]:
        """Search PropertyRoom for items"""
        items = []
        
        url = f"{self.base_url}/s/{query.replace(' ', '+')}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=30, follow_redirects=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find all listing containers
                listings = soup.select('.ListingContainer')
                print(f"PropertyRoom: Found {len(listings)} listing containers")
                
                for listing in listings[:max_results]:
                    try:
                        item = self._parse_listing(listing)
                        if item and item.title:
                            items.append(item)
                    except Exception as e:
                        continue
                
                print(f"PropertyRoom: Successfully parsed {len(items)} items")
                        
            except Exception as e:
                print(f"PropertyRoom search error: {e}")
        
        return items
    
    def _parse_listing(self, listing) -> Optional[AuctionItem]:
        """Parse a single PropertyRoom listing"""
        try:
            # Get listing ID
            lid = listing.get('lid', '')
            
            # Title and URL
            title_elem = listing.select_one('.product-name-category a')
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            href = title_elem.get('href', '')
            url = f"{self.base_url}{href}" if href.startswith('/') else href
            
            # Price
            price_elem = listing.select_one('[id*="uxPrice"]')
            price = 0.0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                match = re.search(r'\$\s*([\d,]+\.?\d*)', price_text)
                if match:
                    price = float(match.group(1).replace(',', ''))
            
            # Time left
            time_elem = listing.select_one('[id*="uxTimeLeft"]')
            time_left = "check listing"
            if time_elem:
                time_left = time_elem.get_text(strip=True)
            
            # Image
            img_elem = listing.select_one('img[id*="uxImage"]')
            image_url = None
            if img_elem:
                image_url = img_elem.get('src', '')
            
            # Condition - PropertyRoom is mostly police recovered items
            condition = "Police Auction - See listing"
            
            return AuctionItem(
                title=title[:200],
                price=price,
                bids=0,  # PropertyRoom doesn't show bid count in search
                time_left=time_left,
                shipping=0,  # Usually shown separately
                condition=condition,
                url=url,
                image_url=image_url,
                source="propertyroom"
            )
            
        except Exception as e:
            return None
    
    async def get_item_details(self, item_url: str) -> Optional[dict]:
        """Get detailed info for a specific item"""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(item_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                details = {
                    'description': '',
                    'condition_details': '',
                    'location': '',
                    'seller': '',
                }
                
                # Extract description
                desc_elem = soup.select_one('.listing-description, .product-description')
                if desc_elem:
                    details['description'] = desc_elem.get_text(strip=True)[:500]
                
                # Extract location
                loc_elem = soup.select_one('[class*="location"], [class*="seller-location"]')
                if loc_elem:
                    details['location'] = loc_elem.get_text(strip=True)
                
                return details
                
            except Exception as e:
                print(f"PropertyRoom item fetch error: {e}")
                return None


def format_results(items: List[AuctionItem]) -> str:
    """Format results for display"""
    if not items:
        return "No items found."
    
    lines = [f"🚔 PropertyRoom: Found {len(items)} items\n"]
    
    for i, item in enumerate(items[:10], 1):
        lines.append(f"{i}. ${item.price:.2f} - {item.time_left}")
        lines.append(f"   {item.title[:55]}...")
        lines.append(f"   {item.url}")
        lines.append("")
    
    return "\n".join(lines)


# CLI entry point
if __name__ == "__main__":
    import sys
    import asyncio
    
    if len(sys.argv) < 2:
        print("Usage: python propertyroom.py <search query>")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    print(f"Searching PropertyRoom for: {query}")
    
    scraper = PropertyRoomScraper()
    items = asyncio.run(scraper.search(query))
    print(format_results(items))
