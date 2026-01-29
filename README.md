# Auction Hunter 🎯

Find profitable auction deals on eBay. Scrapes listings, estimates retail value, and calculates profit potential.

## Features

- **eBay Scraping**: Playwright-based scraper that bypasses bot protection
- **Price Estimation**: Heuristic retail price estimation for common products
- **Profit Analysis**: Calculate potential profit, ROI, and margin
- **Deal Alerts**: WhatsApp-formatted alerts for good deals
- **Duplicate Tracking**: Avoid sending repeat alerts

## Quick Start

```bash
# Install dependencies
pip install playwright beautifulsoup4 httpx lxml
python -m playwright install chromium

# Run a hunt
python hunt.py "thinkpad" --min-profit 50
```

## Usage

### Command Line

```bash
# Search for deals
python hunt.py "macbook pro"
python hunt.py "iphone 14" --min-profit 100

# Direct scraper test
python scrapers/browser.py "laptop"
```

### From Daklus

Ask Daklus to:
- "Hunt for laptop deals"
- "Search eBay for iPhone deals and send me the good ones"
- "Find ThinkPad auctions under $200"

## Project Structure

```
auction-hunter/
├── hunt.py              # Main deal hunting script
├── scrapers/
│   ├── browser.py       # Playwright-based eBay scraper
│   └── ebay_parser.py   # Text parsing utilities
├── utils/
│   └── price_checker.py # Retail price estimation & profit analysis
├── notifications/
│   └── alerts.py        # WhatsApp alert formatting
└── db/
    └── models.py        # Database models (future)
```

## How It Works

1. **Scrape**: Uses headless Chromium to fetch eBay auction listings
2. **Parse**: Extracts price, bids, time left, condition from each listing
3. **Analyze**: Estimates retail value based on product keywords
4. **Calculate**: Computes profit after shipping and platform fees
5. **Alert**: Formats good deals for WhatsApp notification

## Deal Criteria

- **Good Deal**: >$30 profit AND >25% margin
- **Great Deal**: >$75 profit AND >40% margin

## Limitations

- Price estimates are heuristic (not real-time market data)
- eBay may rate-limit with heavy usage
- Currently eBay only (GovDeals/Liquidation need work)

## Future Plans

- [ ] Real price API integration (Amazon, Google Shopping)
- [ ] GovDeals and Liquidation.com scrapers
- [ ] Scheduled hunting with cron
- [ ] Web dashboard
- [ ] Database for tracking deals

---

Built by Daklus ⚡
