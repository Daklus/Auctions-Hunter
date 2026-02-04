"""
SQLite Database for Auction Hunter

Tracks:
- Seen deals (avoid duplicate alerts)
- Search history
- Saved/favorited deals
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from contextlib import contextmanager

# Database path - use /app/data in Docker, local otherwise
DB_PATH = os.getenv("DATABASE_PATH", "data/auction_hunter.db")


def get_db_path():
    """Get database path, creating directory if needed"""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize database tables"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Seen deals - track items we've already processed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                item_url TEXT UNIQUE NOT NULL,
                title TEXT,
                price REAL,
                profit REAL,
                margin REAL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notified INTEGER DEFAULT 0
            )
        """)
        
        # Search history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                source TEXT,
                results_count INTEGER,
                deals_found INTEGER,
                searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Saved/favorited deals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                item_url TEXT UNIQUE NOT NULL,
                title TEXT,
                price REAL,
                profit REAL,
                margin REAL,
                notes TEXT,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_url ON seen_deals(item_url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_source ON seen_deals(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_searches_query ON searches(query)")


@dataclass
class SeenDeal:
    """A deal we've seen before"""
    id: int
    source: str
    item_url: str
    title: str
    price: float
    profit: float
    margin: float
    first_seen: datetime
    last_seen: datetime
    notified: bool


def is_deal_seen(item_url: str) -> bool:
    """Check if we've seen this deal before"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM seen_deals WHERE item_url = ?", (item_url,))
        return cursor.fetchone() is not None


def mark_deal_seen(source: str, item_url: str, title: str = None, 
                   price: float = None, profit: float = None, 
                   margin: float = None, notified: bool = False):
    """Mark a deal as seen (or update if exists)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO seen_deals (source, item_url, title, price, profit, margin, notified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_url) DO UPDATE SET
                last_seen = CURRENT_TIMESTAMP,
                price = COALESCE(excluded.price, price),
                profit = COALESCE(excluded.profit, profit),
                margin = COALESCE(excluded.margin, margin),
                notified = CASE WHEN excluded.notified = 1 THEN 1 ELSE notified END
        """, (source, item_url, title, price, profit, margin, int(notified)))


def get_unseen_deals(item_urls: List[str]) -> List[str]:
    """Filter to only unseen deals"""
    if not item_urls:
        return []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(item_urls))
        cursor.execute(f"""
            SELECT item_url FROM seen_deals 
            WHERE item_url IN ({placeholders})
        """, item_urls)
        seen = {row['item_url'] for row in cursor.fetchall()}
    
    return [url for url in item_urls if url not in seen]


def log_search(query: str, source: str = None, results_count: int = 0, deals_found: int = 0):
    """Log a search to history"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO searches (query, source, results_count, deals_found)
            VALUES (?, ?, ?, ?)
        """, (query, source, results_count, deals_found))


def get_recent_searches(limit: int = 20) -> List[dict]:
    """Get recent search history"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT query, source, results_count, deals_found, searched_at
            FROM searches
            ORDER BY searched_at DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def save_deal(source: str, item_url: str, title: str, price: float, 
              profit: float, margin: float, notes: str = None):
    """Save a deal to favorites"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO saved_deals 
            (source, item_url, title, price, profit, margin, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (source, item_url, title, price, profit, margin, notes))


def get_saved_deals() -> List[dict]:
    """Get all saved deals"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM saved_deals ORDER BY saved_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


def remove_saved_deal(item_url: str):
    """Remove a deal from favorites"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM saved_deals WHERE item_url = ?", (item_url,))


def get_stats() -> dict:
    """Get database statistics"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM seen_deals")
        total_seen = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM seen_deals WHERE notified = 1")
        total_notified = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM searches")
        total_searches = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM saved_deals")
        total_saved = cursor.fetchone()[0]
        
        return {
            'total_deals_seen': total_seen,
            'total_notified': total_notified,
            'total_searches': total_searches,
            'total_saved': total_saved
        }


# Initialize database on import
init_db()
