# Auction Hunter 🎯

Find profitable auction deals on eBay and PropertyRoom. Scrapes listings, estimates retail value, and calculates profit potential.

## Features

- **eBay Scraping**: Playwright-based scraper that bypasses bot protection
- **PropertyRoom Scraping**: HTTP-based scraper for police/government surplus auctions
- **Price Estimation**: Heuristic retail price estimation for common products
- **Profit Analysis**: Calculate potential profit, ROI, and margin
- **Deal Alerts**: Telegram notifications for good deals
- **Web Dashboard**: FastAPI web interface for browsing deals
- **Duplicate Tracking**: SQLite database to avoid repeat alerts

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt
python -m playwright install chromium

# Run a hunt
python hunt.py "thinkpad" --min-profit 50

# Start web dashboard
python web/app.py
# Open http://localhost:8080
```

### Docker (Recommended)

```bash
# Build image
docker build -t auction-hunter .

# Run container
docker run -p 8080:8080 -e USERNAME=admin -e PASSWORD=secret auction-hunter

# Open http://localhost:8080
```

## Usage

### Command Line

```bash
# Search for deals
python hunt.py "macbook pro"
python hunt.py "iphone 14" --min-profit 100

# Send results to Telegram
python hunt.py "laptop" --telegram

# Direct scraper test
python scrapers/browser.py "laptop"
```

### Web Dashboard

```bash
# Start the web app
python web/app.py

# Access at http://localhost:8080
# Default credentials: hunter / deals2026
```

### Telegram Notifications

```bash
# Standalone script with notifications
python hunt_telegram.py "thinkpad" --notify-all
```

## Project Structure

```
auction-hunter/
├── hunt.py                    # Main deal hunting script
├── hunt_telegram.py          # Hunt with Telegram notifications
├── web/
│   └── app.py                # FastAPI web dashboard
├── scrapers/
│   ├── browser.py            # Playwright-based eBay scraper
│   ├── propertyroom.py       # HTTP-based PropertyRoom scraper
│   └── base.py               # Base scraper classes
├── utils/
│   └── price_checker.py      # Retail price estimation
├── notifications/
│   ├── telegram.py           # Telegram message formatting
│   └── clawdbot_integration.py  # Clawdbot integration
├── db/
│   └── models.py             # SQLAlchemy database models
├── Dockerfile                # Docker configuration
├── railway.json              # Railway deployment config
└── requirements.txt          # Python dependencies
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `USERNAME` | Web dashboard username | `hunter` |
| `PASSWORD` | Web dashboard password | `deals2026` |
| `DATABASE_URL` | SQLite database path | `sqlite:///auction_hunter.db` |
| `TELEGRAM_USER_ID` | Target Telegram user for notifications | `493895844` |

## Deployment

### Railway (Recommended)

One-click deploy with HTTPS built-in:

1. Fork this repo to your GitHub account
2. Connect Railway to your GitHub repo
3. Railway auto-detects the Dockerfile
4. HTTPS enabled automatically

See [DEPLOY.md](DEPLOY.md) for detailed instructions.

### Render

Alternative deployment platform:

1. Connect GitHub repo to Render
2. Render reads `render.yaml` configuration
3. Auto-deploy on every push

### Docker Compose

```yaml
version: '3.8'
services:
  auction-hunter:
    build: .
    ports:
      - "8080:8080"
    environment:
      - USERNAME=admin
      - PASSWORD=your_secure_password
      - DATABASE_URL=sqlite:///data/auction_hunter.db
    volumes:
      - ./data:/app/data
```

## How It Works

1. **Scrape**: Uses headless Chromium to fetch eBay auction listings
2. **Parse**: Extracts price, bids, time left, condition from each listing
3. **Analyze**: Estimates retail value based on product keywords
4. **Calculate**: Computes profit after shipping and platform fees
5. **Alert**: Formats good deals for Telegram notification
6. **Store**: Saves deals to SQLite database to avoid duplicates

## Deal Criteria

- **Good Deal**: >$30 profit AND >25% margin
- **Great Deal**: >$75 profit AND >40% margin

## Limitations

- Price estimates are heuristic (not real-time market data)
- eBay may rate-limit with heavy usage
- GovDeals and Liquidation.com blocked by bot protection

## Future Plans

- [ ] Real price API integration (Amazon, Google Shopping)
- [ ] GovDeals and Liquidation.com scrapers (with proxy support)
- [ ] Scheduled hunting with cron
- [ ] Web dashboard improvements
- [ ] Price history tracking

---

Built by Daklus ⚡
