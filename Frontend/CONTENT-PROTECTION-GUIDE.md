# Content Protection Toggle Guide

## Overview

Cluemore includes content protection that makes the app invisible to screen sharing and screenshot applications. This is enabled by default for security, but can be toggled off during development when you need to take screenshots.

## Current Status

- **Default:** Content protection is **ENABLED** (app is invisible to screen sharing)
- **Setting:** Persisted in your user settings and remembers your preference

## How to Toggle During Development

### Method 1: Browser Console (Recommended)

1. **Open Developer Tools:**
   - Press `F12` or `Cmd+Option+I` (macOS) 
   - Or right-click in the app and select "Inspect Element"

2. **Go to Console tab**

3. **Use these commands:**

```javascript
// Check current status
dev.status()

// Make app VISIBLE to screen sharing (for screenshots)
dev.makeVisible()

// Make app INVISIBLE to screen sharing (secure mode)  
dev.makeInvisible()

// Show help
dev.help()
```

### Method 2: Direct API (Advanced)

```javascript
// Get current status
await window.electronAPI.getContentProtectionStatus()

// Toggle content protection
await window.electronAPI.toggleContentProtection(false) // Make visible
await window.electronAPI.toggleContentProtection(true)  // Make invisible
```

## Quick Development Workflow

1. **When you need to take screenshots:**
   ```javascript
   dev.makeVisible()
   ```

2. **When you're done with screenshots:**
   ```javascript
   dev.makeInvisible()
   ```

3. **Check what mode you're in:**
   ```javascript
   dev.status()
   ```

## What This Controls

- **Content Protection ENABLED (invisible):**
  - ✅ Secure - app content can't be captured
  - ❌ Can't take screenshots for development
  - ❌ Invisible to screen sharing apps

- **Content Protection DISABLED (visible):**
  - ✅ Can take screenshots 
  - ✅ Visible to screen sharing apps
  - ⚠️ Less secure - app content can be captured

## Auto-Notification

The app will automatically log to console when content protection status changes:

```
🔒 Content protection changed: DISABLED
📱 Content protection disabled - app is now visible to screen sharing
```

## Troubleshooting

### Console Helper Not Available

If `dev` commands don't work:

1. Make sure you're in the main app window (not auth window)
2. Refresh the app or restart it
3. Check console for any error messages

### Content Protection Not Working

1. Try restarting the app
2. Check if you're using the latest version
3. Make sure you're testing with a screen sharing app that respects content protection

## Technical Details

- Uses Electron's `setContentProtection()` API
- Setting is persisted in `settings.json` in your user data directory
- Applied to all windows (main, auth, prompt editor)
- Changes take effect immediately without restart needed

---

**💡 Pro Tip:** Set up a keyboard shortcut in your development environment to quickly run `dev.makeVisible()` and `dev.makeInvisible()` for faster workflow! 