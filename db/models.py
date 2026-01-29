from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum
from sqlalchemy.orm import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class ConditionType(enum.Enum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"
    SALVAGE = "salvage"
    PARTS_ONLY = "parts_only"
    UNKNOWN = "unknown"


class AuctionItemDB(Base):
    """Tracked auction items"""
    __tablename__ = 'auction_items'
    
    id = Column(Integer, primary_key=True)
    external_id = Column(String, index=True)
    source = Column(String, index=True)  # govdeals, ebay, liquidation
    title = Column(String)
    current_price = Column(Float)
    retail_price = Column(Float, nullable=True)
    profit_margin = Column(Float, nullable=True)
    condition = Column(String)
    url = Column(String)
    image_url = Column(String, nullable=True)
    location = Column(String, nullable=True)
    shipping = Column(Float, nullable=True)
    end_time = Column(DateTime, nullable=True)
    
    # Tracking
    is_good_deal = Column(Boolean, default=False)
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchQuery(Base):
    """Saved search queries for monitoring"""
    __tablename__ = 'search_queries'
    
    id = Column(Integer, primary_key=True)
    query = Column(String)
    sources = Column(String)  # comma-separated: govdeals,ebay,liquidation
    min_profit = Column(Float, default=50)
    max_price = Column(Float, nullable=True)
    conditions = Column(String, nullable=True)  # comma-separated
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """Alert history"""
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer)
    message = Column(String)
    sent_to = Column(String)  # phone number
    sent_at = Column(DateTime, default=datetime.utcnow)
