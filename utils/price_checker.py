"""
Price Checker - Compare auction prices with retail values

Uses web scraping to estimate retail prices and calculate profit potential.
"""

import re
import asyncio
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class PriceEstimate:
    """Retail price estimate from various sources"""
    query: str
    estimated_retail: Optional[float] = None
    source: str = "unknown"
    confidence: str = "low"  # low, medium, high
    
    def __post_init__(self):
        if self.estimated_retail and self.estimated_retail > 0:
            self.confidence = "medium"


@dataclass
class ProfitAnalysis:
    """Profit potential analysis for an auction item"""
    auction_price: float
    shipping_cost: float
    estimated_retail: float
    condition_modifier: float  # 1.0 = new, 0.7 = refurb, 0.5 = used, 0.3 = parts
    platform_fee_percent: float = 13.0  # eBay ~13%, Amazon ~15%
    
    @property
    def total_cost(self) -> float:
        return self.auction_price + self.shipping_cost
    
    @property
    def expected_sell_price(self) -> float:
        return self.estimated_retail * self.condition_modifier
    
    @property
    def platform_fees(self) -> float:
        return self.expected_sell_price * (self.platform_fee_percent / 100)
    
    @property
    def profit(self) -> float:
        return self.expected_sell_price - self.total_cost - self.platform_fees
    
    @property
    def profit_margin_percent(self) -> float:
        if self.expected_sell_price <= 0:
            return 0
        return (self.profit / self.expected_sell_price) * 100
    
    @property
    def roi_percent(self) -> float:
        if self.total_cost <= 0:
            return 0
        return (self.profit / self.total_cost) * 100
    
    @property
    def is_good_deal(self) -> bool:
        """A good deal has >$30 profit and >25% margin"""
        return self.profit > 30 and self.profit_margin_percent > 25
    
    @property
    def is_great_deal(self) -> bool:
        """A great deal has >$75 profit and >40% margin"""
        return self.profit > 75 and self.profit_margin_percent > 40
    
    def to_dict(self) -> dict:
        return {
            'auction_price': round(self.auction_price, 2),
            'shipping': round(self.shipping_cost, 2),
            'total_cost': round(self.total_cost, 2),
            'estimated_retail': round(self.estimated_retail, 2),
            'condition_modifier': self.condition_modifier,
            'expected_sell_price': round(self.expected_sell_price, 2),
            'platform_fees': round(self.platform_fees, 2),
            'profit': round(self.profit, 2),
            'margin_percent': round(self.profit_margin_percent, 1),
            'roi_percent': round(self.roi_percent, 1),
            'is_good_deal': self.is_good_deal,
            'is_great_deal': self.is_great_deal
        }
    
    def summary(self) -> str:
        emoji = "🔥" if self.is_great_deal else "💰" if self.is_good_deal else "📊"
        return (
            f"{emoji} Cost: ${self.total_cost:.2f} → "
            f"Sell: ${self.expected_sell_price:.2f} → "
            f"Profit: ${self.profit:.2f} ({self.profit_margin_percent:.0f}%)"
        )


def get_condition_modifier(condition: str) -> float:
    """Convert condition string to price modifier"""
    condition_lower = condition.lower()
    
    if 'new' in condition_lower and 'pre' not in condition_lower:
        return 1.0
    elif 'refurbished' in condition_lower or 'renewed' in condition_lower:
        if 'excellent' in condition_lower:
            return 0.85
        elif 'good' in condition_lower:
            return 0.75
        return 0.80
    elif 'pre-owned' in condition_lower or 'used' in condition_lower:
        if 'like new' in condition_lower:
            return 0.85
        elif 'good' in condition_lower:
            return 0.70
        elif 'acceptable' in condition_lower:
            return 0.55
        return 0.65
    elif 'salvage' in condition_lower:
        return 0.35
    elif 'parts' in condition_lower or 'not working' in condition_lower:
        return 0.25
    
    return 0.70  # Default for unknown


def extract_product_keywords(title: str) -> str:
    """Extract key product identifiers from title for price lookup"""
    # Remove common auction noise words
    noise = [
        'lot of', 'bundle', 'as is', 'for parts', 'not working',
        'read description', 'see photos', 'local pickup', 'no reserve',
        'free shipping', 'fast shipping', 'tested', 'working',
        'lot', 'qty', 'quantity', 'untested'
    ]
    
    cleaned = title.lower()
    for word in noise:
        cleaned = cleaned.replace(word, ' ')
    
    # Extract model numbers (alphanumeric patterns)
    models = re.findall(r'\b[A-Z0-9]+-?[A-Z0-9]+\b', title, re.IGNORECASE)
    
    # Get first few meaningful words
    words = [w for w in cleaned.split() if len(w) > 2][:6]
    
    # Combine with model numbers
    keywords = ' '.join(words[:4])
    if models:
        keywords += ' ' + models[0]
    
    return keywords.strip()


