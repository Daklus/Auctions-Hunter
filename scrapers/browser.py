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
        """
        Search GovDeals auctions.
        
        NOTE: GovDeals uses Akamai bot protection which blocks most automated access.
        This scraper may return 0 results unless using residential proxies.
        Consider manual searching or API access if available.
        """
        if not self.browser:
            await self.start()
        
        items = []
        
        # Create stealth context
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )
        page = await context.new_page()
        
        # Stealth scripts
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        
        try:
            # GovDeals new Angular site - use their search
            url = f"https://www.govdeals.com/search?q={query.replace(' ', '%20')}"
            print(f"Searching GovDeals: {url}")
            
            await page.goto(url, wait_until='domcontentloaded', timeout=45000)
            await page.wait_for_timeout(5000)  # Wait for Angular to render
            
            # Try to wait for search results to load
            try:
                await page.wait_for_selector('[class*="search-result"], [class*="auction-card"], [class*="item-card"], .card', timeout=10000)
            except:
                print("GovDeals: No search results selector found, trying alternative...")
            
            # GovDeals 2024 structure - cards with auction items
            selectors = [
                '.card.auction-card',
                '[class*="auction-card"]',
                '[class*="search-result"]',
                '.card[routerlink]',
                'a[href*="/asset/"]',
            ]
            
            listings = []
            for selector in selectors:
                try:
                    found = await page.query_selector_all(selector)
                    if found:
                        listings = found
                        print(f"GovDeals: Found {len(found)} items with selector: {selector}")
                        break
                except:
                    continue
            
            # Fallback: get all links that look like asset pages
            if not listings:
                print("GovDeals: Trying link-based extraction...")
                links = await page.query_selector_all('a[href*="/asset/"]')
                seen_urls = set()
                for link in links:
                    href = await link.get_attribute('href')
                    if href and href not in seen_urls:
                        seen_urls.add(href)
                        listings.append(link)
                print(f"GovDeals: Found {len(listings)} asset links")
            
            for listing in listings[:max_results]:
                try:
                    item = await self._parse_govdeals_listing(listing, page)
                    if item and item.title:
                        items.append(item)
                except Exception as e:
                    continue
            
            print(f"GovDeals: Successfully parsed {len(items)} items")
                    
        except Exception as e:
            print(f"GovDeals search error: {e}")
        finally:
            await page.close()
            await context.close()
        
        return items
    
    async def _parse_govdeals_listing(self, listing, page) -> Optional[AuctionItem]:
        """Parse GovDeals listing from Angular SPA"""
        try:
            # Get card text content
            card_text = await listing.inner_text()
            if not card_text or len(card_text) < 10:
                return None
            
            lines = [l.strip() for l in card_text.split('\n') if l.strip()]
            
            # First substantial line is usually title
            title = None
            for line in lines:
                if len(line) > 15 and not line.startswith('$'):
                    title = line
                    break
            
            if not title:
                title = lines[0] if lines else "Unknown"
            
            # Get URL
            url = ""
            link = await listing.query_selector('a[href*="/asset/"]')
            if not link:
                link = listing if await listing.get_attribute('href') else None
            if link:
                href = await link.get_attribute('href')
                if href:
                    url = f"https://www.govdeals.com{href}" if href.startswith('/') else href
            
            # Extract price - look for dollar amounts
            price = 0.0
            for line in lines:
                match = re.search(r'\$\s*([\d,]+\.?\d*)', line)
                if match:
                    try:
                        price = float(match.group(1).replace(',', ''))
                        break
                    except:
                        pass
            
            # Extract time remaining
            time_left = "check listing"
            for line in lines:
                if any(t in line.lower() for t in ['day', 'hour', 'min', 'end', 'closes']):
                    time_left = line[:50]
                    break
            
            # Extract location if available
            location = None
            for line in lines:
                if any(s in line for s in [', ', 'County', 'City', 'State']):
                    if not line.startswith('$') and len(line) < 60:
                        location = line
                        break
            
            return AuctionItem(
                title=title[:200],
                price=price,
                bids=0,
                time_left=time_left,
                shipping=0,  # GovDeals is usually local pickup
                condition="See listing",
                url=url,
                source="govdeals"
            )
        except Exception as e:
            return None


    async def search_liquidation(self, query: str, max_results: int = 20) -> List[AuctionItem]:
        """
        Search Liquidation.com.
        
        NOTE: Liquidation.com uses Akamai bot protection which blocks most automated access.
        This scraper may return 0 results unless using residential proxies.
        Consider manual searching or API access if available.
        """
        if not self.browser:
            await self.start()
        
        items = []
        
        # Create stealth context with extra protection
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )
        page = await context.new_page()
        
        # Advanced stealth scripts
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = { runtime: {} };
        """)
        
        try:
            # Navigate to homepage first to get cookies
            print("Liquidation.com: Loading homepage...")
            await page.goto("https://www.liquidation.com", wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Now search
            url = f"https://www.liquidation.com/aucSearch/index/search?q={query.replace(' ', '%20')}"
            print(f"Searching Liquidation.com: {url}")
            
            await page.goto(url, wait_until='domcontentloaded', timeout=45000)
            await page.wait_for_timeout(5000)
            
            # Check if we got blocked
            content = await page.content()
            if 'Access Denied' in content:
                print("Liquidation.com: Still blocked, trying alternative approach...")
                # Try using their main search box
                await page.goto("https://www.liquidation.com", wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(2000)
                
                # Look for search input
                search_input = await page.query_selector('input[type="search"], input[name="q"], #search')
                if search_input:
                    await search_input.fill(query)
                    await search_input.press('Enter')
                    await page.wait_for_timeout(5000)
            
            # Liquidation.com structure - auction cards
            selectors = [
                '.auction-tile',
                '.search-result-tile',
                '[class*="auction-card"]',
                '.lot-card',
                'a[href*="/auction/"]',
            ]
            
            listings = []
            for selector in selectors:
                try:
                    found = await page.query_selector_all(selector)
                    if found:
                        listings = found
                        print(f"Liquidation.com: Found {len(found)} items with selector: {selector}")
                        break
                except:
                    continue
            
            for listing in listings[:max_results]:
                try:
                    item = await self._parse_liquidation_listing(listing)
                    if item and item.title:
                        items.append(item)
                except Exception as e:
                    continue
            
            print(f"Liquidation.com: Successfully parsed {len(items)} items")
                    
        except Exception as e:
            print(f"Liquidation.com search error: {e}")
        finally:
            await page.close()
            await context.close()
        
        return items
    
    async def _parse_liquidation_listing(self, listing) -> Optional[AuctionItem]:
        """Parse Liquidation.com listing"""
        try:
            card_text = await listing.inner_text()
            if not card_text or len(card_text) < 10:
                return None
            
            lines = [l.strip() for l in card_text.split('\n') if l.strip()]
            
            # Title
            title = None
            for line in lines:
                if len(line) > 20 and not line.startswith('$') and not line.startswith('Bid'):
                    title = line
                    break
            
            if not title:
                title = lines[0] if lines else "Unknown Lot"
            
            # URL
            url = ""
            link = await listing.query_selector('a[href*="/auction/"]')
            if not link:
                href = await listing.get_attribute('href')
                if href and '/auction/' in href:
                    url = href if href.startswith('http') else f"https://www.liquidation.com{href}"
            else:
                href = await link.get_attribute('href')
                if href:
                    url = href if href.startswith('http') else f"https://www.liquidation.com{href}"
            
            # Price - current bid
            price = 0.0
            for line in lines:
                # Look for "Current Bid: $X" or just "$X"
                match = re.search(r'\$\s*([\d,]+\.?\d*)', line)
                if match:
                    try:
                        price = float(match.group(1).replace(',', ''))
                        break
                    except:
                        pass
            
            # Retail value / MSRP (Liquidation often shows this)
            retail_price = None
            for line in lines:
                if 'retail' in line.lower() or 'msrp' in line.lower():
                    match = re.search(r'\$\s*([\d,]+\.?\d*)', line)
                    if match:
                        try:
                            retail_price = float(match.group(1).replace(',', ''))
                        except:
                            pass
            
            # Time left
            time_left = "check listing"
            for line in lines:
                if any(t in line.lower() for t in ['day', 'hour', 'end', 'closes', 'left']):
                    time_left = line[:50]
                    break
            
            # Condition
            condition = "See manifest"
            for line in lines:
                line_lower = line.lower()
                if any(c in line_lower for c in ['new', 'refurb', 'used', 'salvage', 'customer return']):
                    condition = line[:50]
                    break
            
            return AuctionItem(
                title=title[:200],
                price=price,
                bids=0,
                time_left=time_left,
                shipping=0,  # Usually shows separately
                condition=condition,
                url=url,
                source="liquidation"
            )
        except Exception as e:
            return None


async def search_all(query: str, max_per_site: int = 15) -> dict:
    """Search all auction sites"""
    scraper = BrowserScraper()
    
    try:
        await scraper.start()
        
        # Search in parallel
        ebay_task = scraper.search_ebay(query, max_per_site)
        govdeals_task = scraper.search_govdeals(query, max_per_site)
        liquidation_task = scraper.search_liquidation(query, max_per_site)
        
        ebay_items, govdeals_items, liquidation_items = await asyncio.gather(
            ebay_task, govdeals_task, liquidation_task,
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(ebay_items, Exception):
            print(f"eBay error: {ebay_items}")
            ebay_items = []
        if isinstance(govdeals_items, Exception):
            print(f"GovDeals error: {govdeals_items}")
            govdeals_items = []
        if isinstance(liquidation_items, Exception):
            print(f"Liquidation.com error: {liquidation_items}")
            liquidation_items = []
        
        return {
            "query": query,
            "ebay": [vars(i) for i in ebay_items],
            "govdeals": [vars(i) for i in govdeals_items],
            "liquidation": [vars(i) for i in liquidation_items],
            "total": len(ebay_items) + len(govdeals_items) + len(liquidation_items)
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
    
    if results.get('liquidation'):
        lines.append("\n📦 Liquidation.com:")
        for i, item in enumerate(results['liquidation'][:5], 1):
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
