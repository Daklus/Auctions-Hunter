from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class ItemCondition(Enum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"
    SALVAGE = "salvage"
    PARTS_ONLY = "parts_only"
    UNKNOWN = "unknown"


@dataclass
class AuctionItem:
    """Represents an item from any auction site"""
    id: str
    title: str
    current_price: float
    source: str  # govdeals, ebay, liquidation
    url: str
    condition: ItemCondition
    end_time: Optional[str] = None
    image_url: Optional[str] = None
    location: Optional[str] = None
    shipping: Optional[float] = None
    retail_price: Optional[float] = None  # Estimated retail/market value
    profit_margin: Optional[float] = None  # Calculated potential profit
    
    def calculate_profit(self, market_price: float, fees_percent: float = 15) -> float:
        """Calculate potential profit after fees"""
        total_cost = self.current_price + (self.shipping or 0)
        fees = market_price * (fees_percent / 100)
        self.profit_margin = market_price - total_cost - fees
        return self.profit_margin
    
    def is_good_deal(self, min_profit: float = 50, min_margin_percent: float = 30) -> bool:
        """Check if this is worth buying"""
        if not self.retail_price or not self.profit_margin:
            return False
        margin_percent = (self.profit_margin / self.retail_price) * 100
        return self.profit_margin >= min_profit and margin_percent >= min_margin_percent


class BaseScraper(ABC):
    """Base class for all auction site scrapers"""
    
    def __init__(self):
        self.name = "base"
        self.base_url = ""
    
    @abstractmethod
    async def search(self, query: str, max_results: int = 50) -> List[AuctionItem]:
        """Search for items matching query"""
        pass
    
    @abstractmethod
    async def get_item(self, item_id: str) -> Optional[AuctionItem]:
        """Get details for a specific item"""
        pass
    
    def parse_condition(self, condition_str: str) -> ItemCondition:
        """Parse condition string to enum"""
        condition_lower = condition_str.lower()
        if 'new' in condition_lower:
            return ItemCondition.NEW
        elif 'refurb' in condition_lower:
            return ItemCondition.REFURBISHED
        elif 'salvage' in condition_lower:
            return ItemCondition.SALVAGE
        elif 'parts' in condition_lower:
            return ItemCondition.PARTS_ONLY
        elif 'used' in condition_lower:
            return ItemCondition.USED
        return ItemCondition.UNKNOWN
