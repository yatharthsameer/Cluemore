# Cluemore Backend - Heroku Deployment Guide

## Prerequisites

1. **Heroku CLI** - Install from [heroku.com](https://devcenter.heroku.com/articles/heroku-cli)
2. **Git** - Ensure your code is in a git repository
3. **API Keys** - Have your Gemini and OpenAI API keys ready

## Quick Deploy

### Option 1: One-Click Deploy (Recommended)

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/yourusername/cluemore)

1. Click the "Deploy to Heroku" button above
2. Enter your app name
3. Set your API keys in the config vars
4. Click "Deploy app"

### Option 2: Manual Deploy

1. **Login to Heroku**
   ```bash
   heroku login
   ```

2. **Create Heroku App**
   ```bash
   heroku create your-app-name
   ```

3. **Add PostgreSQL Add-on**
   ```bash
   heroku addons:create heroku-postgresql:essential-0
   ```

4. **Set Environment Variables**
   ```bash
   heroku config:set FLASK_ENV=production
   heroku config:set GEMINI_API_KEY=your_gemini_api_key_here
   heroku config:set OPENAI_API_KEY=your_openai_api_key_here
   heroku config:set JWT_SECRET=$(openssl rand -hex 32)
   heroku config:set FRONTEND_URL=https://your-app-name.herokuapp.com
   ```

5. **Deploy**
   ```bash
   git add .
   git commit -m "Prepare for production deployment"
   git push heroku main
   ```

## Environment Variables

Set these in your Heroku app dashboard or via CLI:

| Variable | Description | Required |
|----------|-------------|----------|
| `FLASK_ENV` | Set to "production" | Yes |
| `DATABASE_URL` | PostgreSQL connection URL (auto-set by Heroku) | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `JWT_SECRET` | Secret for JWT tokens | Yes |
| `FRONTEND_URL` | Your frontend URL for CORS | Yes |

## Database Setup

The database tables are automatically created when the app starts. The PostgreSQL add-on provides:

- **Development**: `heroku-postgresql:essential-0` (Free, 10K rows)
- **Production**: `heroku-postgresql:standard-0` (Paid, 10M rows)

## Monitoring

- **Logs**: `heroku logs --tail`
- **Database**: `heroku pg:info`
- **App Status**: `heroku ps`

## Local Development

1. **Setup local environment**
   ```bash
   cp env.example .env
   # Edit .env with your values
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run locally**
   ```bash
   python server.py
   ```

## Frontend Integration

Update your frontend to point to your Heroku app:

```javascript
const API_BASE_URL = 'https://your-app-name.herokuapp.com';
```

## Security Considerations

- ✅ JWT tokens for authentication
- ✅ CORS restricted to frontend domain
- ✅ PostgreSQL with SSL required
- ✅ Environment variables for secrets
- ✅ Production-ready gunicorn server

## Troubleshooting

### Common Issues

1. **App won't start**
   - Check logs: `heroku logs --tail`
   - Verify all environment variables are set
   - Ensure PostgreSQL add-on is attached

2. **Database connection errors**
   - Verify `DATABASE_URL` is set
   - Check PostgreSQL add-on status: `heroku addons`

3. **CORS errors**
   - Verify `FRONTEND_URL` matches your frontend domain
   - Check that `FLASK_ENV=production` is set

4. **API key errors**
   - Verify `GEMINI_API_KEY` and `OPENAI_API_KEY` are set
   - Test keys locally first

### Useful Commands

```bash
# Check config vars
heroku config

# Open app in browser
heroku open

# Scale dynos
heroku ps:scale web=1

# Restart app
heroku restart

# Database console
heroku pg:psql

# View recent logs
heroku logs --tail --num=50
```

## Cost Estimation

- **Heroku Dyno**: $7/month (eco dyno)
- **PostgreSQL**: $9/month (essential-0)
- **Total**: ~$16/month

## Scaling

For higher traffic:
- Upgrade to `standard-1x` dynos
- Add more web dynos: `heroku ps:scale web=2`
- Upgrade PostgreSQL plan as needed

## Support

For issues:
1. Check the logs first
2. Review this deployment guide
3. Check Heroku documentation
4. Open an issue in the repository 