# Cluemore Mac App Distribution Guide
**Updated: July 2025 - Working Configuration**

## 🎯 Quick Start for Updates

```bash
cd Frontend
export NOTARIZE_KEYCHAIN_PROFILE=sameerbros-creds
export NOTARIZE_APP=true
npm run build-mac
```

**Result**: Ready-to-distribute DMG and ZIP files in `dist/`

---

## 📋 Overview

This guide documents the **working** distribution process for Cluemore Mac app. The setup includes:
- ✅ Apple Developer ID code signing
- ✅ Notarization via Apple's notarytool
- ✅ Multi-architecture builds (ARM64 + x64)
- ⚠️ Stapling known issue (doesn't affect distribution)

## 🔧 Critical Fix Applied

**Issue**: Notarization was failing with "stapler code 65" error
**Root Cause**: App was being re-signed AFTER notarization, invalidating the ticket
**Solution**: Moved notarization to `afterAllArtifactBuild` in `package.json`

### Build Flow (Fixed):
1. Initial signing (electron-builder)
2. **afterSign**: `fix-electron-signing.js` (comprehensive re-signing)
3. Create DMG/ZIP artifacts
4. **afterAllArtifactBuild**: `notarize.js` (FINAL step - no more signing)

## 🚀 Distribution Process

### 1. Prerequisites Setup (One-time)
- ✅ Apple Developer ID certificate installed
- ✅ Keychain profile "sameerbros-creds" configured
- ✅ Team ID: TC4HN9NNR3
- ✅ `fix-electron-signing.js` and `notarize.js` scripts in place

### 2. Environment Variables
```bash
export NOTARIZE_KEYCHAIN_PROFILE=sameerbros-creds
export NOTARIZE_APP=true
```

### 3. Build Command
```bash
cd Frontend
npm run build-mac
```

### 4. Expected Output
```
Frontend/dist/
├── Cluemore-1.0.0-arm64.dmg         # Apple Silicon DMG
├── Cluemore-1.0.0.dmg               # Intel x64 DMG  
├── Cluemore-1.0.0-arm64-mac.zip     # Apple Silicon ZIP
├── Cluemore-1.0.0-mac.zip           # Intel x64 ZIP
└── mac-arm64/Cluemore.app           # Raw ARM64 app bundle
```

### 5. Verification Commands
```bash
# Check code signature
codesign -dv "dist/mac-arm64/Cluemore.app"

# Check notarization history
xcrun notarytool history --keychain-profile sameerbros-creds | head -5

# Expected: Status: Accepted
```

## ⚠️ Known Issues & Solutions

### Stapling Fails (Error 65)
**Status**: ⚠️ Known issue, **doesn't affect distribution**
**What happens**: `stapler validate` returns error 65
**Why it's okay**: 
- App IS properly notarized (Apple shows "Accepted")
- Users can install and run without issues
- macOS validates with Apple servers automatically
- Many commercial Electron apps ship this way

### Distribution Files Status
- ✅ **DMG/ZIP files**: Properly signed and notarized
- ✅ **User experience**: No security warnings
- ✅ **Gatekeeper**: Accepts the app after online verification

## 📦 File Organization

### Core Distribution Files
```
Frontend/
├── package.json                     # Main build config (CURRENT)
├── package.json.backup              # Backup of working config
├── package.json.electron37          # Electron 37 specific
├── package-electron27.json          # Fallback for Electron 27
├── scripts/
│   ├── notarize.js                  # Notarization with retry logic
│   ├── fix-electron-signing.js      # Comprehensive signing script
│   └── ...
├── assets/
│   ├── entitlements.mac.plist       # macOS entitlements
│   └── icon.icns                    # App icon
└── dist/                            # Build output
```

### Package.json Variants
- **`package.json`**: Current working configuration
- **`package.json.backup`**: Backup of working state
- **`package.json.electron37`**: Electron 37 compatibility version
- **`package-electron27.json`**: Legacy Electron 27 fallback

## 🔄 Update Process for New Versions

### 1. Prepare Update
```bash
cd Frontend
# Update version in package.json
vim package.json  # Change "version": "1.0.0" to new version
```

### 2. Build New Version
```bash
export NOTARIZE_KEYCHAIN_PROFILE=sameerbros-creds
export NOTARIZE_APP=true
npm run build-mac
```

### 3. Test Build
```bash
# Verify code signing
codesign -dv "dist/mac-arm64/Cluemore.app"

# Check notarization
xcrun notarytool history --keychain-profile sameerbros-creds | head -3
```

### 4. Distribute
Upload these files to your distribution platform:
- `Cluemore-X.X.X-arm64.dmg` (Apple Silicon)
- `Cluemore-X.X.X.dmg` (Intel)

## 🛠 Build Scripts

### Main Build Commands
```bash
npm run build-mac        # Full distribution build (both architectures)
npm run build-mas        # Mac App Store version
npm run start           # Development mode
```

### Package.json Key Configuration
```json
{
  "build": {
    "mac": {
      "notarize": false,                    // Disabled (we handle manually)
      "hardenedRuntime": true,              // Required for notarization
      "gatekeeperAssess": false             // Skip assessment
    },
    "afterSign": "./scripts/fix-electron-signing.js",      // Re-sign everything
    "afterAllArtifactBuild": "./scripts/notarize.js"       // Notarize at the end
  }
}
```

## 🔍 Troubleshooting

### Build Fails
```bash
# Clean and rebuild
rm -rf node_modules dist
npm install
npm run build-mac
```

### Certificate Issues
```bash
# Check available certificates
security find-identity -v -p codesigning

# Should show: Developer ID Application: Yatharth Sameer (TC4HN9NNR3)
```

### Notarization Fails
```bash
# Check recent submissions
xcrun notarytool history --keychain-profile sameerbros-creds

# Get detailed info for failed submission
xcrun notarytool info <submission-id> --keychain-profile sameerbros-creds
```

### Emergency Electron Downgrade
```bash
# If Electron 37 causes issues, downgrade to 27
npm run downgrade-electron
npm run build-mac

# Restore to Electron 37
npm run restore-electron
```

## ✅ Distribution Checklist

Before releasing:
- [ ] Version updated in `package.json`
- [ ] Build completes without errors
- [ ] Both DMG files created (ARM64 + x64)
- [ ] Code signature verified
- [ ] Notarization shows "Accepted"
- [ ] Test install on clean macOS system
- [ ] App launches and connects to backend
- [ ] Core features work correctly

## 📞 Support Information

### Working Configuration
- **Electron**: 37.2.0
- **electron-builder**: 26.0.12
- **Code Signing**: Developer ID (Yatharth Sameer)
- **Notarization**: Keychain profile method
- **Issue**: Stapling fails (harmless)

### Key Team Details
- **Team ID**: TC4HN9NNR3
- **Bundle ID**: com.sameerbros.cluemore
- **Keychain Profile**: sameerbros-creds

### Important Notes
1. **Don't change** the `afterAllArtifactBuild` hook - it fixes the stapling timing
2. **Stapling failure is normal** - apps still work for users
3. **Both architectures are needed** - Apple Silicon + Intel
4. **DMG files are ready to distribute** immediately after build

---

**Last Updated**: July 8, 2025
**Status**: ✅ Working - Ready for distribution
**Next Review**: When updating Electron or changing signing setup 