def estimate_retail_from_title(title: str) -> Optional[float]:
    """
    Rough retail price estimation based on product keywords.
    This is a simple heuristic - real implementation would use price APIs.
    """
    title_lower = title.lower()
    
    # Skip accessories and non-valuable items
    skip_keywords = ['cable', 'lock', 'bag', 'backpack', 'charger', 'adapter', 
                     'case', 'sleeve', 'stand', 'mount', 'holder', 'strap',
                     'cleaning', 'kit', 'cover', 'skin', 'protector', 'lot of']
    if any(kw in title_lower for kw in skip_keywords):
        # These are accessories, not the main item
        if not any(main in title_lower for main in ['macbook', 'thinkpad', 'iphone', 'ipad', 'galaxy']):
            return None
    
    # Laptops - detect by brand/model names too
    laptop_keywords = ['laptop', 'notebook', 'macbook', 'thinkpad', 'latitude', 
                       'chromebook', 'elitebook', 'probook', 'ideapad', 'pavilion',
                       'inspiron', 'xps', 'surface pro', 'surface laptop']
    is_laptop = any(kw in title_lower for kw in laptop_keywords)
    
    if is_laptop:
        if 'macbook pro' in title_lower:
            if '16' in title_lower or 'm3' in title_lower or 'm2' in title_lower:
                return 2000
            return 1200
        elif 'macbook air' in title_lower:
            return 900
        elif 'thinkpad' in title_lower:
            if 'x1' in title_lower:
                return 1200
            return 600
        elif 'dell latitude' in title_lower:
            return 500
        elif 'chromebook' in title_lower:
            return 200
        elif 'gaming' in title_lower or 'predator' in title_lower or 'rog' in title_lower:
            return 1000
        return 400
    
    # Phones
    if 'iphone' in title_lower:
        if '15 pro' in title_lower:
            return 1000
        elif '15' in title_lower:
            return 800
        elif '14 pro' in title_lower:
            return 800
        elif '14' in title_lower:
            return 600
        elif '13' in title_lower:
            return 500
        elif '12' in title_lower:
            return 400
        return 350
    
    if 'galaxy' in title_lower or 'samsung' in title_lower:
        if 's24' in title_lower or 's23' in title_lower:
            return 700
        elif 's22' in title_lower or 's21' in title_lower:
            return 500
        return 300
    
    # Tablets
    if 'ipad' in title_lower:
        if 'pro' in title_lower:
            return 800
        elif 'air' in title_lower:
            return 500
        return 350
    
    # Gaming
    if 'playstation' in title_lower or 'ps5' in title_lower:
        return 450
    if 'xbox' in title_lower:
        if 'series x' in title_lower:
            return 450
        return 300
    if 'nintendo switch' in title_lower:
        if 'oled' in title_lower:
            return 350
        return 250
    
    # Default
    return None


def analyze_deal(
    title: str,
    auction_price: float,
    shipping: float = 0,
    condition: str = "Unknown"
) -> Optional[ProfitAnalysis]:
    """Analyze if an auction item is a good deal"""
    
    # Estimate retail price
    retail = estimate_retail_from_title(title)
    if not retail:
        return None
    
    # Get condition modifier
    modifier = get_condition_modifier(condition)
    
    # Create analysis
    return ProfitAnalysis(
        auction_price=auction_price,
        shipping_cost=shipping,
        estimated_retail=retail,
        condition_modifier=modifier
    )


def format_deal_alert(
    title: str,
    analysis: ProfitAnalysis,
    url: str,
    time_left: str = "unknown"
) -> str:
    """Format a deal as a WhatsApp message"""
    
    if analysis.is_great_deal:
        emoji = "🔥🔥🔥"
        header = "GREAT DEAL!"
    elif analysis.is_good_deal:
        emoji = "💰"
        header = "Good Deal Found"
    else:
        emoji = "📊"
        header = "Deal Analysis"
    
    return f"""{emoji} *{header}*

*{title[:80]}*

💵 Auction: ${analysis.auction_price:.2f}
📦 Shipping: ${analysis.shipping_cost:.2f}
💳 Total Cost: ${analysis.total_cost:.2f}

🏷️ Est. Retail: ${analysis.estimated_retail:.2f}
📈 Profit: *${analysis.profit:.2f}* ({analysis.profit_margin_percent:.0f}% margin)
⏰ Time Left: {time_left}

🔗 {url}"""


# Test
if __name__ == "__main__":
    # Test cases
    tests = [
        ("Dell Latitude 7490 i7-8650U 16GB", 150, 15, "Pre-Owned"),
        ("MacBook Pro 16 M3 Pro", 1200, 0, "Excellent - Refurbished"),
        ("iPhone 14 Pro 128GB", 400, 10, "Used - Good"),
        ("Nintendo Switch OLED", 180, 12, "New"),
        ("Lot of 5 Chromebooks for parts", 50, 20, "For parts"),
    ]
    
    print("Deal Analysis Tests\n" + "="*50)
    
    for title, price, ship, cond in tests:
        analysis = analyze_deal(title, price, ship, cond)
        if analysis:
            print(f"\n{title}")
            print(f"  Condition: {cond}")
            print(f"  {analysis.summary()}")
            print(f"  Good deal: {analysis.is_good_deal}, Great deal: {analysis.is_great_deal}")
