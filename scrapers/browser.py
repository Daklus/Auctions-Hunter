"""
Browser-based scraper using Playwright

Bypasses bot protection by using a real browser.
"""

import asyncio
from playwright.async_api import async_playwright, Page, Browser
from typing import List, Optional
from dataclasses import dataclass
import re


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
    source: str = "ebay"
    
    @property
    def total_cost(self) -> float:
        return self.price + self.shipping


class BrowserScraper:
    """Playwright-based scraper for auction sites"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright = None
    
    async def start(self):
        """Start the browser with stealth settings"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
            ]
        )
    
    async def stop(self):
        """Stop the browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def search_ebay(self, query: str, max_results: int = 20) -> List[AuctionItem]:
        """Search eBay auctions"""
        if not self.browser:
            await self.start()
        
        items = []
        
        # Create context with stealth settings
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )
        
        page = await context.new_page()
        
        # Add stealth scripts
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """)
        
        try:
            # Build search URL - auction only, ending soonest
            url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}&_sop=1&LH_Auction=1"
            
            # Navigate - use domcontentloaded for faster response
            await page.goto(url, wait_until='domcontentloaded', timeout=45000)
            await page.wait_for_timeout(5000)  # Wait for JS to render
            
            # Debug: Check page title
            title = await page.title()
            print(f"Page title: {title}")
            
            # Check if we got a challenge page
            if 'Pardon' in title or 'Checking' in title:
                print("Got challenge page, waiting...")
                await page.wait_for_timeout(10000)
                title = await page.title()
                print(f"After wait, title: {title}")
            
            # eBay 2024+ structure: .srp-results contains .s-card items
            # Each s-card has a link and text content
            selectors = [
                '.srp-results .s-card',  # Main results cards
                '.s-card.s-card--horizontal',  # Horizontal cards
                'div.s-card',  # Any card div
            ]
            listings = []
            
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    found = await page.query_selector_all(selector)
                    # Filter to cards with real item links
                    for card in found:
                        link = await card.query_selector('a[href*="www.ebay.com/itm/"]')
                        if link:
                            href = await link.get_attribute('href')
                            # Skip placeholder items
                            if href and '/123456' not in href:
                                listings.append(card)
                    if listings:
                        print(f"Found {len(listings)} item cards with selector: {selector}")
                        break
                except:
                    continue
            
            # Fallback: get cards by looking for item links
            if not listings:
                print("Trying fallback card extraction...")
                links = await page.query_selector_all('a.s-card__link[href*="www.ebay.com/itm/"]')
                seen = set()
                for link in links:
                    href = await link.get_attribute('href')
                    if '/123456' in href:
                        continue
                    item_id = href.split('/itm/')[1].split('?')[0] if href else None
                    if item_id and item_id not in seen:
                        seen.add(item_id)
                        # Get parent card
                        try:
                            card = await link.evaluate_handle('el => el.closest(".s-card") || el.closest("li") || el.parentElement.parentElement')
                            listings.append(card)
                        except:
                            pass
                print(f"Found {len(listings)} cards via fallback")
            
            parse_attempts = 0
            for listing in listings[:max_results]:
                try:
                    parse_attempts += 1
                    item = await self._parse_ebay_listing(listing)
                    if item:
                        if item.price > 0:
                            items.append(item)
                        elif parse_attempts <= 3:
                            print(f"Item {parse_attempts} has no price: {item.title[:50] if item.title else 'No title'}")
                    elif parse_attempts <= 3:
                        print(f"Item {parse_attempts} parsing returned None")
                except Exception as e:
                    if parse_attempts <= 3:
                        print(f"Parse error on item {parse_attempts}: {e}")
                    continue
            
            print(f"Successfully parsed {len(items)} items from {parse_attempts} attempts")
                    
        except Exception as e:
            print(f"eBay search error: {e}")
        finally:
            await page.close()
            await context.close()
        
        return items
    
    async def _parse_ebay_listing(self, listing) -> Optional[AuctionItem]:
        """Parse a single eBay listing card element"""
        try:
            # Get URL from link in card
            url = ""
            link = await listing.query_selector('a[href*="/itm/"]')
            if link:
                url = await link.get_attribute('href') or ""
            
            if not url or '/itm/' not in url:
                return None
            
            # Get full text content of the card
            card_text = await listing.inner_text()
            if not card_text or 'Shop on eBay' in card_text:
                return None
            
            # Parse the text content
            lines = [l.strip() for l in card_text.split('\n') if l.strip()]
            
            # First meaningful line is usually the title
            title = None
            for line in lines:
                if line and len(line) > 10 and 'Opens in' not in line:
                    title = line
                    break
            
            if not title:
                return None
            
            # Extract price from text - look for $XX.XX pattern
            price = 0.0
            for line in lines:
                match = re.search(r'^\$?([\d,]+\.?\d*)\s*$', line)
                if match:
                    try:
                        price = float(match.group(1).replace(',', ''))
                        if price > 0:
                            break
                    except:
                        pass
            
            # Extract bids
            bids = 0
            for line in lines:
                match = re.search(r'(\d+)\s*bids?', line, re.IGNORECASE)
                if match:
                    bids = int(match.group(1))
                    break
            
            # Extract time left
            time_left = "unknown"
            for line in lines:
                if 'left' in line.lower() and ('m ' in line or 'h ' in line or 'd ' in line):
                    time_left = line
                    break
            
            # Extract shipping
            shipping = 0.0
            for line in lines:
                if 'delivery' in line.lower() or 'shipping' in line.lower():
                    if 'free' in line.lower():
                        shipping = 0.0
                    else:
                        match = re.search(r'\$?([\d,]+\.?\d*)', line)
                        if match:
                            shipping = float(match.group(1).replace(',', ''))
                    break
            
            # Extract condition
            condition = "Unknown"
            for line in lines:
                line_lower = line.lower()
                if 'new' in line_lower or 'used' in line_lower or 'refurbished' in line_lower or 'pre-owned' in line_lower:
                    condition = line
                    break
            
            # Get image URL
            image_url = None
            try:
                elem = await listing.query_selector('img')
                if elem:
                    image_url = await elem.get_attribute('src')
            except:
                pass
            
            return AuctionItem(
                title=title[:200] if title else "",
                price=price,
                bids=bids,
                time_left=time_left,
                shipping=shipping,
                condition=condition,
                url=url,
                image_url=image_url,
                source="ebay"
            )
            
        except Exception as e:
            return None
    
    async def search_govdeals(self, query: str, max_results: int = 20) -> List[AuctionItem]:
        """Search GovDeals auctions"""
        if not self.browser:
            await self.start()
        
        items = []
        page = await self.browser.new_page()
        
        try:
            url = f"https://www.govdeals.com/index.cfm?fa=Main.AdvSearchResultsNew&searchPg=Main&kession=keyword&keywords={query.replace(' ', '+')}"
            
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)  # Extra wait for JS
            
            # GovDeals uses different selectors
            listings = await page.query_selector_all('[class*="auction"], .ad-tile, .listing')
            
            for listing in listings[:max_results]:
                try:
                    item = await self._parse_govdeals_listing(listing, page)
                    if item:
                        items.append(item)
                except:
                    continue
                    
        except Exception as e:
            print(f"GovDeals search error: {e}")
        finally:
            await page.close()
        
        return items
    
    async def _parse_govdeals_listing(self, listing, page) -> Optional[AuctionItem]:
        """Parse GovDeals listing - structure varies"""
        try:
            title_elem = await listing.query_selector('a, .title, h3, h4')
            if not title_elem:
                return None
            title = await title_elem.inner_text()
            
            link = await listing.query_selector('a[href*="itemID"]')
            url = ""
            if link:
                href = await link.get_attribute('href')
                url = f"https://www.govdeals.com/{href}" if not href.startswith('http') else href
            
            price_elem = await listing.query_selector('[class*="price"], [class*="bid"]')
            price = 0.0
            if price_elem:
                price_text = await price_elem.inner_text()
                match = re.search(r'\$?([\d,]+\.?\d*)', price_text)
                if match:
                    price = float(match.group(1).replace(',', ''))
            
            return AuctionItem(
                title=title.strip(),
                price=price,
                bids=0,
                time_left="check listing",
                shipping=0,
                condition="See listing",
                url=url,
                source="govdeals"
            )
        except:
            return None


