# Cluemore Auto-Update System

## Overview

Cluemore now includes an automated update system that checks for new versions and allows users to download and install updates seamlessly.

## How It Works

1. **Automatic Checks**: App checks for updates on startup (production only)
2. **User Notification**: Shows dialog when updates are available
3. **Download & Install**: Users can download and install updates with one click
4. **GitHub Releases**: Uses GitHub Releases as the update feed

## User Experience

### Update Available Dialog
When an update is found:
```
┌─────────────────────────────────────┐
│ Cluemore Update Available           │
├─────────────────────────────────────┤
│ A new version is available (v1.2.0) │
│ Download now and install when ready?│
│                                     │
│              [Later]  [Download]    │
└─────────────────────────────────────┘
```

### Download Progress
- Console logs show download progress
- Renderer receives progress events (optional UI)

### Install Confirmation
After download completes:
```
┌─────────────────────────────────────┐
│ Update Ready to Install             │
├─────────────────────────────────────┤
│ Update downloaded successfully.     │
│ Restart the app to apply the update │
│ now?                               │
│                                     │
│              [Later]  [Install &    │
│                       Restart]     │
└─────────────────────────────────────┘
```

## Publishing Updates

### 1. Prepare Release

Update version in `package.json`:
```json
{
  "version": "1.2.0"
}
```

### 2. Build for Distribution

```bash
cd frontend
export NOTARIZE_APP=true
export NOTARIZE_KEYCHAIN_PROFILE=sameerbros-creds
npm run build-mac
```

This creates:
- `Cluemore-1.2.0-arm64.dmg` (Apple Silicon)
- `Cluemore-1.2.0.dmg` (Intel)
- `Cluemore-1.2.0-arm64-mac.zip` (Apple Silicon ZIP)
- `Cluemore-1.2.0-mac.zip` (Intel ZIP)
- `latest-mac.yml` (update metadata)

### 3. Create GitHub Release

1. Go to GitHub repository
2. Click "Releases" → "Create a new release"
3. Set tag version: `v1.2.0` (must match package.json version)
4. Upload all generated files:
   ```
   Cluemore-1.2.0-arm64.dmg
   Cluemore-1.2.0.dmg
   Cluemore-1.2.0-arm64-mac.zip
   Cluemore-1.2.0-mac.zip
   latest-mac.yml
   ```
5. Write release notes
6. Publish release

### 4. Update Propagation

- `electron-updater` polls GitHub for new releases
- Users with older versions will see update notification on next launch
- Updates are differential (delta) when possible

## Configuration

### GitHub Repository Settings

In `package.json`:
```json
"publish": [
  {
    "provider": "github",
    "owner": "sameerbros",
    "repo": "cluemore",
    "private": false
  }
]
```

### Environment Requirements

- **Production Only**: Auto-updates only work in production builds
- **Code Signing**: macOS requires signed and notarized builds
- **GitHub Releases**: Public repository for update feed

## Manual Update Checks

You can also trigger update checks programmatically:

```javascript
// In renderer process
const result = await window.electronAPI.checkForUpdates();
if (result.success) {
  console.log('Update check completed');
} else {
  console.error('Update check failed:', result.error);
}
```

## Development vs Production

| Environment | Auto-Updates | Behavior |
|-------------|--------------|----------|
| Development | ❌ Disabled | No update checks performed |
| Production | ✅ Enabled | Full auto-update functionality |

## Troubleshooting

### Updates Not Working

1. **Check Environment**: Ensure `NODE_ENV=production`
2. **Verify Signing**: macOS requires signed builds
3. **GitHub Release**: Ensure `latest-mac.yml` is uploaded
4. **Version Format**: Use semver (e.g., `1.2.0`, not `v1.2.0` in package.json)

### Common Issues

| Issue | Solution |
|-------|----------|
| "No updates available" | Check GitHub release tag format (`v1.2.0`) |
| Update downloads but won't install | Verify code signing and notarization |
| Progress not showing | Check console logs, renderer events optional |
| Private repo access | Add `GH_TOKEN` environment variable |

## Security Notes

- Updates are verified through code signatures
- Only signed releases are accepted
- Update metadata is served over HTTPS
- No arbitrary code execution risks

## Advanced Features

### Periodic Checks
Add to main.js for hourly checks:
```javascript
setInterval(() => autoUpdater.checkForUpdates(), 4 * 60 * 60 * 1000);
```

### Beta Channel
Build with beta channel:
```bash
npm run build-mac -- --publish=always --prepackaged
```

Update publish config:
```json
"publish": {
  "provider": "github",
  "channel": "beta"
}
```

### Custom UI
Replace dialogs with custom renderer UI using IPC events.

## Testing Updates

1. Build version `1.0.0` and install
2. Update package.json to `1.0.1`
3. Build and create GitHub release
4. Launch installed `1.0.0` app
5. Should see update notification

## Checklist for Releases

- [ ] Update version in package.json
- [ ] Build with production settings
- [ ] Verify code signing and notarization
- [ ] Create GitHub release with correct tag
- [ ] Upload all required files
- [ ] Test update flow with previous version
- [ ] Monitor for successful updates 