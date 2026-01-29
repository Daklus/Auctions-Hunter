"""
eBay Parser - Parses markdown output from web_fetch

Since direct requests get blocked, this parses the markdown format
that web_fetch returns from eBay search results.
"""

import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class EbayListing:
    """Parsed eBay auction listing"""
    price: float
    bids: int
    time_left: str
    shipping: float
    seller: str
    seller_rating: str
    is_best_offer: bool = False
    
    @property
    def total_cost(self) -> float:
        return self.price + self.shipping
    
    def to_dict(self) -> dict:
        return {
            'price': self.price,
            'bids': self.bids,
            'time_left': self.time_left,
            'shipping': self.shipping,
            'total_cost': self.total_cost,
            'seller': self.seller,
            'seller_rating': self.seller_rating,
            'is_best_offer': self.is_best_offer
        }


def parse_ebay_markdown(text: str) -> List[EbayListing]:
    """
    Parse eBay search results from web_fetch markdown output.
    
    Format example:
    - $249.990 bids · Time left3m left (Today 05:32 PM)or Best Offer+$30.00 deliveryLocated in United Statespadola55 100% positive (823)
    """
    listings = []
    
    # Split by list items
    items = re.split(r'\n- ', text)
    
    for item in items:
        if not item.strip():
            continue
            
        try:
            listing = parse_single_listing(item)
            if listing:
                listings.append(listing)
        except Exception as e:
            continue
    
    return listings


def parse_single_listing(text: str) -> Optional[EbayListing]:
    """Parse a single listing line"""
    
    # eBay format: "$218.5027 bids" means $218.50 with 27 bids (concatenated)
    # Pattern: $PRICE + BIDS + " bids"
    price_bids_match = re.match(r'\$?([\d,]+\.\d{2})(\d+)\s*bids?\s*·', text.strip())
    
    if price_bids_match:
        price = float(price_bids_match.group(1).replace(',', ''))
        bids = int(price_bids_match.group(2))
    else:
        # Try simple price match for "0 bids" case: "$249.990 bids"
        simple_match = re.match(r'\$?([\d,]+\.\d{2})(\d*)\s*bids?\s*·', text.strip())
        if simple_match:
            price = float(simple_match.group(1).replace(',', ''))
            bids = int(simple_match.group(2)) if simple_match.group(2) else 0
        else:
            return None
    
    # Extract time left: "3m left" or "1h 30m left"
    time_match = re.search(r'Time left\s*([\dh\sm]+\s*left)', text, re.IGNORECASE)
    if not time_match:
        time_match = re.search(r'(\d+[hm]\s*(?:\d+[hm])?\s*left)', text, re.IGNORECASE)
    time_left = time_match.group(1).strip() if time_match else "unknown"
    
    # Extract shipping: "+$30.00 delivery" or "Free delivery"
    shipping = 0.0
    if 'free delivery' in text.lower() or 'free shipping' in text.lower():
        shipping = 0.0
    else:
        ship_match = re.search(r'\+\$?([\d,]+\.?\d*)\s*deliver', text, re.IGNORECASE)
        if ship_match:
            shipping = float(ship_match.group(1).replace(',', ''))
    
    # Extract seller and rating: "padola55 100% positive (823)"
    seller_match = re.search(r'States([a-zA-Z0-9_-]+)\s*(\d+\.?\d*%?\s*positive)', text)
    seller = seller_match.group(1) if seller_match else "unknown"
    seller_rating = seller_match.group(2) if seller_match else "unknown"
    
    # Check for Best Offer
    is_best_offer = 'best offer' in text.lower()
    
    return EbayListing(
        price=price,
        bids=bids,
        time_left=time_left,
        shipping=shipping,
        seller=seller,
        seller_rating=seller_rating,
        is_best_offer=is_best_offer
    )


def filter_good_deals(
    listings: List[EbayListing],
    max_price: float = 500,
    min_bids: int = 0,
    max_shipping: float = 50
) -> List[EbayListing]:
    """Filter listings for potential deals"""
    return [
        l for l in listings
        if l.price <= max_price
        and l.bids >= min_bids
        and l.shipping <= max_shipping
    ]


def summarize_listings(listings: List[EbayListing]) -> str:
    """Create a summary of listings"""
    if not listings:
        return "No listings found."
    
    lines = [f"Found {len(listings)} auctions:\n"]
    
    # Sort by price
    sorted_listings = sorted(listings, key=lambda x: x.price)
    
    for i, l in enumerate(sorted_listings[:10], 1):
        lines.append(
            f"{i}. ${l.price:.2f} ({l.bids} bids) - {l.time_left}"
        )
        if l.shipping > 0:
            lines[-1] += f" +${l.shipping:.2f} ship"
    
    if len(listings) > 10:
        lines.append(f"\n...and {len(listings) - 10} more")
    
    # Stats
    prices = [l.price for l in listings]
    lines.append(f"\nPrice range: ${min(prices):.2f} - ${max(prices):.2f}")
    lines.append(f"Average: ${sum(prices)/len(prices):.2f}")
    
    return "\n".join(lines)


# Example usage for testing
if __name__ == "__main__":
    sample = """
- $249.990 bids · Time left3m left (Today 05:32 PM)or Best Offer+$30.00 deliveryLocated in United Statespadola55 100% positive (823)
- $99.000 bids · Time left3m left (Today 05:33 PM)+$10.13 deliveryLocated in United StatesFree returnsvictoriousarmy 100% positive (839)
- $218.5027 bids · Time left5m left (Today 05:35 PM)+$10.00 delivery in 2-4 daysLocated in United Statestechredosurplus 99.7% positive (63K)
"""
    listings = parse_ebay_markdown(sample)
    print(summarize_listings(listings))
