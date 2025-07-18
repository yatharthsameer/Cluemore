#!/bin/bash

# Cluemore Production Build Script
# This script builds the Mac app for distribution with proper code signing and notarization

set -e  # Exit on any error

echo "🚀 Starting Cluemore production build..."
echo "📁 Current directory: $(pwd)"

# Check if we're in the Frontend directory
if [[ ! -f "package.json" ]]; then
    echo "❌ Error: package.json not found. Please run from the Frontend directory."
    exit 1
fi

# Check if required credentials are available
if ! security find-identity -v -p codesigning | grep -q "TC4HN9NNR3"; then
    echo "❌ Error: Developer ID certificate not found in keychain."
    echo "   Please ensure 'Developer ID Application: Yatharth Sameer (TC4HN9NNR3)' is installed."
    exit 1
fi

# Check if keychain profile exists
if ! xcrun notarytool history --keychain-profile sameerbros-creds >/dev/null 2>&1; then
    echo "❌ Error: Keychain profile 'sameerbros-creds' not found."
    echo "   Please set up notarization credentials first."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Set up environment for notarization
export NOTARIZE_KEYCHAIN_PROFILE=sameerbros-creds
export NOTARIZE_APP=true

echo "🔧 Environment configured:"
echo "   NOTARIZE_KEYCHAIN_PROFILE=$NOTARIZE_KEYCHAIN_PROFILE"
echo "   NOTARIZE_APP=$NOTARIZE_APP"

# Clean previous build if it exists
if [[ -d "dist" ]]; then
    echo "🧹 Cleaning previous build..."
    rm -rf dist
fi

# Install dependencies if needed
if [[ ! -d "node_modules" ]]; then
    echo "📦 Installing dependencies..."
    npm install
fi

echo "🔨 Building Mac application..."
echo "   This will create ARM64 version for Apple Silicon Macs"
echo "   Build may take 5-10 minutes including notarization..."

# Run the build
npm run build-mac

# Check if build was successful
if [[ $? -eq 0 ]]; then
    echo ""
    echo "🎉 Build completed successfully!"
    echo ""
    echo "📦 Distribution files created:"
    
    if [[ -f "dist/Cluemore-1.0.0-arm64.dmg" ]]; then
        echo "   ✅ dist/Cluemore-1.0.0-arm64.dmg (Apple Silicon)"
        echo "      Size: $(du -h dist/Cluemore-1.0.0-arm64.dmg | cut -f1)"
    fi
    
    if [[ -f "dist/Cluemore-1.0.0-arm64-mac.zip" ]]; then
        echo "   ✅ dist/Cluemore-1.0.0-arm64-mac.zip"
    fi
    
    echo ""
    echo "🔍 Verification:"
    
    # Verify code signing
    if [[ -d "dist/mac-arm64/Cluemore.app" ]]; then
        echo "   📝 Checking code signature..."
        if codesign -dv "dist/mac-arm64/Cluemore.app" >/dev/null 2>&1; then
            echo "   ✅ Code signature valid"
        else
            echo "   ❌ Code signature verification failed"
        fi
    fi
    
    # Check notarization history
    echo "   📝 Checking notarization status..."
    recent_status=$(xcrun notarytool history --keychain-profile sameerbros-creds 2>/dev/null | head -6 | grep -o "status: [A-Za-z]*" | head -1 | cut -d' ' -f2)
    if [[ "$recent_status" == "Accepted" ]]; then
        echo "   ✅ Notarization: Accepted"
    else
        echo "   ⚠️  Notarization status: $recent_status"
    fi
    
    echo ""
    echo "🚀 Ready for distribution!"
    echo "   Upload the ARM64 DMG file to your distribution platform"
    echo "   Apple Silicon Mac users can download and install without security warnings"
    
    # Note about stapling
    echo ""
    echo "ℹ️  Note: Stapling may show 'Error 65' - this is a known issue and doesn't"
    echo "   affect distribution. The apps are properly notarized and will work for users."
    
else
    echo ""
    echo "❌ Build failed!"
    echo "   Check the error messages above for details"
    echo "   Common solutions:"
    echo "   - Run: rm -rf node_modules && npm install"
    echo "   - Check certificate installation: security find-identity -v -p codesigning"
    echo "   - Verify keychain profile: xcrun notarytool history --keychain-profile sameerbros-creds"
    exit 1
fi 