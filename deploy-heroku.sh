#!/bin/bash

# Heroku Backend Deployment Script for Monorepo
# This script deploys the backend subdirectory to Heroku

set -e

echo "🚀 Deploying backend to Heroku..."

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Check if backend directory exists
if [ ! -d "backend" ]; then
    echo "❌ Error: backend directory not found"
    exit 1
fi

# Set Heroku app name (you can override this)
HEROKU_APP=${HEROKU_APP:-"your-cluemore-app"}

echo "📁 Deploying backend directory to Heroku app: $HEROKU_APP"

# Deploy using git subtree
git subtree push --prefix=backend heroku main

echo "✅ Backend deployed successfully to Heroku!"
echo "🌐 Your app should be available at: https://$HEROKU_APP.herokuapp.com" 