async def search_all(query: str, max_per_site: int = 15) -> dict:
    """Search all auction sites"""
    scraper = BrowserScraper()
    
    try:
        await scraper.start()
        
        # Search in parallel
        ebay_task = scraper.search_ebay(query, max_per_site)
        govdeals_task = scraper.search_govdeals(query, max_per_site)
        
        ebay_items, govdeals_items = await asyncio.gather(
            ebay_task, govdeals_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(ebay_items, Exception):
            ebay_items = []
        if isinstance(govdeals_items, Exception):
            govdeals_items = []
        
        return {
            "query": query,
            "ebay": [vars(i) for i in ebay_items],
            "govdeals": [vars(i) for i in govdeals_items],
            "total": len(ebay_items) + len(govdeals_items)
        }
        
    finally:
        await scraper.stop()


def format_results(results: dict) -> str:
    """Format search results for display"""
    lines = [f"🔍 Search: {results['query']}", f"Found {results['total']} items\n"]
    
    if results.get('ebay'):
        lines.append("📦 eBay Auctions:")
        for i, item in enumerate(results['ebay'][:5], 1):
            lines.append(f"  {i}. ${item['price']:.2f} ({item['bids']} bids) - {item['time_left']}")
            lines.append(f"     {item['title'][:50]}...")
    
    if results.get('govdeals'):
        lines.append("\n🏛️ GovDeals:")
        for i, item in enumerate(results['govdeals'][:5], 1):
            lines.append(f"  {i}. ${item['price']:.2f} - {item['title'][:50]}...")
    
    return "\n".join(lines)


# CLI entry point
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python browser.py <search query>")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    print(f"Searching for: {query}")
    
    results = asyncio.run(search_all(query))
    print(format_results(results))
