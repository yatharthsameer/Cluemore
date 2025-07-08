#!/bin/bash

# Heroku Setup Script for Cluemore Backend
# Run this once to set up your Heroku app with the correct configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔧 Setting up Heroku for Cluemore Backend${NC}"

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo -e "${RED}❌ Heroku CLI not found. Please install it first.${NC}"
    echo "Install from: https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Get app name from user
read -p "Enter your Heroku app name (or press Enter for 'cluemore-backend'): " HEROKU_APP
HEROKU_APP=${HEROKU_APP:-"cluemore-backend"}

echo -e "${YELLOW}📱 Creating Heroku app: $HEROKU_APP${NC}"

# Create Heroku app (if it doesn't exist)
heroku apps:info $HEROKU_APP >/dev/null 2>&1 || heroku create $HEROKU_APP

# Add Heroku remote
heroku git:remote -a $HEROKU_APP

# Set buildpack for Python
echo -e "${YELLOW}🐍 Setting Python buildpack${NC}"
heroku buildpacks:set heroku/python -a $HEROKU_APP

# Set environment variables
echo -e "${YELLOW}⚙️ Setting environment variables${NC}"
heroku config:set FLASK_ENV=production -a $HEROKU_APP
heroku config:set PYTHON_VERSION=3.11.0 -a $HEROKU_APP

# Add database addon (optional)
echo -e "${YELLOW}🗄️ Adding database addon${NC}"
heroku addons:create heroku-postgresql:mini -a $HEROKU_APP || echo "Database addon might already exist"

echo -e "${GREEN}✅ Heroku setup complete!${NC}"
echo -e "${GREEN}📁 To deploy, run: ./deploy-heroku.sh${NC}"
echo -e "${GREEN}🌐 Your app will be available at: https://$HEROKU_APP.herokuapp.com${NC}"

# Save app name for deploy script
echo "export HEROKU_APP=$HEROKU_APP" > .heroku-app-name 