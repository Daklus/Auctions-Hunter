# Deploy to Railway

Step-by-step guide to deploy Auction Hunter on Railway with automatic HTTPS.

## Prerequisites

- GitHub account
- Railway account (sign up at [railway.app](https://railway.app))
- This repository forked to your GitHub account

## Deployment Steps

### 1. Fork the Repository

1. Go to https://github.com/Daklus/Auctions-Hunter
2. Click **"Fork"** button (top right)
3. Select your personal GitHub account
4. Wait for fork to complete

### 2. Create Railway Project

1. Go to [railway.app/dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your forked `Auctions-Hunter` repository
5. Click **"Add Variables"** (we'll configure these in step 4)

### 3. Configure Environment Variables

In Railway dashboard → your project → **Variables** tab, add:

| Variable | Value | Description |
|----------|-------|-------------|
| `USERNAME` | `your_username` | Web dashboard login |
| `PASSWORD` | `your_password` | Web dashboard password |
| `DATABASE_URL` | `sqlite:///data/auction_hunter.db` | Database file path |

**Important:** Change the default credentials for security!

### 4. Deploy

Railway automatically detects the `railway.json` and `Dockerfile`:

1. Click **"Deploy"** (or it auto-deploys on push)
2. Wait for build to complete (2-3 minutes)
3. Railway runs healthcheck at `/health`
4. Once green, click the **domain URL** (e.g., `auction-hunter.up.railway.app`)

### 5. Access Your App

```
URL: https://your-app-name.up.railway.app
Username: (what you set in USERNAME variable)
Password: (what you set in PASSWORD variable)
```

## Updating Your Deployment

Any push to your GitHub repo automatically redeploys:

```bash
# Make changes locally
git add .
git commit -m "Update features"
git push origin main

# Railway auto-deploys in ~2 minutes
```

## Troubleshooting

### Build Fails

Check Railway logs for errors. Common issues:
- Missing environment variables
- Playwright browser download timeout (retry the deploy)

### App Won't Start

1. Check the **Deploy Logs** in Railway
2. Verify `DATABASE_URL` format is correct
3. Ensure healthcheck passes at `/health`

### HTTPS Not Working

Railway provides HTTPS automatically. If you see HTTP:
1. Check domain settings in Railway dashboard
2. Ensure you're using the `.up.railway.app` URL

## Cost

| Tier | Cost | Features |
|------|------|----------|
| **Starter** | $5/mo | 512 MB RAM, always on |
| **Developer** | Free | 512 MB RAM, sleeps after inactivity |

Free tier is sufficient for testing. Upgrade to Starter for production.

## Alternative: Docker Local Build

Test locally before deploying:

```bash
# Build
docker build -t auction-hunter .

# Run with env vars
docker run -p 8080:8080 \
  -e USERNAME=admin \
  -e PASSWORD=secret \
  -e DATABASE_URL=sqlite:///data/auction_hunter.db \
  -v $(pwd)/data:/app/data \
  auction-hunter

# Access at http://localhost:8080
```

## Support

- Railway Docs: https://docs.railway.app
- Project Issues: https://github.com/Daklus/Auctions-Hunter/issues
