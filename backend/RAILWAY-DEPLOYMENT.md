# Cluemore Backend - Railway Deployment Guide

## Why Railway?

Railway is recommended over Heroku for this project because:
- **Cost-effective**: More generous free tier and better pricing
- **Modern infrastructure**: Better performance and faster deployments  
- **Simpler setup**: Less configuration needed, automatic HTTPS
- **PostgreSQL included**: Free database included in starter plan
- **No sleep mode**: Apps don't go to sleep like Heroku's eco dynos
- **Better DX**: More intuitive dashboard and real-time logs

## Quick Deploy (Recommended)

### Option 1: One-Click Deploy
1. Fork this repository to your GitHub account
2. Go to [Railway](https://railway.app)
3. Click "Deploy from GitHub repo"
4. Select your forked repository
5. Railway will automatically detect it's a Python app
6. Add PostgreSQL service from the dashboard
7. Set environment variables (see below)
8. Deploy!

### Option 2: Railway CLI Deploy

1. **Install Railway CLI**
   ```bash
   # Via npm
   npm install -g @railway/cli
   
   # Via Homebrew (macOS)
   brew install railway
   
   # Or download from https://docs.railway.app/develop/cli
   ```

2. **Run the deployment script**
   ```bash
   cd backend
   ./deploy-railway.sh
   ```

3. **Follow the prompts** - the script will guide you through the entire process

## Manual Setup

If you prefer manual setup:

1. **Login to Railway**
   ```bash
   railway login
   ```

2. **Create new project**
   ```bash
   railway init cluemore-backend
   ```

3. **Add PostgreSQL**
   ```bash
   railway add postgresql
   ```

4. **Set environment variables** (see section below)

5. **Deploy**
   ```bash
   railway up
   ```

## Environment Variables

Set these in your Railway dashboard:

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `FLASK_ENV` | Flask environment | Yes | `production` |
| `DATABASE_URL` | PostgreSQL URL (auto-set by Railway) | Yes | Auto-generated |
| `GEMINI_API_KEY` | Google Gemini API key | Yes | `AIza...` |
| `OPENAI_API_KEY` | OpenAI API key | Yes | `sk-...` |
| `JWT_SECRET` | Secret for JWT tokens | Yes | Generate with `openssl rand -hex 32` |
| `FRONTEND_URL` | Your frontend URL for CORS | Yes | `https://yourapp.vercel.app` |

### Setting Environment Variables

**Via Railway Dashboard:**
1. Go to your project dashboard
2. Click on your service
3. Go to "Variables" tab
4. Add each variable

**Via CLI:**
```bash
railway variables set FLASK_ENV=production
railway variables set GEMINI_API_KEY=your_key_here
railway variables set OPENAI_API_KEY=your_key_here
railway variables set JWT_SECRET=$(openssl rand -hex 32)
railway variables set FRONTEND_URL=https://yourapp.vercel.app
```

## Database Setup

The database tables are automatically created when the app starts. Railway's PostgreSQL provides:
- **Starter Plan**: Free with 500MB storage
- **Developer Plan**: $5/month with 8GB storage
- **Team Plan**: $20/month with 32GB storage

## Custom Domain (Optional)

1. Go to your Railway project dashboard
2. Click on your service
3. Go to "Settings" tab
4. Click "Generate Domain" for a free `.railway.app` domain
5. Or add your custom domain in "Custom Domains"

## Monitoring & Debugging

### View Logs
```bash
# Real-time logs
railway logs

# Logs with follow
railway logs --follow

# Service-specific logs
railway logs --service backend
```

### Check Status
```bash
railway status
```

### Open Dashboard
```bash
railway open
```

### Connect to Database
```bash
railway connect postgresql
```

## Frontend Integration

Update your frontend to point to your Railway app:

```javascript
// For Railway-generated domain
const API_BASE_URL = 'https://your-app-name.railway.app';

// For custom domain
const API_BASE_URL = 'https://api.yourdomain.com';
```

## Cost Estimation

Railway pricing (as of 2024):
- **Starter**: $0/month (500MB storage, $5 usage credit)
- **Developer**: $20/month (includes $20 usage credit)
- **Team**: $100/month (includes $100 usage credit)

Typical usage for this app: ~$5-15/month depending on traffic.

## Scaling

Railway automatically scales based on usage:
- **CPU**: Auto-scales based on demand
- **Memory**: 512MB default, can increase up to 8GB
- **Storage**: Starts at 1GB, can increase as needed

To manually adjust resources:
1. Go to service settings
2. Adjust "Resources" section
3. Set CPU and memory limits

## Troubleshooting

### Common Issues

1. **App won't start**
   ```bash
   railway logs
   ```
   - Check all environment variables are set
   - Verify PostgreSQL service is running
   - Check Python version compatibility

2. **Database connection errors**
   - Verify PostgreSQL service is attached
   - Check `DATABASE_URL` is automatically set
   - Test connection: `railway connect postgresql`

3. **CORS errors**
   - Verify `FRONTEND_URL` matches your frontend domain exactly
   - Check `FLASK_ENV=production` is set
   - Ensure no trailing slashes in URLs

4. **API key errors**
   - Verify `GEMINI_API_KEY` and `OPENAI_API_KEY` are set
   - Test keys work locally first
   - Check for any extra spaces or characters

### Useful Commands

```bash
# View all environment variables
railway variables

# Restart service
railway redeploy

# View service info
railway status

# Open project dashboard
railway open

# View usage and billing
railway usage

# Connect to database
railway connect postgresql

# View deployment history
railway deployments
```

## Security Best Practices

- ✅ All secrets stored as environment variables
- ✅ PostgreSQL with SSL enabled by default
- ✅ CORS properly configured for production
- ✅ JWT tokens for authentication
- ✅ HTTPS enforced by Railway

## Migration from Other Platforms

### From Heroku
1. Export your environment variables from Heroku
2. Set them in Railway dashboard
3. Your PostgreSQL data can be migrated using `pg_dump` and `pg_restore`
4. Update DNS records to point to Railway

### From Vercel/Netlify
1. Railway is better suited for backend APIs than Vercel Functions
2. Move your API routes to this Flask/FastAPI backend
3. Keep your frontend on Vercel/Netlify if preferred

## Support

For issues:
1. Check Railway logs first: `railway logs`
2. Review this deployment guide
3. Check [Railway documentation](https://docs.railway.app)
4. Join [Railway Discord](https://discord.gg/railway) for community support
5. Open an issue in this repository

## Next Steps After Deployment

1. **Test all endpoints** using your Railway URL
2. **Update frontend** to use new backend URL
3. **Set up monitoring** (Railway provides built-in metrics)
4. **Configure custom domain** if needed
5. **Set up CI/CD** with GitHub Actions (optional)

Your backend should now be live at: `https://your-app-name.railway.app`
