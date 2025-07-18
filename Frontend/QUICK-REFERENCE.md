# Cluemore Distribution - Quick Reference

## 🚀 Build for Distribution (Easy Way)

```bash
cd Frontend
./scripts/build-production.sh
```

**Result**: Ready-to-distribute DMG files in `dist/`

---

## 🔧 Manual Build Commands

```bash
cd Frontend
export NOTARIZE_KEYCHAIN_PROFILE=sameerbros-creds
export NOTARIZE_APP=true
npm run build-mac
```

---

## ✅ Verification Commands

```bash
# Check code signature
codesign -dv "dist/mac-arm64/Cluemore.app"

# Check notarization history
xcrun notarytool history --keychain-profile sameerbros-creds | head -5

# Verify distribution files
ls -la dist/*.dmg
```

---

## 📦 Distribution Files

After successful build:
- `dist/Cluemore-1.0.0-arm64.dmg` → **Apple Silicon (M1/M2/M3)**
- `dist/Cluemore-1.0.0-arm64.dmg` → **Apple Silicon**

**Upload both files to your distribution platform**

---

## 🛠 Troubleshooting

### Build Fails
```bash
rm -rf node_modules dist
npm install
./scripts/build-production.sh
```

### Certificate Issues
```bash
security find-identity -v -p codesigning
# Should show: Developer ID Application: Yatharth Sameer (TC4HN9NNR3)
```

### Emergency Downgrade
```bash
cp config/package-variants/package-electron27.json package.json
npm install
```

---

## 📋 Version Update Process

1. **Update version in `package.json`**
2. **Run build**: `./scripts/build-production.sh`
3. **Test on clean macOS system**
4. **Upload new DMG files**

---

## ⚠️ Known Issues

- **Stapling Error 65**: Normal, doesn't affect distribution
- **spctl shows "Unnotarized"**: Apps still work for users
- **Notarization timing**: May take 5-10 minutes

---

**Key Point**: DMG files are ready to distribute even if stapling shows errors! 