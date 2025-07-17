#!/bin/bash

# Bundle Size Analysis Script for Cluemore
echo "🔍 Analyzing Cluemore bundle size..."

# Clean and reinstall dependencies
echo "📦 Cleaning and reinstalling dependencies..."
rm -rf node_modules package-lock.json
npm install --only=production --silent

echo "📊 Production dependencies size:"
du -sh node_modules/ 2>/dev/null || echo "No node_modules found"

echo ""
echo "🔍 Largest production dependencies:"
du -sh node_modules/* 2>/dev/null | sort -hr | head -5

echo ""
echo "📱 App source files size:"
find . -name "*.js" -o -name "*.html" -o -name "*.css" | grep -v node_modules | xargs du -ch | tail -1

echo ""
echo "🖼️  Assets size:"
du -sh assets/ icon.png 2>/dev/null | sort -hr

echo ""
echo "💡 Recommendations:"
echo "   - Total production node_modules should be < 100MB"
echo "   - Consider lazy loading heavy dependencies"
echo "   - Use electron-builder's compression features"
echo "   - Remove unused files from assets/"

# Reinstall all dependencies (including dev)
echo ""
echo "🔄 Reinstalling all dependencies..."
npm install --silent

echo "✅ Analysis complete!" 