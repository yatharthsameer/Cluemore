# 🚀 Deployment Setup Guide

This guide helps you set up CI/CD for the Cluemore monorepo with backend deployment to Heroku and frontend Mac app distribution.

## 📁 Project Structure

```
cluemore/
├── backend/                 # Python Flask API
│   ├── server.py
│   ├── requirements.txt
│   ├── Procfile
│   └── ...
├── frontend/                # Electron Mac App
│   ├── main.js
│   ├── package.json
│   └── ...
├── .github/workflows/       # CI/CD pipelines
├── deploy-heroku.sh         # Manual deployment script
├── heroku-setup.sh          # One-time Heroku setup
└── package.json            # Root monorepo config
```

## 🛠️ One-Time Setup

### 1. Heroku Setup

#### Option A: Automated Setup (Recommended)
```bash
# Run the setup script
./heroku-setup.sh
```

#### Option B: Manual Setup
```bash
# Install Heroku CLI if needed
# https://devcenter.heroku.com/articles/heroku-cli

# Create Heroku app
heroku create your-app-name

# Add Heroku remote
heroku git:remote -a your-app-name

# Set buildpack
heroku buildpacks:set heroku/python

# Add database (optional)
heroku addons:create heroku-postgresql:mini
```

### 2. GitHub Secrets Setup

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:
- `HEROKU_API_KEY`: Your Heroku API key (get from `heroku auth:token`)
- `HEROKU_APP_NAME`: Your Heroku app name
- `HEROKU_EMAIL`: Your Heroku account email

### 3. Environment Variables

#### Backend (`backend/.env`)
```env
# Copy from backend/env.example and fill in your values
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
DATABASE_URL=sqlite:///users.db  # Local development
# DATABASE_URL will be set automatically by Heroku for production
```

#### Frontend
Environment variables are handled in the frontend code as needed.

## 🚀 Deployment Options

### Automatic Deployment (CI/CD)

Once set up, deployments happen automatically:

- **Push to `main` branch** → Triggers deployment
- **Backend changes** → Deploys to Heroku
- **Frontend changes** → Builds Mac app
- **Both** → Deploys and builds simultaneously

### Manual Deployment

#### Backend to Heroku
```bash
# Quick deployment
./deploy-heroku.sh

# Or manual git subtree push
git subtree push --prefix=backend heroku main
```

#### Frontend Build
```bash
cd frontend
npm install
npm run build
npm run dist:mac  # Creates .dmg file
```

## 🔄 Development Workflow

### Local Development
```bash
# Install all dependencies
npm run install:all

# Run both backend and frontend
npm run dev

# Or run individually
npm run backend:dev
npm run frontend:dev
```

### Making Changes

1. **Backend changes**: Edit files in `backend/`
2. **Frontend changes**: Edit files in `frontend/`
3. **Commit and push**: CI/CD handles the rest

### Testing Deployment

1. **Create a test branch**:
   ```bash
   git checkout -b test-deployment
   ```

2. **Make changes and push**:
   ```bash
   git add .
   git commit -m "Test deployment"
   git push origin test-deployment
   ```

3. **Check GitHub Actions** for build status

4. **Merge to main** when ready for production

## 🐛 Troubleshooting

### Common Issues

#### Heroku Deployment Fails
- Check `HEROKU_API_KEY` secret is correct
- Verify app name in secrets matches actual Heroku app
- Check backend dependencies in `requirements.txt`

#### Frontend Build Fails
- Ensure Node.js version matches (18+)
- Check `frontend/package.json` scripts
- Verify macOS runner for Electron builds

#### Git Subtree Issues
```bash
# If subtree push fails, try force push (be careful!)
git push heroku `git subtree split --prefix=backend main`:main --force
```

### Logs and Debugging

```bash
# View Heroku logs
heroku logs --tail -a your-app-name

# Check GitHub Actions
# Go to your repo → Actions tab → View workflow runs
```

## 📚 Additional Resources

- [Heroku Python Documentation](https://devcenter.heroku.com/articles/getting-started-with-python)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Electron Builder Documentation](https://www.electron.build/)

## 🎯 Best Practices

1. **Always test in development** before pushing to main
2. **Use environment variables** for sensitive data
3. **Keep dependencies updated** in both backend and frontend
4. **Monitor deployments** via GitHub Actions and Heroku dashboard
5. **Use semantic versioning** for releases 