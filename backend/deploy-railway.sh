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
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI is not installed. Installing now..."
    echo "💡 Visit: https://docs.railway.app/develop/cli for manual installation"
    
    # Try to install Railway CLI
    if command -v npm &> /dev/null; then
        echo "📦 Installing Railway CLI via npm..."
        npm install -g @railway/cli
    elif command -v brew &> /dev/null; then
        echo "🍺 Installing Railway CLI via Homebrew..."
        brew install railway
    else
        echo "❌ Please install Railway CLI manually from https://docs.railway.app/develop/cli"
        exit 1
    fi
fi

# Login to Railway
echo "🔐 Logging into Railway..."
railway login

# Initialize Railway project
echo "🎯 Initializing Railway project..."
railway init

# Link to existing project or create new one
echo "🔗 Linking to Railway project..."
echo "Choose an option:"
echo "1. Create a new project"
echo "2. Link to existing project"
read -p "Enter your choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo "📝 Enter your project name:"
    read -p "Project name: " project_name
    railway init "$project_name"
elif [ "$choice" = "2" ]; then
    railway link
else
    echo "❌ Invalid choice. Exiting."
    exit 1
fi

# Add PostgreSQL service
echo "🗄️ Adding PostgreSQL database..."
railway add postgresql

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
railway up

# Check deployment status
echo "✅ Deployment initiated!"
echo "📝 To check logs, run: railway logs"
echo "🔍 To check service status, run: railway status"
echo "🌐 To open dashboard, run: railway open"

# Optional: open the dashboard
read -p "Do you want to open Railway dashboard? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    railway open
fi

echo "🎉 Done!"
echo ""
echo "📋 Next steps:"
echo "1. Check deployment logs: railway logs"
echo "2. Get your app URL: railway domain"
echo "3. Update your frontend to use the new backend URL"
echo "4. Test your API endpoints"
