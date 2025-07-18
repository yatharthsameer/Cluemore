# Cluemore Frontend Project Organization

## 📁 Directory Structure

```
Frontend/
├── 📋 DISTRIBUTION-GUIDE.md         # Complete distribution documentation
├── 📋 QUICK-REFERENCE.md            # Essential commands cheat sheet
├── 📋 PROJECT-ORGANIZATION.md       # This file
├── 🚫 .gitignore                    # Prevents unwanted files
│
├── 📦 package.json                  # Main build configuration (ACTIVE)
├── 📦 package-lock.json             # Lock file for dependencies
│
├── config/
│   └── package-variants/
│       ├── package.json.backup      # Backup of working config
│       ├── package.json.electron37  # Electron 37 specific config
│       └── package-electron27.json  # Legacy Electron 27 config
│
├── scripts/
│   ├── 🔨 build-production.sh       # Easy build script (NEW)
│   ├── 🔐 notarize.js               # Notarization with retry logic
│   └── ✍️  fix-electron-signing.js   # Comprehensive signing script
│
├── assets/
│   ├── 🎨 icon.icns                 # macOS app icon
│   ├── 📄 entitlements.mac.plist    # macOS entitlements
│   ├── 📄 entitlements.mas.plist    # Mac App Store entitlements
│   └── 📄 entitlements.mas.inherit.plist
│
├── 🏗️ main.js                       # Electron main process
├── 🔌 preload.js                    # Preload script for security
├── 🌐 index.html                    # Main application UI
├── 🔐 auth.html                     # Authentication page
├── 🖼️ icon.png                      # App icon (PNG format)
│
└── dist/                           # Build output (created during build)
    ├── Cluemore-X.X.X-arm64.dmg    # Apple Silicon distribution
    ├── Cluemore-X.X.X-arm64-mac.zip # Apple Silicon ZIP
    └── mac-arm64/Cluemore.app      # Raw app bundle
```

## 🧹 **Recently Cleaned Up**

### ❌ **Removed Files (No longer needed):**
- `README-DISTRIBUTION.md` → Replaced by `DISTRIBUTION-GUIDE.md`
- `SETUP-CODESIGNING.md` → Information moved to `DISTRIBUTION-GUIDE.md`
- `build-config.js` → **SECURITY RISK** (contained plain text credentials)
- `scripts/sign-native-modules.js` → Redundant (handled by `fix-electron-signing.js`)
- `scripts/custom-sign.js` → Redundant (replaced by current scripts)
- `*.cer` files → Certificate authority files (not needed in project)
- `.DS_Store` files → macOS system files

### 🛡️ **Security Improvements:**
- Added `.gitignore` to prevent sensitive files
- Removed plain text credentials from codebase
- Credentials now only stored securely in keychain

## 🎯 Key Files for Distribution

### Essential Files (Don't Modify)
- `package.json` - Working build configuration
- `scripts/notarize.js` - Fixed notarization process
- `scripts/fix-electron-signing.js` - Signing process
- `assets/entitlements.mac.plist` - Security entitlements

### Easy Commands
- `./scripts/build-production.sh` - One-click distribution build
- `QUICK-REFERENCE.md` - Essential commands only

### Backup/Recovery
- `config/package-variants/` - Different configuration options
- `DISTRIBUTION-GUIDE.md` - Complete documentation

## 🚀 Quick Start for New Team Members

1. **Clone and setup**:
   ```bash
   cd Frontend
   npm install
   ```

2. **Build for distribution**:
   ```bash
   ./scripts/build-production.sh
   ```

3. **Check results**:
   ```bash
   ls -la dist/*.dmg
   ```

## 🔧 Configuration Management

### Current Working Setup
- **Main config**: `package.json` (Electron 37, working notarization)
- **Build hook**: `afterAllArtifactBuild` → `scripts/notarize.js`
- **Signing hook**: `afterSign` → `scripts/fix-electron-signing.js`

### Backup Configurations
- **Latest backup**: `config/package-variants/package.json.backup`
- **Electron 37**: `config/package-variants/package.json.electron37`
- **Legacy fallback**: `config/package-variants/package-electron27.json`

### Switching Configurations
```bash
# Emergency downgrade to Electron 27
cp config/package-variants/package-electron27.json package.json
npm install

# Restore working configuration
cp config/package-variants/package.json.backup package.json
npm install
```

## ⚠️ Critical Notes

1. **Don't modify** `afterAllArtifactBuild` in package.json - it fixes notarization timing
2. **Stapling Error 65 is normal** - apps still work for distribution
3. **ARM64 DMG for Apple Silicon Macs** - Apple Silicon architecture only
4. **Build script checks prerequisites** automatically
5. **Never commit credentials** - use keychain profiles only

## 📋 Maintenance Checklist

### Before Major Updates
- [ ] Backup current `package.json` to `config/package-variants/`
- [ ] Test build with new dependencies
- [ ] Verify code signing still works
- [ ] Check notarization process

### After Successful Changes
- [ ] Update `config/package-variants/package.json.backup`
- [ ] Document changes in `DISTRIBUTION-GUIDE.md`
- [ ] Test full distribution process

## 🆘 Emergency Recovery

If builds break:
1. **Restore working config**: `cp config/package-variants/package.json.backup package.json`
2. **Clean rebuild**: `rm -rf node_modules dist && npm install`
3. **Test build**: `./scripts/build-production.sh`

## 🛡️ Security Best Practices

- ✅ **Credentials in keychain only** (not in files)
- ✅ **`.gitignore` prevents sensitive files**
- ✅ **No plain text passwords**
- ✅ **Certificate files excluded from git**

---

**Last organized**: July 9, 2025  
**Cleanup completed**: ✅ Project streamlined and secured  
**Working status**: ✅ Ready for production distribution 