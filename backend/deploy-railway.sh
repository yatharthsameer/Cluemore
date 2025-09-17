#!/bin/bash

# Railway deployment script for Cluemore Backend
# This script will help you deploy your backend to Railway

echo "🚀 Deploying Cluemore Backend to Railway..."

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Error: requirements.txt not found. Please run this script from the backend directory."
    exit 1
fi

# Check if railway CLI is installed
RAILWAY_CMD="railway"
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI is not installed. Installing now..."
    echo "💡 Visit: https://docs.railway.app/develop/cli for manual installation"
    
    # Try to install Railway CLI
    if command -v npm &> /dev/null; then
        echo "📦 Installing Railway CLI via npm..."
        npm install -g @railway/cli
        # Check if global install worked, otherwise use npx
        if ! command -v railway &> /dev/null; then
            echo "ℹ️ Using npx to run Railway CLI..."
            RAILWAY_CMD="npx @railway/cli"
        fi
    elif command -v brew &> /dev/null; then
        echo "🍺 Installing Railway CLI via Homebrew..."
        brew install railway
    else
        echo "❌ Please install Railway CLI manually from https://docs.railway.app/develop/cli"
        exit 1
    fi
fi

# Login to Railway
echo "🔐 Please login to Railway in your browser..."
echo "ℹ️ If you need to logout first, run: $RAILWAY_CMD logout"
echo "Press Enter when ready to login..."
read -p ""
$RAILWAY_CMD login

# Initialize Railway project
echo "🎯 Creating new Railway project..."
echo "📝 Enter your project name (or press Enter for 'cluemore-backend'):"
read -p "Project name: " project_name
project_name=${project_name:-cluemore-backend}

# Create new project
if [ -z "$project_name" ]; then
    $RAILWAY_CMD init
else
    # Railway init doesn't take project name as argument, we'll set it after
    $RAILWAY_CMD init
fi

# Add PostgreSQL service (correct syntax)
echo "🗄️ Adding PostgreSQL database..."
$RAILWAY_CMD add --database postgres

# Set environment variables
echo "🔧 Setting up environment variables..."
echo "Please set the following environment variables in Railway dashboard:"
echo "1. FLASK_ENV=production"
echo "2. GEMINI_API_KEY=your_gemini_api_key_here"
echo "3. OPENAI_API_KEY=your_openai_api_key_here"
echo "4. JWT_SECRET=your_jwt_secret_here"
echo "5. FRONTEND_URL=https://your-frontend-domain.com"

read -p "Have you set all environment variables in Railway dashboard? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Please set environment variables first, then run this script again."
    echo "🌐 Open Railway dashboard: railway open"
    exit 1
fi

# Deploy to Railway
echo "🚀 Deploying to Railway..."
$RAILWAY_CMD up

# Check deployment status
echo "✅ Deployment initiated!"
echo "📝 To check logs, run: $RAILWAY_CMD logs"
echo "🔍 To check service status, run: $RAILWAY_CMD status"
echo "🌐 To open dashboard, run: $RAILWAY_CMD open"

# Optional: open the dashboard
read -p "Do you want to open Railway dashboard? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    $RAILWAY_CMD open
fi

echo "🎉 Done!"
echo ""
echo "📋 Next steps:"
echo "1. Check deployment logs: $RAILWAY_CMD logs"
echo "2. Get your app URL: $RAILWAY_CMD domain"
echo "3. Update your frontend to use the new backend URL"
echo "4. Test your API endpoints"
