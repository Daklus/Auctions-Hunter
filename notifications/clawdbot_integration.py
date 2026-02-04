"""
Clawdbot Integration for Telegram Notifications

This module integrates with Clawdbot's message tool to send
deal alerts to Daniel's personal Telegram.

Usage from Clawdbot session:
    from notifications.clawdbot_integration import send_deal_alert
    
    send_deal_alert(
        title="MacBook Pro",
        price=1200,
        profit=450,
        url="https://ebay.com/itm/..."
    )
"""

import os
from typing import Optional
from dataclasses import dataclass


# Daniel's personal Telegram ID
DANIEL_TELEGRAM_ID = "493895844"


@dataclass
class DealNotification:
    """A deal notification ready to send"""
    title: str
    price: float
    shipping: float
    profit: float
    margin_percent: float
    condition: str
    time_left: str
    url: str
    source: str = "eBay"
    
    def to_telegram_message(self) -> str:
        """Format as Telegram message with Markdown"""
        total_cost = self.price + self.shipping
        emoji = "🔥🔥🔥" if self.profit > 75 and self.margin_percent > 40 else "💰"
        
        return f"""{emoji} *Deal Alert from Auction Hunter!*

*{self.title}*

💵 Auction Price: ${self.price:.2f}
📦 Shipping: ${self.shipping:.2f}
💳 Total Cost: ${total_cost:.2f}
📈 Est. Profit: *${self.profit:.2f}* ({self.margin_percent:.0f}% margin)
🏷️ Condition: {self.condition}
⏰ Time Left: {self.time_left}
📍 Source: {self.source}

🔗 [View Auction]({self.url})"""


class ClawdbotNotifier:
    """
    Sends notifications through Clawdbot's message tool.
    
    This class formats messages for Telegram delivery.
    The actual sending happens via Clawdbot's message tool.
    """
    
    TARGET = DANIEL_TELEGRAM_ID  # Daniel's personal Telegram
    
    def __init__(self):
        self.sent_urls = set()
    
    def format_alert(self, 
                    title: str,
                    price: float,
                    shipping: float,
                    profit: float,
                    margin: float,
                    condition: str,
                    time_left: str,
                    url: str,
                    source: str = "eBay") -> str:
        """Format a deal alert message"""
        
        notification = DealNotification(
            title=title,
            price=price,
            shipping=shipping,
            profit=profit,
            margin_percent=margin,
            condition=condition,
            time_left=time_left,
            url=url,
            source=source
        )
        
        return notification.to_telegram_message()
    
    def format_summary(self, query: str, deals: list, total_scanned: int) -> str:
        """Format a summary of deals found"""
        
        if not deals:
            return f"🔍 *Auction Hunt: {query}*\n\nNo profitable deals found from {total_scanned} items scanned."
        
        great_deals = [d for d in deals if d.get('profit', 0) > 75]
        
        lines = [
            f"🎯 *Auction Hunter Results*",
            f"",
            f"Query: {query}",
            f"Items scanned: {total_scanned}",
            f"Profitable deals found: {len(deals)}",
            f"🔥 Great deals: {len(great_deals)}",
            f""
        ]
        
        for i, deal in enumerate(deals[:5], 1):
            profit = deal.get('profit', 0)
            margin = deal.get('margin_percent', 0)
            emoji = "🔥" if profit > 75 else "💰"
            title = deal.get('title', 'Unknown')[:40]
            
            lines.append(f"{emoji} *${profit:.0f}* ({margin:.0f}%) — {title}...")
        
        if len(deals) > 5:
            lines.append(f"\n_...and {len(deals) - 5} more deals_")
        
        return "\n".join(lines)
    
    def should_send(self, url: str) -> bool:
        """Check if we should send alert for this URL (deduplication)"""
        if url in self.sent_urls:
            return False
        self.sent_urls.add(url)
        return True


# Convenience function for quick alerts
def send_deal_alert(title: str, price: float, profit: float, url: str, **kwargs) -> str:
    """
    Create a formatted deal alert message.
    
    Returns the formatted message which can be sent via Clawdbot's message tool.
    
    Example:
        message = send_deal_alert(
            title="MacBook Pro",
            price=1200,
            profit=450,
            url="https://ebay.com/itm/123"
        )
        # Then use Clawdbot message tool to send
    """
    notifier = ClawdbotNotifier()
    
    return notifier.format_alert(
        title=title,
        price=price,
        shipping=kwargs.get('shipping', 0),
        profit=profit,
        margin=kwargs.get('margin', 30),
        condition=kwargs.get('condition', 'Unknown'),
        time_left=kwargs.get('time_left', 'Unknown'),
        url=url,
        source=kwargs.get('source', 'eBay')
    )


def send_summary_alert(query: str, deals: list, total_scanned: int) -> str:
    """
    Create a summary alert message.
    
    Returns formatted message for Clawdbot to send.
    """
    notifier = ClawdbotNotifier()
    return notifier.format_summary(query, deals, total_scanned)


# Test
if __name__ == "__main__":
    # Test formatting
    message = send_deal_alert(
        title="MacBook Pro 16 M3 Max 32GB RAM 1TB SSD - Excellent Condition",
        price=1200.00,
        shipping=25.00,
        profit=450.00,
        margin=35.0,
        condition="Used - Excellent",
        time_left="2 hours 15 min",
        url="https://www.ebay.com/itm/123456789"
    )
    
    print("Test message formatted:")
    print("=" * 60)
    print(message)
    print("=" * 60)
    print(f"\nTarget: Daniel's personal Telegram ({DANIEL_TELEGRAM_ID})")
