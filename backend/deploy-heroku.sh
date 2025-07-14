#!/bin/bash

# Heroku deployment script for Cluemore Backend
# This script will redeploy your backend with the updated OpenAI client requirements

echo "🚀 Deploying Cluemore Backend to Heroku..."

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found. Please run this script from the backend directory."
    exit 1
fi

# Check if heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Error: Heroku CLI is not installed. Please install it first."
    echo "   Visit: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Get the current git status
echo "📋 Checking git status..."
git status

# Add the updated requirements.txt
echo "📦 Adding updated requirements.txt..."
git add requirements.txt
git add openai_client.py

# Commit the changes
echo "💾 Committing changes..."
git commit -m "Fix OpenAI client version compatibility issue

- Updated openai from 1.30.1 to 1.55.3
- Added httpx==0.27.2 for compatibility
- Resolves 'unexpected keyword argument proxies' error"

# Push to heroku
echo "🚀 Pushing to Heroku..."
git push heroku main

# Check deployment status
echo "✅ Deployment complete!"
echo "📝 To check logs, run: heroku logs --tail"
echo "🔍 To check app status, run: heroku ps"

# Optional: open the app
read -p "Do you want to open your app in the browser? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    heroku open
fi

echo "🎉 Done!" 