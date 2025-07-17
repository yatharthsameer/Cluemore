#!/bin/bash

# Auto-Update Test Script for Cluemore
# This script helps test the auto-update functionality

set -e

echo "🧪 Cluemore Auto-Update Test Script"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check current version
CURRENT_VERSION=$(node -e "console.log(require('./package.json').version)")
echo -e "${BLUE}📋 Current app version: $CURRENT_VERSION${NC}"

# Suggest new version
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# Increment minor version for testing
NEW_MINOR=$((MINOR + 1))
NEW_VERSION="$MAJOR.$NEW_MINOR.0"

echo -e "${YELLOW}💡 Suggested test version: $NEW_VERSION${NC}"
echo ""

# Ask user for confirmation
echo "🤔 Do you want to:"
echo "1. Update to suggested version ($NEW_VERSION) and build"
echo "2. Enter custom version"
echo "3. Just run diagnostics (no version change)"
echo "4. Exit"
echo ""

read -p "Choose option (1-4): " choice

case $choice in
    1)
        TEST_VERSION=$NEW_VERSION
        UPDATE_VERSION=true
        ;;
    2)
        read -p "Enter new version (e.g., 1.4.0): " TEST_VERSION
        UPDATE_VERSION=true
        ;;
    3)
        UPDATE_VERSION=false
        ;;
    4)
        echo "👋 Exiting..."
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Invalid option. Exiting.${NC}"
        exit 1
        ;;
esac

if [ "$UPDATE_VERSION" = true ]; then
    echo ""
    echo -e "${BLUE}🔄 Updating version to $TEST_VERSION...${NC}"
    
    # Update package.json version
    node -e "
    const fs = require('fs');
    const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    pkg.version = '$TEST_VERSION';
    fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
    console.log('✅ Updated package.json version to $TEST_VERSION');
    "
    
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Keep a copy of your current v$CURRENT_VERSION app for testing!${NC}"
    echo "   The update popup will only appear in the OLD version when a NEW version is available."
    echo ""
    
    read -p "📱 Do you have the v$CURRENT_VERSION app installed? (y/n): " has_old_app
    
    if [ "$has_old_app" != "y" ]; then
        echo -e "${RED}❌ You need the old app version to test updates!${NC}"
        echo "   Please install the current v$CURRENT_VERSION app first, then run this script."
        
        # Revert version change
        node -e "
        const fs = require('fs');
        const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
        pkg.version = '$CURRENT_VERSION';
        fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
        console.log('↩️  Reverted package.json version to $CURRENT_VERSION');
        "
        exit 1
    fi
    
    echo ""
    echo -e "${BLUE}🏗️  Building new version...${NC}"
    
    # Clean previous builds
    if [ -d "dist" ]; then
        rm -rf dist
        echo "🧹 Cleaned previous build"
    fi
    
    # Build the new version
    echo "📦 Running npm run build-mac..."
    npm run build-mac
    
    if [ $? -eq 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Build completed successfully!${NC}"
        echo ""
        echo -e "${BLUE}📤 Next steps:${NC}"
        echo "1. Go to: https://github.com/yatharthsameer/cluemore/releases"
        echo "2. Create a new release with tag: v$TEST_VERSION"
        echo "3. Upload the DMG files from dist/ folder"
        echo "4. Publish the release"
        echo "5. Open your OLD v$CURRENT_VERSION app"
        echo "6. The update popup should appear!"
        echo ""
        echo -e "${YELLOW}📁 Built files location:${NC}"
        ls -la dist/*.dmg 2>/dev/null || echo "   No DMG files found in dist/"
        
    else
        echo -e "${RED}❌ Build failed!${NC}"
        echo "   Check the error messages above"
        
        # Revert version change
        node -e "
        const fs = require('fs');
        const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
        pkg.version = '$CURRENT_VERSION';
        fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
        console.log('↩️  Reverted package.json version to $CURRENT_VERSION');
        "
        exit 1
    fi
else
    echo ""
    echo -e "${BLUE}🔍 Running diagnostics only...${NC}"
fi

# Run diagnostics
echo ""
echo -e "${BLUE}🔧 Running release diagnostics...${NC}"
node scripts/check-github-release.js

echo ""
echo -e "${GREEN}✅ Auto-update test script completed!${NC}"

if [ "$UPDATE_VERSION" = true ]; then
    echo ""
    echo -e "${YELLOW}🧪 Testing Instructions:${NC}"
    echo "1. Make sure you have the v$CURRENT_VERSION app installed"
    echo "2. Publish the v$TEST_VERSION release on GitHub"
    echo "3. Open the v$CURRENT_VERSION app"
    echo "4. Wait a few seconds - update popup should appear"
    echo "5. If no popup, check the app console logs"
    echo ""
    echo -e "${BLUE}💡 Troubleshooting:${NC}"
    echo "   - App must be signed for auto-updates on macOS"
    echo "   - Check main.js console logs for errors"
    echo "   - Verify release is published (not draft)"
    echo "   - Try manually: Help → Check for Updates"
fi 