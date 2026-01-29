#!/usr/bin/env python3
"""Debug script to see what eBay HTML looks like"""

import asyncio
from playwright.async_api import async_playwright

async def debug():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox']
    )
    
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    
    page = await context.new_page()
    
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    
    url = "https://www.ebay.com/sch/i.html?_nkw=laptop&_sop=1&LH_Auction=1"
    await page.goto(url, wait_until='domcontentloaded', timeout=45000)
    await page.wait_for_timeout(5000)
    
    print(f"Title: {await page.title()}")
    
    # Take screenshot
    await page.screenshot(path='/tmp/ebay_debug.png')
    print("Screenshot saved to /tmp/ebay_debug.png")
    
    # Find s-card__link elements
    links = await page.query_selector_all('a.s-card__link')
    print(f"Found {len(links)} s-card__link elements")
    
    # Filter to real items (not placeholder 123456)
    real_links = []
    for link in links:
        href = await link.get_attribute('href')
        if href and 'www.ebay.com/itm/' in href and '/123456' not in href:
            real_links.append(link)
    
    print(f"Found {len(real_links)} real item links")
    
    # Examine first real item
    for i, link in enumerate(real_links[:3]):
        print(f"\n--- Real Item {i+1} ---")
        href = await link.get_attribute('href')
        print(f"href: {href[:80]}...")
        
        # Get outer HTML to see structure
        outer = await link.evaluate('el => el.outerHTML')
        print(f"outer HTML: {outer[:500]}")
        
        # Get all parent elements
        try:
            # Go up to find containing card
            ancestors = await link.evaluate('''el => {
                let path = [];
                let current = el.parentElement;
                for(let i=0; i<5 && current; i++) {
                    path.push(current.className);
                    current = current.parentElement;
                }
                return path;
            }''')
            print(f"ancestors: {ancestors}")
            
            # Get grandparent text
            gp = await link.evaluate_handle('el => el.parentElement.parentElement.parentElement')
            gp_text = await gp.inner_text()
            print(f"grandparent text:\n{gp_text[:500]}")
        except Exception as e:
            print(f"Error: {e}")
    
    await context.close()
    await browser.close()
    await playwright.stop()

asyncio.run(debug())
