"""
Telegram notifications for Auction Hunter

Sends deal alerts directly to Daniel's Telegram (personal, not group).
"""

import os
import asyncio
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class TelegramDealAlert:
    """A deal alert formatted for Telegram"""
    title: str
    auction_price: float
    shipping: float
    estimated_profit: float
    margin_percent: float
    condition: str
    time_left: str
    url: str
    source: str = "ebay"
    image_url: Optional[str] = None
    
    @property
    def total_cost(self) -> float:
        return self.auction_price + self.shipping
    
    @property
    def is_great(self) -> bool:
        return self.estimated_profit > 75 and self.margin_percent > 40
    
    def to_message(self) -> str:
        """Format as Telegram message with Markdown"""
        emoji = "🔥🔥🔥" if self.is_great else "💰"
        urgency = "⚡ URGENT: " if "hour" in self.time_left.lower() or "min" in self.time_left.lower() else ""
        
        return f"""{emoji} {urgency}*Auction Deal Found!*

*{self.title[:80]}*

💵 *Auction:* ${self.auction_price:.2f}
📦 *Shipping:* ${self.shipping:.2f}
💳 *Total Cost:* ${self.total_cost:.2f}
📈 *Est. Profit:* ${self.estimated_profit:.2f} ({self.margin_percent:.0f}% margin)
🏷️ *Condition:* {self.condition}
⏰ *Time Left:* {self.time_left}
📍 *Source:* {self.source}

🔗 [View Auction]({self.url})"""


class TelegramNotifier:
    """Send deal alerts to Telegram via Clawdbot message tool"""
    
    # Daniel's personal Telegram ID
    TARGET_USER = "493895844"
    
    def __init__(self, channel: str = "telegram"):
        self.channel = channel
        self.sent_deals = set()
    
    def _get_item_id(self, url: str) -> str:
        """Extract unique item ID from URL"""
        try:
            if '/itm/' in url:
                return url.split('/itm/')[1].split('?')[0]
            return url
        except:
            return url
    
    def should_notify(self, url: str) -> bool:
        """Check if we already sent this deal"""
        item_id = self._get_item_id(url)
        return item_id not in self.sent_deals
    
    def mark_sent(self, url: str):
        """Mark deal as sent"""
        item_id = self._get_item_id(url)
        self.sent_deals.add(item_id)
    
    def format_deal_message(self, 
                          title: str,
                          price: float,
                          shipping: float,
                          profit: float,
                          margin: float,
                          condition: str,
                          time_left: str,
                          url: str,
                          source: str = "ebay",
                          image_url: Optional[str] = None) -> str:
        """Format a single deal alert"""
        
        alert = TelegramDealAlert(
            title=title,
            auction_price=price,
            shipping=shipping,
            estimated_profit=profit,
            margin_percent=margin,
            condition=condition,
            time_left=time_left,
            url=url,
            source=source,
            image_url=image_url
        )
        
        return alert.to_message()
    
    def format_summary(self, query: str, deals: List[dict], total_scanned: int) -> str:
        """Format a summary of multiple deals"""
        
        if not deals:
            return f"🔍 *Auction Hunt: {query}*\n\nNo profitable deals found from {total_scanned} items scanned."
        
        great_deals = [d for d in deals if d.get('profit', 0) > 75]
        
        lines = [
            f"🎯 *Auction Hunt Results: {query}*",
            f"",
            f"Found *{len(deals)}* profitable deals from {total_scanned} items",
            f"🔥 Great deals: {len(great_deals)}",
            f""
        ]
        
        for i, deal in enumerate(deals[:5], 1):
            profit = deal.get('profit', 0)
            margin = deal.get('margin', 0)
            emoji = "🔥" if profit > 75 and margin > 40 else "💰"
            
            lines.append(
                f"{emoji} *${profit:.0f}* profit ({margin:.0f}%) — {deal.get('title', 'Unknown')[:40]}..."
            )
        
        if len(deals) > 5:
            lines.append(f"\n_...and {len(deals) - 5} more deals_")
        
        return "\n".join(lines)


# Quick test function
def test_notification():
    """Test the notification formatting"""
    notifier = TelegramNotifier()
    
    message = notifier.format_deal_message(
        title="MacBook Pro 16 M3 Max 32GB RAM 1TB SSD",
        price=1200.00,
        shipping=25.00,
        profit=450.00,
        margin=35.0,
        condition="Used - Excellent",
        time_left="2 hours 15 min",
        url="https://www.ebay.com/itm/123456789",
        source="eBay"
    )
    
    print(message)
    return message


if __name__ == "__main__":
    test_notification()
