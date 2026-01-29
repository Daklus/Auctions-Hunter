"""
Alert System - Send deal alerts via WhatsApp

This module formats and sends alerts. When run from Clawdbot,
the message tool handles actual delivery.
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class DealAlert:
    """A deal alert ready to send"""
    title: str
    auction_price: float
    shipping: float
    estimated_profit: float
    margin_percent: float
    condition: str
    time_left: str
    url: str
    source: str = "ebay"
    
    @property
    def total_cost(self) -> float:
        return self.auction_price + self.shipping
    
    @property
    def is_great(self) -> bool:
        return self.estimated_profit > 75 and self.margin_percent > 40
    
    def to_message(self) -> str:
        """Format as WhatsApp message"""
        emoji = "🔥" if self.is_great else "💰"
        
        return f"""{emoji} *Deal Alert!*

*{self.title[:80]}*

💵 Price: ${self.auction_price:.2f} + ${self.shipping:.2f} ship
💳 Total: ${self.total_cost:.2f}
📈 Est. Profit: *${self.estimated_profit:.2f}* ({self.margin_percent:.0f}%)
📦 Condition: {self.condition[:30]}
⏰ Ends: {self.time_left}

🔗 {self.url}"""
    
    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'price': self.auction_price,
            'shipping': self.shipping,
            'total_cost': self.total_cost,
            'profit': self.estimated_profit,
            'margin': self.margin_percent,
            'condition': self.condition,
            'time_left': self.time_left,
            'url': self.url,
            'source': self.source,
            'is_great': self.is_great
        }


def format_summary_alert(
    query: str,
    deals: List[DealAlert],
    total_scanned: int
) -> str:
    """Format a summary of deals found"""
    
    if not deals:
        return f"🔍 *{query}* - No profitable deals found from {total_scanned} items."
    
    great_deals = [d for d in deals if d.is_great]
    
    lines = [
        f"🎯 *Auction Hunt: {query}*",
        f"Found *{len(deals)}* deals ({len(great_deals)} great!) from {total_scanned} items",
        ""
    ]
    
    # Top 5 deals
    for deal in deals[:5]:
        emoji = "🔥" if deal.is_great else "💰"
        lines.append(
            f"{emoji} *${deal.estimated_profit:.0f}* profit"
            f" | ${deal.total_cost:.0f} → {deal.time_left[:15]}"
        )
        lines.append(f"   {deal.title[:45]}...")
    
    if len(deals) > 5:
        lines.append(f"\n_{len(deals) - 5} more deals not shown_")
    
    return "\n".join(lines)


def format_urgent_alert(deal: DealAlert) -> str:
    """Format urgent alert for time-sensitive deals"""
    
    return f"""⚡ *URGENT DEAL* ⚡

*{deal.title[:70]}*

💰 ${deal.total_cost:.2f} → *${deal.estimated_profit:.2f} profit*
⏰ {deal.time_left}

Quick! {deal.url}"""


class AlertTracker:
    """Track sent alerts to avoid duplicates"""
    
    def __init__(self, storage_path: str = "/tmp/auction_alerts.json"):
        self.storage_path = storage_path
        self.sent_alerts = self._load()
    
    def _load(self) -> dict:
        try:
            with open(self.storage_path) as f:
                return json.load(f)
        except:
            return {"items": {}, "last_summary": None}
    
    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump(self.sent_alerts, f)
    
    def should_alert(self, item_id: str) -> bool:
        """Check if we should send alert for this item"""
        return item_id not in self.sent_alerts.get("items", {})
    
    def mark_sent(self, item_id: str, deal: DealAlert):
        """Mark item as alerted"""
        if "items" not in self.sent_alerts:
            self.sent_alerts["items"] = {}
        
        self.sent_alerts["items"][item_id] = {
            "title": deal.title[:50],
            "profit": deal.estimated_profit,
            "sent_at": datetime.now().isoformat()
        }
        self._save()
    
    def get_stats(self) -> dict:
        """Get alert statistics"""
        items = self.sent_alerts.get("items", {})
        return {
            "total_sent": len(items),
            "total_profit": sum(i.get("profit", 0) for i in items.values())
        }


# For Daklus to call directly
def create_deal_alert(
    title: str,
    price: float,
    shipping: float,
    profit: float,
    margin: float,
    condition: str,
    time_left: str,
    url: str
) -> str:
    """Create a formatted deal alert message"""
    
    deal = DealAlert(
        title=title,
        auction_price=price,
        shipping=shipping,
        estimated_profit=profit,
        margin_percent=margin,
        condition=condition,
        time_left=time_left,
        url=url
    )
    
    return deal.to_message()
