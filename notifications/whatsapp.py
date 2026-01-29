"""
WhatsApp notifications via Clawdbot

This module integrates with Clawdbot's message system to send
deal alerts via WhatsApp.

Usage (from Clawdbot):
    When good deals are found, Daklus can send alerts directly
    using the message tool.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass 
class DealAlert:
    """A deal alert to send"""
    title: str
    price: float
    retail_price: float
    profit: float
    condition: str
    source: str
    url: str
    
    def format_message(self) -> str:
        """Format as WhatsApp message"""
        emoji = "🔥" if self.profit > 100 else "💰"
        condition_emoji = {
            'new': '✨',
            'refurbished': '🔧',
            'used': '📦',
            'salvage': '⚠️',
            'parts_only': '🔩'
        }.get(self.condition, '❓')
        
        return f"""{emoji} *Deal Found!*

*{self.title[:100]}*

💵 Auction: ${self.price:.2f}
🏷️ Retail: ${self.retail_price:.2f}
📈 Profit: ${self.profit:.2f}
{condition_emoji} Condition: {self.condition.title()}
📍 Source: {self.source.title()}

🔗 {self.url}"""


def format_deal_summary(deals: List[DealAlert]) -> str:
    """Format multiple deals as summary"""
    if not deals:
        return "No good deals found."
    
    lines = [f"🎯 *Found {len(deals)} Good Deals!*\n"]
    
    for i, deal in enumerate(deals[:5], 1):  # Top 5
        lines.append(
            f"{i}. *{deal.title[:50]}...*\n"
            f"   ${deal.price:.0f} → ${deal.profit:.0f} profit ({deal.condition})\n"
        )
    
    if len(deals) > 5:
        lines.append(f"\n...and {len(deals) - 5} more deals")
    
    return "\n".join(lines)
