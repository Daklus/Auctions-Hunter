# Database module - uses native SQLite for simplicity
from .database import (
    init_db,
    get_connection,
    is_deal_seen,
    mark_deal_seen,
    get_unseen_deals,
    log_search,
    get_recent_searches,
    save_deal,
    get_saved_deals,
    remove_saved_deal,
    get_stats
)

__all__ = [
    'init_db',
    'get_connection', 
    'is_deal_seen',
    'mark_deal_seen',
    'get_unseen_deals',
    'log_search',
    'get_recent_searches',
    'save_deal',
    'get_saved_deals',
    'remove_saved_deal',
    'get_stats'
]
