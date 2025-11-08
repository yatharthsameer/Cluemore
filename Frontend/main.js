const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, desktopCapturer, ipcMain, systemPreferences, dialog, session } = require('electron');
const WebSocket = require('ws');
const { autoUpdater } = require('electron-updater');
const path = require('path');
const https = require('https');
const http = require('http');
const keytar = require('keytar');

// Basic startup logging
console.log('🎬 Cluemore starting...');
console.log(`   Version: ${app.getVersion()}`);
console.log(`   Packaged: ${app.isPackaged}`);

// Load environment variables only in development
// Use try-catch to handle missing dotenv in production builds
try {
  if (process.env.NODE_ENV !== 'production') {
    require('dotenv').config({
      path: process.env.NODE_ENV === 'production' ? '.env.production' : '.env.development'
    });
    console.log('📄 Environment variables loaded from .env file');
  }
} catch (error) {
  // dotenv not available in production build - this is expected
  console.log('📄 Using system environment variables (dotenv not available)');
}

let win;
let authWin;
let promptEditorWin; // Add prompt editor panel window
let currentUser = null;
let jwtToken = null;
let isPinnedOnTop = false; // Default to normal window level
let isContentProtectionEnabled = true; // Default to enabled (secure)

// Audio transcription variables
let audioWebSocket = null;
let isAudioCapturing = false;
let audioContext = null;
let audioWorkletNode = null;
let mediaStreamSource = null;
let systemAudioStream = null;
let audioWsKeepaliveTimer = null;

// Backend URL configuration
// Use environment variable or fallback to ngrok URL for testing
const BACKEND_URL = process.env.BACKEND_URL || 'https://d87005d0505e.ngrok-free.app';

// Log environment configuration
console.log(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
console.log(`🔗 Backend URL: ${BACKEND_URL}`);
const SERVICE_NAME = 'Cluemore';
const ACCOUNT_NAME = 'user_jwt_token';

// Helper function to make HTTP/HTTPS requests
function makeRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    console.log(`Making request to: ${url}`);
    const urlObj = new URL(url);
    const isHttps = urlObj.protocol === 'https:';

    const requestOptions = {
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 3000),
      path: urlObj.pathname + urlObj.search,
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Cluemore/1.0.0',
        ...options.headers
      },
      // For HTTPS requests, ensure we handle certificates properly
      rejectUnauthorized: true,
      timeout: 30000 // 30 second timeout
    };

    console.log(`Request options:`, requestOptions);

    const client = isHttps ? https : http;
    const req = client.request(requestOptions, (res) => {
      console.log(`Response status: ${res.statusCode}`);
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        console.log(`Response data: ${data}`);
        try {
          const jsonData = JSON.parse(data);
          resolve(jsonData);
        } catch (error) {
          console.error('JSON parse error:', error);
          resolve({ error: 'Invalid JSON response', data, statusCode: res.statusCode });
        }
      });
    });

    req.on('error', (error) => {
      console.error('Request error:', error);
      reject(error);
    });

    req.on('timeout', () => {
      console.error('Request timeout');
      req.destroy();
      reject(new Error('Request timeout'));
    });

    if (options.body) {
      const bodyString = JSON.stringify(options.body);
      console.log(`Request body: ${bodyString}`);
      try {
        // Ensure Content-Length is set for WSGI backends behind ASGI bridge
        req.setHeader('Content-Length', Buffer.byteLength(bodyString));
      } catch (e) {
        console.warn('Failed to set Content-Length header:', e);
      }
      req.write(bodyString);
    }

    req.end();
  });
}

// Authentication helper functions
async function storeToken(token) {
  try {
    // Use permission dialog manager in case keychain access triggers a dialog
    await permissionDialogManager.handleSystemDialog(async () => {
      await keytar.setPassword(SERVICE_NAME, ACCOUNT_NAME, token);
      return true;
    }, 'keychain-store');

    jwtToken = token;
    console.log('JWT token stored securely');
    return true;
  } catch (error) {
    console.error('Failed to store token:', error);
    return false;
  }
}

async function getStoredToken() {
  try {
    // Use permission dialog manager in case keychain access triggers a dialog
    const token = await permissionDialogManager.handleSystemDialog(async () => {
      return await keytar.getPassword(SERVICE_NAME, ACCOUNT_NAME);
    }, 'keychain-retrieve');

    if (token) {
      jwtToken = token;
      console.log('JWT token retrieved from secure storage');
      return token;
    }
    return null;
  } catch (error) {
    console.error('Failed to retrieve token:', error);
    return null;
  }
}

async function removeStoredToken() {
  try {
    // Use permission dialog manager in case keychain access triggers a dialog
    await permissionDialogManager.handleSystemDialog(async () => {
      await keytar.deletePassword(SERVICE_NAME, ACCOUNT_NAME);
      return true;
    }, 'keychain-delete');

    jwtToken = null;
    currentUser = null;
    console.log('JWT token removed from secure storage');
    return true;
  } catch (error) {
    console.error('Failed to remove token:', error);
    return false;
  }
}

async function verifyStoredToken() {
  try {
    if (!jwtToken) {
      jwtToken = await getStoredToken();
    }

    if (!jwtToken) {
      console.log('No stored token found');
      return false;
    }

    const response = await makeRequest(`${BACKEND_URL}/api/auth/verify`, {
      method: 'POST',
      body: { token: jwtToken }
    });

    if (response.success && response.valid) {
      currentUser = response.user;
      console.log('Token verified, user:', currentUser.email);
      return true;
    } else {
      console.log('Token verification failed, removing stored token');
      await removeStoredToken();
      return false;
    }
  } catch (error) {
    console.error('Token verification error:', error);
    await removeStoredToken();
    return false;
  }
}

async function authenticateUser(email, password) {
  try {
    const response = await makeRequest(`${BACKEND_URL}/api/auth/login`, {
      method: 'POST',
      body: { email, password }
    });

    if (response.success && response.token) {
      await storeToken(response.token);
      currentUser = response.user;
      console.log('User authenticated successfully:', currentUser.email);
      return { success: true, user: currentUser, token: response.token };
    } else {
      console.log('Authentication failed:', response.error);
      return { success: false, error: response.error || 'Authentication failed' };
    }
  } catch (error) {
    console.error('Authentication error:', error);
    return { success: false, error: 'Network error: ' + error.message };
  }
}

async function registerUser(email, password) {
  try {
    const response = await makeRequest(`${BACKEND_URL}/api/auth/register`, {
      method: 'POST',
      body: { email, password }
    });

    if (response.success && response.token) {
      await storeToken(response.token);
      currentUser = response.user;
      console.log('User registered successfully:', currentUser.email);
      return { success: true, user: currentUser, token: response.token };
    } else {
      console.log('Registration failed:', response.error);
      return { success: false, error: response.error || 'Registration failed' };
    }
  } catch (error) {
    console.error('Registration error:', error);
    return { success: false, error: 'Network error: ' + error.message };
  }
}

// Setting management functions
function getPinOnTopSetting() {
  try {
    const fs = require('fs');
    const path = require('path');
    const userDataPath = app.getPath('userData');
    const settingsPath = path.join(userDataPath, 'settings.json');

    if (fs.existsSync(settingsPath)) {
      const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
      return settings.pinOnTop || false;
    }
  } catch (error) {
    console.error('Error reading pin setting:', error);
  }
  return false; // Default to false (normal level)
}

function setPinOnTopSetting(enabled) {
  try {
    const fs = require('fs');
    const path = require('path');
    const userDataPath = app.getPath('userData');
    const settingsPath = path.join(userDataPath, 'settings.json');

    let settings = {};
    if (fs.existsSync(settingsPath)) {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    }

    settings.pinOnTop = enabled;
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));

    console.log(`📌 Pin on top setting saved: ${enabled}`);
  } catch (error) {
    console.error('Error saving pin setting:', error);
  }
}

// Content protection setting management functions
function getContentProtectionSetting() {
  try {
    const fs = require('fs');
    const path = require('path');
    const userDataPath = app.getPath('userData');
    const settingsPath = path.join(userDataPath, 'settings.json');

    if (fs.existsSync(settingsPath)) {
      const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
      return settings.contentProtection !== undefined ? settings.contentProtection : true; // Default to enabled
    }
  } catch (error) {
    console.error('Error reading content protection setting:', error);
  }
  return true; // Default to enabled (secure)
}

function setContentProtectionSetting(enabled) {
  try {
    const fs = require('fs');
    const path = require('path');
    const userDataPath = app.getPath('userData');
    const settingsPath = path.join(userDataPath, 'settings.json');

    let settings = {};
    if (fs.existsSync(settingsPath)) {
      settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
    }

    settings.contentProtection = enabled;
    fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));

    console.log(`🔒 Content protection setting saved: ${enabled}`);
  } catch (error) {
    console.error('Error saving content protection setting:', error);
  }
}

// Function to toggle pin on top for all windows
function togglePinOnTop(enabled) {
  isPinnedOnTop = enabled;
  setPinOnTopSetting(enabled);

  console.log(`📌 ${enabled ? 'Pinning' : 'Unpinning'} all windows...`);

  // Apply to all existing windows
  if (win && !win.isDestroyed()) {
    if (enabled) {
      win.setAlwaysOnTop(true, 'screen-saver');
    } else {
      win.setAlwaysOnTop(false);
    }
  }

  if (authWin && !authWin.isDestroyed()) {
    if (enabled) {
      authWin.setAlwaysOnTop(true, 'screen-saver');
    } else {
      authWin.setAlwaysOnTop(false);
    }
  }

  if (promptEditorWin && !promptEditorWin.isDestroyed()) {
    if (enabled) {
      promptEditorWin.setAlwaysOnTop(true, 'screen-saver');
    } else {
      promptEditorWin.setAlwaysOnTop(false);
    }
  }
}

// Function to toggle content protection for all windows
function toggleContentProtection(enabled) {
  isContentProtectionEnabled = enabled;
  setContentProtectionSetting(enabled);

  console.log(`🔒 ${enabled ? 'Enabling' : 'Disabling'} content protection for all windows...`);

  // Apply to all existing windows
  if (win && !win.isDestroyed()) {
    win.setContentProtection(enabled);
  }

  if (authWin && !authWin.isDestroyed()) {
    authWin.setContentProtection(enabled);
  }

  if (promptEditorWin && !promptEditorWin.isDestroyed()) {
    promptEditorWin.setContentProtection(enabled);
  }

  // Notify user about the change
  const message = enabled
    ? '🔒 Content protection enabled - app is now invisible to screen sharing'
    : '📱 Content protection disabled - app is now visible to screen sharing';

  console.log(message);

  // Send notification to the renderer if main window exists
  if (win && !win.isDestroyed()) {
    win.webContents.send('content-protection-changed', { enabled, message });
  }
}

// Enhanced Permission Dialog Manager
class PermissionDialogManager {
  constructor() {
    this.isDialogActive = false;
    this.originalWindowStates = new Map();
    this.restoreTimeout = null;
    this.maxWaitTime = 30000; // 30 seconds max wait
    this.dialogCheckInterval = null;
  }

  // Save current window states before lowering
  saveWindowStates() {
    this.originalWindowStates.clear();

    if (win && !win.isDestroyed()) {
      this.originalWindowStates.set('main', {
        window: win,
        isAlwaysOnTop: win.isAlwaysOnTop(),
        isVisible: win.isVisible()
      });
    }

    if (authWin && !authWin.isDestroyed()) {
      this.originalWindowStates.set('auth', {
        window: authWin,
        isAlwaysOnTop: authWin.isAlwaysOnTop(),
        isVisible: authWin.isVisible()
      });
    }

    if (promptEditorWin && !promptEditorWin.isDestroyed()) {
      this.originalWindowStates.set('editor', {
        window: promptEditorWin,
        isAlwaysOnTop: promptEditorWin.isAlwaysOnTop(),
        isVisible: promptEditorWin.isVisible()
      });
    }

    console.log('🔒 Saved window states:', Array.from(this.originalWindowStates.keys()));
  }

    // Temporarily lower all windows to normal level for system dialogs
  async lowerAllWindowsForDialog(dialogType = 'permission') {
    if (this.isDialogActive) {
      console.log('🔄 Dialog already active, skipping lower operation');
      return;
    }

    console.log(`🔽 Lowering all windows for ${dialogType} dialog...`);
    this.isDialogActive = true;
    
    // Save current states
    this.saveWindowStates();
    
    // Check if we have any windows to manage
    if (this.originalWindowStates.size === 0) {
      console.log('🔽 No existing windows to lower - this is likely a startup permission request');
    } else {
      // Lower all windows to normal level
      for (const [key, state] of this.originalWindowStates) {
        if (state.window && !state.window.isDestroyed()) {
          try {
            state.window.setAlwaysOnTop(false);
            console.log(`🔽 Lowered ${key} window to normal level`);
          } catch (error) {
            console.error(`Error lowering ${key} window:`, error);
          }
        }
      }
    }

    // Small delay to ensure windows are lowered before dialog appears
    await new Promise(resolve => setTimeout(resolve, 150));
  }

    // Restore all windows to their original states after dialog is dismissed
  async restoreAllWindowsAfterDialog(forceDelay = 0) {
    if (!this.isDialogActive) {
      console.log('🔼 No active dialog, skipping restore operation');
      return;
    }

    console.log('🔼 Restoring window levels after dialog dismissal...');
    
    // Clear any existing restore timeout
    if (this.restoreTimeout) {
      clearTimeout(this.restoreTimeout);
      this.restoreTimeout = null;
    }

    // Wait for dialog to be fully dismissed
    // Use longer delay for permission dialogs to ensure they're fully dismissed
    const waitTime = Math.max(forceDelay, 500);
    console.log(`⏳ Waiting ${waitTime}ms for dialog dismissal...`);
    await new Promise(resolve => setTimeout(resolve, waitTime));

    // Restore windows based on current pin setting and original states
    for (const [key, state] of this.originalWindowStates) {
      if (state.window && !state.window.isDestroyed()) {
        try {
          // Only restore to pinned state if:
          // 1. Pin setting is currently enabled, AND
          // 2. Window was originally visible (don't pin hidden windows)
          if (isPinnedOnTop && state.isVisible) {
            state.window.setAlwaysOnTop(true, 'screen-saver');
            console.log(`🔼 Restored ${key} window to screen-saver level`);
          } else {
            state.window.setAlwaysOnTop(false);
            console.log(`🔼 Kept ${key} window at normal level`);
          }
        } catch (error) {
          console.error(`Error restoring ${key} window:`, error);
        }
      }
    }

    this.isDialogActive = false;
    this.originalWindowStates.clear();
    console.log('✅ Window restoration complete');
  }

  // Enhanced function to handle any system permission dialog
  async handleSystemDialog(operation, dialogType = 'permission') {
    console.log(`🔐 Handling ${dialogType} dialog for operation:`, operation.name || 'anonymous');

    try {
      // STEP 1: Lower all windows before system dialog
      await this.lowerAllWindowsForDialog(dialogType);

      // STEP 2: Check if this is likely to trigger a permission dialog
      const isPermissionRequest = dialogType.includes('screen-recording') && process.platform === 'darwin';

      if (isPermissionRequest) {
        // For screen recording permission, handle the async dialog properly
        return await this.handleScreenRecordingPermission(operation);
      } else {
        // STEP 3: Execute the operation that triggers the dialog
        const result = await operation();

        // STEP 4: Restore windows after operation completes
        await this.restoreAllWindowsAfterDialog();

        return result;
      }
    } catch (error) {
      console.error(`Error in ${dialogType} dialog handling:`, error);

      // STEP 5: Ensure windows are restored even if operation fails
      await this.restoreAllWindowsAfterDialog();

      throw error;
    }
  }

    // Special handling for screen recording permission which has async dialog behavior
  async handleScreenRecordingPermission(operation) {
    console.log('🔐 Special handling for screen recording permission dialog');
    
    // Check initial permission status
    const initialStatus = systemPreferences.getMediaAccessStatus('screen');
    console.log(`📺 Initial screen recording status: ${initialStatus}`);
    
    if (initialStatus === 'granted') {
      console.log('📺 Permission already granted, executing operation directly');
      const result = await operation();
      await this.restoreAllWindowsAfterDialog();
      return result;
    }

    // Permission not granted - this will likely trigger a dialog
    console.log('📺 Permission not granted, expecting system dialog to appear...');
    
    let operationResult = null;
    let operationError = null;

    // Execute the operation (which will fail but trigger the dialog)
    try {
      operationResult = await operation();
    } catch (error) {
      operationError = error;
      console.log('📺 Operation failed as expected, system dialog should appear soon...');
    }

    // Wait for the system permission dialog to appear and be handled
    console.log('⏳ Waiting for system permission dialog to be handled...');
    const dialogHandled = await this.waitForPermissionDialogCompletion('screen', initialStatus);
    
    if (dialogHandled) {
      console.log('✅ Permission dialog was handled by user');
      
      // Try the operation again if it failed initially
      if (operationError) {
        console.log('🔄 Retrying operation after permission grant...');
        try {
          operationResult = await operation();
          operationError = null;
        } catch (retryError) {
          console.log('❌ Operation still failed after permission dialog');
          operationError = retryError;
        }
      }
    } else {
      console.log('⏰ Timeout waiting for permission dialog');
    }

    // Restore windows after dialog is handled (only if we have windows to restore)
    if (this.originalWindowStates.size > 0) {
      await this.restoreAllWindowsAfterDialog();
    } else {
      console.log('🔼 No windows to restore (startup mode)');
      this.isDialogActive = false;
      this.originalWindowStates.clear();
    }

    // Return result or throw error
    if (operationError) {
      throw operationError;
    }
    return operationResult;
  }

  // Wait for permission dialog to be completed by polling permission status
  async waitForPermissionDialogCompletion(permissionType, initialStatus, maxWaitMs = 30000) {
    const startTime = Date.now();
    const pollInterval = 500; // Check every 500ms

    console.log(`⏳ Polling for ${permissionType} permission status change...`);

    while (Date.now() - startTime < maxWaitMs) {
      await new Promise(resolve => setTimeout(resolve, pollInterval));

      const currentStatus = systemPreferences.getMediaAccessStatus(permissionType);

      if (currentStatus !== initialStatus) {
        console.log(`📺 Permission status changed: ${initialStatus} → ${currentStatus}`);

        // Wait a bit more for dialog to fully dismiss
        await new Promise(resolve => setTimeout(resolve, 1000));
        return true;
      }

      // Log every 5 seconds to show we're still waiting
      if ((Date.now() - startTime) % 5000 < pollInterval) {
        console.log(`⏳ Still waiting for permission dialog (${Math.round((Date.now() - startTime) / 1000)}s)...`);
      }
    }

    console.log(`⏰ Timeout after ${maxWaitMs}ms waiting for permission dialog`);
    return false;
  }

  // Safety mechanism to restore windows if they get stuck
  enableSafetyRestore() {
    if (this.restoreTimeout) {
      clearTimeout(this.restoreTimeout);
    }

    // Auto-restore after max wait time as safety measure
    this.restoreTimeout = setTimeout(async () => {
      if (this.isDialogActive) {
        console.log('⚠️ Safety timeout reached, force-restoring windows');
        await this.restoreAllWindowsAfterDialog(100);
      }
    }, this.maxWaitTime);
  }

  // Clean up any active dialogs and restore windows
  async emergencyRestore() {
    console.log('🚨 Emergency window restore triggered');
    if (this.restoreTimeout) {
      clearTimeout(this.restoreTimeout);
      this.restoreTimeout = null;
    }

    this.isDialogActive = false;
    await this.restoreAllWindowsAfterDialog(0);
  }
}

// Create global permission dialog manager instance
const permissionDialogManager = new PermissionDialogManager();

// Helper functions for managing window levels during permission requests
async function temporarilyLowerAllWindows() {
  // Use the enhanced permission dialog manager
  return await permissionDialogManager.lowerAllWindowsForDialog('legacy');
}

async function restoreAllWindowLevels() {
  // Use the enhanced permission dialog manager
  return await permissionDialogManager.restoreAllWindowsAfterDialog();
}

// Permission request functions for macOS
async function requestAllPermissions(isStartup = false) {
  if (process.platform !== 'darwin') {
    console.log('⏭️ Permission requests only needed on macOS');
    return true;
  }

  console.log(`🔐 Requesting necessary permissions... ${isStartup ? '(startup)' : '(runtime)'}`);
  
  try {
    // Request Screen Recording permission (required for screenshot functionality)
    const screenAccess = systemPreferences.getMediaAccessStatus('screen');
    console.log(`📺 Screen recording access status: ${screenAccess}`);
    
    if (screenAccess !== 'granted') {
      console.log('📺 Requesting screen recording permission...');

      // Use enhanced permission dialog manager with startup flag
      const dialogType = isStartup ? 'screen-recording-startup' : 'screen-recording';
      await permissionDialogManager.handleSystemDialog(async () => {
        return await desktopCapturer.getSources({ 
          types: ['screen'], 
          thumbnailSize: { width: 150, height: 150 } 
        });
      }, dialogType);
    }

    // Test keychain access (required for secure token storage)
    // Note: We'll test this when we actually need to store/retrieve tokens
    console.log('🔑 Keychain access will be tested when needed (during authentication)');

    console.log('✅ Permission requests completed');
    return true;
  } catch (error) {
    console.error('❌ Error requesting permissions:', error);
    return false;
  }
}



// Function to check current permission status
function checkPermissionStatus() {
  if (process.platform !== 'darwin') {
    return { allGranted: true, permissions: {} };
  }

  const permissions = {
    screen: systemPreferences.getMediaAccessStatus('screen')
  };

  const allGranted = Object.values(permissions).every(status => status === 'granted');

  console.log('🔍 Current permission status:', permissions);
  
  return { allGranted, permissions };
}

function createAuthWindow() {
  const windowOptions = {
    width: 500,
    height: 700,
    resizable: false,
    alwaysOnTop: false, // Default to normal level
    title: 'Cluemore - Login',
    transparent: true,
    frame: false,
    show: false,
    focusable: true,  // Allow keyboard input
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js')
    }
  };

  // Use non-activating panel on macOS to prevent focus stealing for ALL interactions
  if (process.platform === 'darwin') {
    windowOptions.type = 'panel';  // Makes entire window non-activating
  }

  authWin = new BrowserWindow(windowOptions);

  authWin.setContentProtection(isContentProtectionEnabled);

  // Only pin on top if setting is enabled
  if (isPinnedOnTop) {
    authWin.setAlwaysOnTop(true, 'screen-saver');
  }

  authWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  authWin.setFullScreenable(false);

  authWin.loadFile('auth.html');
  authWin.once('ready-to-show', () => {
    authWin.setOpacity(1.0);
    // Use showInactive() to prevent focus stealing
    authWin.showInactive();
    
    // On macOS with panel type, we can focus webContents without activating the app
    if (process.platform === 'darwin' && windowOptions.type === 'panel') {
      authWin.webContents.focus();
    }
  });

  authWin.on('closed', () => {
    authWin = null;
  });
}

function createMainWindow() {
  if (win) {
    // Use showInactive() to prevent focus stealing
    win.showInactive();
    return;
  }

  const windowOptions = {
    width: 950,
    height: 700,
    resizable: false,
    alwaysOnTop: false, // Default to normal level
    title: 'Cluemore',
    skipTaskbar: true,
    transparent: true,
    frame: false,
    show: false,
    focusable: true,  // Allow keyboard input
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true,
      enableBlinkFeatures: 'GetDisplayMedia'  // Explicitly enable getDisplayMedia
    }
  };

  // Use non-activating panel on macOS to prevent focus stealing for ALL interactions
  if (process.platform === 'darwin') {
    windowOptions.type = 'panel';  // Makes entire window non-activating
  }

  win = new BrowserWindow(windowOptions);

  win.setContentProtection(isContentProtectionEnabled);

  // Only pin on top if setting is enabled
  if (isPinnedOnTop) {
    win.setAlwaysOnTop(true, 'screen-saver');
  }

  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.setFullScreenable(false);

  win.loadFile('index.html');
  win.once('ready-to-show', () => {
    win.setOpacity(1.0);
    // Use showInactive() to prevent focus stealing
    win.showInactive();
    
    // On macOS with panel type, we can focus webContents without activating the app
    if (process.platform === 'darwin' && windowOptions.type === 'panel') {
      win.webContents.focus();
    }
  });

  win.on('closed', () => {
    win = null;
  });
}

// Create non-activating panel for prompt editing (macOS only)
function createPromptEditorPanel() {
  // Only use panel type on macOS to prevent focus stealing
  const windowOptions = {
    width: 700,
    height: 550,
    frame: false,
    resizable: false,
    transparent: true,
    alwaysOnTop: false, // Default to normal level
    focusable: true,          // must be true to receive keys
    skipTaskbar: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js')
    }
  };

  // Use non-activating panel on macOS to prevent focus stealing
  if (process.platform === 'darwin') {
    windowOptions.type = 'panel';  // Maps to NSNonActivatingPanelMask
  }

  promptEditorWin = new BrowserWindow(windowOptions);

  promptEditorWin.setContentProtection(isContentProtectionEnabled);

  promptEditorWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  promptEditorWin.setFullScreenable(false);

  // Only pin on top if setting is enabled
  if (isPinnedOnTop) {
    promptEditorWin.setAlwaysOnTop(true, 'screen-saver');
  }

  promptEditorWin.loadFile('prompt-editor.html');

  promptEditorWin.on('closed', () => {
    promptEditorWin = null;
  });

  return promptEditorWin;
}

// Chat function with streaming support
async function sendChatMessage(text, imageData = null, model = 'gemini-2.5-flash', chatHistory = [], customPrompt = null, reasoning = 'low', verbosity = 'medium') {
  try {
    console.log('Sending streaming chat message - Text:', !!text, 'Image:', !!imageData, 'Model:', model, 'History length:', chatHistory.length);
    console.log('Custom prompt:', customPrompt ? customPrompt.substring(0, 100) + '...' : 'None (using default)');
    console.log('GPT-5 Settings - Reasoning:', reasoning, 'Verbosity:', verbosity);

    const payload = {};
    if (text) payload.text = text;
    if (imageData) payload.image = imageData;
    payload.model = model;
    payload.chatHistory = chatHistory;
    payload.customPrompt = customPrompt;
    payload.reasoning = reasoning;
    payload.verbosity = verbosity;

    // Use streaming endpoint
    const response = await fetch(`${BACKEND_URL}/api/chat_protected_stream`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    console.log('Starting to read streaming chat response...');
    
    // Signal start of streaming
    win.webContents.send('chat-stream-start');
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.chunk) {
                // Send chunk to renderer
                win.webContents.send('chat-stream-chunk', data.chunk);
              } else if (data.complete) {
                // Streaming completed
                win.webContents.send('chat-stream-complete');
                console.log('Chat streaming completed successfully');
                return;
              } else if (data.error) {
                // Error occurred
                win.webContents.send('chat-error', data.error);
                console.error('Chat streaming error:', data.error);
                return;
              }
            } catch (parseError) {
              console.error('Error parsing streaming data:', parseError);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

  } catch (error) {
    console.error('Chat streaming error:', error);
    win.webContents.send('chat-error', error.message);
  }
}

// Screenshot function
async function takeScreenshot(forChat = false) {
  try {
    console.log('Taking screenshot...', forChat ? 'for chat' : 'for analysis');

    // Check screen recording permission first (macOS only)
    if (process.platform === 'darwin') {
      const screenAccess = systemPreferences.getMediaAccessStatus('screen');
      console.log(`📺 Screen recording permission status: ${screenAccess}`);
      
      if (screenAccess !== 'granted') {
        console.log('📺 Screen recording permission required, attempting to request...');

        try {
          // Use enhanced permission dialog manager for screenshot permission request
          await permissionDialogManager.handleSystemDialog(async () => {
            return await desktopCapturer.getSources({
              types: ['screen'],
              thumbnailSize: { width: 150, height: 150 }
            });
          }, 'screen-recording-screenshot');

          // Check permission status again after potential grant
          const newScreenAccess = systemPreferences.getMediaAccessStatus('screen');
          if (newScreenAccess !== 'granted') {
            const errorMessage = `🔐 Screen Recording Permission Required\n\nTo capture screenshots, Cluemore needs screen recording permission.\n\n📝 How to fix:\n1. Open System Preferences > Security & Privacy\n2. Click the "Privacy" tab\n3. Select "Screen Recording" from the left sidebar\n4. Check the box next to "Cluemore"\n5. Restart Cluemore if needed\n\nPermission status: ${newScreenAccess}`;

            console.error('Screen recording permission still not granted after request:', newScreenAccess);

            if (forChat) {
              win.webContents.send('chat-error', errorMessage);
            } else {
              win.webContents.send('screenshot-error', errorMessage);
            }
            return;
          }
          console.log('📺 Screen recording permission granted after request');
        } catch (permissionError) {
          console.error('Error requesting screen recording permission:', permissionError);
          const errorMessage = `🔐 Permission Request Failed\n\nUnable to request screen recording permission. Please manually grant it in System Preferences.\n\nError: ${permissionError.message}`;

          if (forChat) {
            win.webContents.send('chat-error', errorMessage);
          } else {
            win.webContents.send('screenshot-error', errorMessage);
          }
          return;
        }
      }
    }

    // Get all available sources (screens) with smaller thumbnail for faster processing
    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width: 1280, height: 720 }  // Reduced size for faster processing
    });

    if (sources.length === 0) {
      const errorMessage = '📺 No screens found for capture. Please ensure your display is active and try again.';
      console.error('No screens found');
      
      if (forChat) {
        win.webContents.send('chat-error', errorMessage);
      } else {
        win.webContents.send('screenshot-error', errorMessage);
      }
      return;
    }

    // Use the first screen (primary display)
    const primaryScreen = sources[0];
    const screenshot = primaryScreen.thumbnail;

    // Convert to base64
    const base64Data = screenshot.toPNG().toString('base64');
    console.log(`Screenshot captured successfully, size: ${base64Data.length} characters`);

    if (forChat) {
      // Send screenshot data to chat interface
      console.log('Sending screenshot to chat interface');
      win.webContents.send('chat-screenshot-captured', base64Data);
      return;
    }

    // Send screenshot to LeetCode Helper for accumulation
    console.log('Sending screenshot to LeetCode Helper for accumulation');
    win.webContents.send('leetcode-screenshot-captured', base64Data);

  } catch (error) {
    console.error('Screenshot error:', error);
    console.error('Error details:', error.message);
    
    // Provide user-friendly error messages based on the error type
    let userFriendlyMessage = '';
    
    if (error.message.includes('getDisplayMedia') || error.message.includes('Screen Capture')) {
      userFriendlyMessage = `🔐 Screen Recording Permission Issue\n\nCluemore couldn't capture your screen. This usually means screen recording permission is missing or restricted.\n\n📝 Please:\n1. Grant screen recording permission in System Preferences\n2. Restart Cluemore\n3. Try taking a screenshot again\n\nTechnical error: ${error.message}`;
    } else if (error.message.includes('timeout') || error.message.includes('network')) {
      userFriendlyMessage = `⏱️ Screenshot Timeout\n\nThe screenshot operation timed out. This might happen if your system is under heavy load.\n\n📝 Please try again in a moment.\n\nTechnical error: ${error.message}`;
    } else {
      userFriendlyMessage = `❌ Screenshot Failed\n\nSomething went wrong while capturing your screen.\n\n📝 Please:\n1. Check that Cluemore has screen recording permission\n2. Try again in a moment\n3. Restart Cluemore if the issue persists\n\nTechnical error: ${error.message}`;
    }
    
    if (forChat) {
      win.webContents.send('chat-error', userFriendlyMessage);
    } else {
      win.webContents.send('screenshot-error', userFriendlyMessage);
    }
  }
}

// Process accumulated screenshots with streaming
async function processAccumulatedScreenshots(screenshots, model = 'gemini-2.5-flash', customPrompt = null, reasoning = 'low', verbosity = 'medium') {
  try {
    console.log('Processing accumulated screenshots with streaming:', screenshots.length, 'Model:', model);
    console.log('Custom prompt:', customPrompt ? customPrompt.substring(0, 100) + '...' : 'None (using default)');
    console.log('GPT-5 Settings - Reasoning:', reasoning, 'Verbosity:', verbosity);

    const payload = {
      images: screenshots,
      model: model,
      customPrompt: customPrompt,
      reasoning: reasoning,
      verbosity: verbosity
    };

    // Use streaming endpoint
    const response = await fetch(`${BACKEND_URL}/api/screenshot_protected_stream`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    console.log('Starting to read streaming screenshot response...');
    
    // Signal start of streaming
    win.webContents.send('screenshot-stream-start');
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.chunk) {
                // Send chunk to renderer
                win.webContents.send('screenshot-stream-chunk', data.chunk);
              } else if (data.complete) {
                // Streaming completed
                win.webContents.send('screenshot-stream-complete');
                console.log('Screenshot streaming completed successfully');
                return;
              } else if (data.error) {
                // Error occurred
                win.webContents.send('screenshot-error', data.error);
                console.error('Screenshot streaming error:', data.error);
                return;
              }
            } catch (parseError) {
              console.error('Error parsing streaming data:', parseError);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

  } catch (error) {
    console.error('Screenshot streaming error:', error);
    console.error('Error details:', error.message);
    win.webContents.send('screenshot-error', error.message);
  }
}

// Manual update checker setup
function setupAutoUpdater() {
  console.log('🔧 Setting up manual update checking');
  
  // Configure GitHub provider
  autoUpdater.setFeedURL({
    provider: 'github',
    owner: 'yatharthsameer',
    repo: 'cluemore',
    private: false,
    releaseType: 'release'
  });

  // Enable automatic download and install when manually triggered
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  // Update available - automatically download
  autoUpdater.on('update-available', (info) => {
    const currentVersion = app.getVersion();
    const availableVersion = info.version;
    
    // Normalize versions for comparison (remove 'v' prefix if present)
    const normalizeVersion = (v) => v.replace(/^v/, '');
    const currentNormalized = normalizeVersion(currentVersion);
    const availableNormalized = normalizeVersion(availableVersion);

    console.log('🔄 Update available!');
    console.log(`   Current: ${currentVersion}, Available: ${availableVersion}`);

    // Check if this is actually a newer version
    if (currentNormalized === availableNormalized) {
      console.log('⚠️ Same version detected, skipping download');
      if (win && !win.isDestroyed()) {
        win.webContents.send('update-notification', {
          type: 'up-to-date',
          version: currentVersion,
          message: 'You are running the latest version!'
        });
      }
      return;
    }

    // Send download notification
    if (win && !win.isDestroyed()) {
      win.webContents.send('update-notification', {
        type: 'download-started',
        version: info.version,
        message: `Downloading update v${info.version}...`
      });
    }

    console.log(`📥 Starting download for v${info.version}...`);
  });

  // Download progress
  autoUpdater.on('download-progress', (progressObj) => {
    const percent = Math.round(progressObj.percent);
    const transferredMB = Math.round(progressObj.transferred / 1024 / 1024);
    const totalMB = Math.round(progressObj.total / 1024 / 1024);

    console.log(`📥 Download progress: ${percent}% (${transferredMB}MB / ${totalMB}MB)`);

    // Send progress to renderer
    if (win && !win.isDestroyed()) {
      win.webContents.send('update-progress', {
        percent: percent,
        transferred: progressObj.transferred,
        total: progressObj.total,
        bytesPerSecond: progressObj.bytesPerSecond
      });
    }
  });

  // Update downloaded - automatically install and restart
  autoUpdater.on('update-downloaded', (info) => {
    console.log('✅ Update downloaded:', info.version);
    console.log('🔄 Auto-installing update and restarting...');
    
    // Send notification to renderer
    if (win && !win.isDestroyed()) {
      win.webContents.send('update-notification', {
        type: 'installing',
        version: info.version,
        message: `Installing update v${info.version}... App will restart automatically.`
      });
    }

    // Give user a moment to see the notification, then restart
    setTimeout(() => {
      autoUpdater.quitAndInstall(false, true);
    }, 2000);
  });

  // Update not available
  autoUpdater.on('update-not-available', (info) => {
    console.log('✅ App is up to date!');
    if (win && !win.isDestroyed()) {
      win.webContents.send('update-notification', {
        type: 'up-to-date',
        version: info.version,
        message: 'You are running the latest version!'
      });
    }
  });

  // Error handling
  autoUpdater.on('error', (error) => {
    console.error('❌ Update error:', error.message);
    if (win && !win.isDestroyed()) {
      win.webContents.send('update-notification', {
        type: 'error',
        message: `Update failed: ${error.message}`
      });
    }
  });

  // Simple checking event
  autoUpdater.on('checking-for-update', () => {
    console.log('🔍 Checking for updates...');
  });

  console.log('✅ Manual update checking configured');
}

app.whenReady().then(async () => {
  console.log('🚀 App is ready, starting initialization...');

  // Set up display media request handler for proper system audio capture
  console.log('🎬 Setting up display media request handler...');
  try {
    session.defaultSession.setDisplayMediaRequestHandler((request, callback) => {
      console.log('🎬 Display media request received:', request);
      console.log('🎬 Request details - video:', request.video, 'audio:', request.audio);

      desktopCapturer.getSources({ types: ['screen', 'window'] }).then((sources) => {
        console.log('📺 Available sources:', sources.length);
        console.log('📺 Sources list:', sources.map(s => ({ id: s.id, name: s.name })));

        // Find the first screen source (preferred for system audio)
        const screenSource = sources.find(source => source.id.startsWith('screen:'));
        const sourceToUse = screenSource || sources[0];

        if (sourceToUse) {
          const response = {
            video: sourceToUse
          };

          // Add audio only if requested and we have a screen source
          if (request.audioRequested && screenSource) {
            response.audio = 'loopback';
            console.log('✅ Adding system audio (loopback) to response');
          } else if (request.audioRequested) {
            console.warn('⚠️ Audio requested but no screen source available for system audio');
          } else {
            console.log('🔇 No audio requested in this call');
          }

          console.log('✅ Calling callback with:', response);
          callback(response);
        } else {
          console.warn('⚠️ No sources available');
          callback({});
        }
      }).catch(error => {
        console.error('❌ Error getting desktop sources:', error);
        callback({});
      });
    }, {
      useSystemPicker: false  // Disable system picker to ensure our handler runs
    });
    console.log('✅ Display media request handler set up successfully');
  } catch (error) {
    console.error('❌ Failed to set up display media request handler:', error);
  }

  // Load pin on top setting
  isPinnedOnTop = getPinOnTopSetting();
  console.log(`📌 Pin on top setting loaded: ${isPinnedOnTop}`);

  // Load content protection setting
  isContentProtectionEnabled = getContentProtectionSetting();
  console.log(`🔒 Content protection setting loaded: ${isContentProtectionEnabled}`);

  // Request all necessary permissions upfront BEFORE creating any windows (macOS only)
  if (process.platform === 'darwin') {
    console.log('🚀 Starting permission request flow...');
    try {
      await requestAllPermissions(true); // Pass startup flag
      console.log('✅ Permission request flow completed');
    } catch (error) {
      console.error('❌ Permission request flow failed:', error);
      // Continue anyway - user can grant permissions later
    }
    
    // Additional delay to ensure all permission dialogs are fully settled
    console.log('⏳ Allowing time for permission dialogs to settle...');
    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  // Check if user is already authenticated
  const isAuthenticated = await verifyStoredToken();

  if (isAuthenticated) {
    console.log('User already authenticated, opening main app');
    createMainWindow();
  } else {
    console.log('No valid authentication, showing login');
    createAuthWindow();
  }

  // Setup manual update checking
  if (app.isPackaged) {
    console.log('✅ Setting up manual update checking...');
    setupAutoUpdater();
  }

  // Global shortcuts for window movement and hiding
  const moveStep = 50; // pixels to move per keypress

  // Helper function to get the currently active window
  function getActiveWindow() {
    if (win && win.isVisible()) {
      return win;
    } else if (authWin && authWin.isVisible()) {
      return authWin;
    }
    return null;
  }

  // Movement shortcuts: cmd + arrow keys
  globalShortcut.register('CommandOrControl+Left', () => {
    const activeWin = getActiveWindow();
    if (activeWin) {
      const [x, y] = activeWin.getPosition();
      activeWin.setPosition(Math.max(0, x - moveStep), y);
    }
  });

  globalShortcut.register('CommandOrControl+Right', () => {
    const activeWin = getActiveWindow();
    if (activeWin) {
      const [x, y] = activeWin.getPosition();
      const [width] = activeWin.getSize();
      const { width: screenWidth } = require('electron').screen.getPrimaryDisplay().workAreaSize;
      activeWin.setPosition(Math.min(screenWidth - width, x + moveStep), y);
    }
  });

  globalShortcut.register('CommandOrControl+Up', () => {
    const activeWin = getActiveWindow();
    if (activeWin) {
      const [x, y] = activeWin.getPosition();
      activeWin.setPosition(x, Math.max(0, y - moveStep));
    }
  });

  globalShortcut.register('CommandOrControl+Down', () => {
    const activeWin = getActiveWindow();
    if (activeWin) {
      const [x, y] = activeWin.getPosition();
      const [, height] = activeWin.getSize();
      const { height: screenHeight } = require('electron').screen.getPrimaryDisplay().workAreaSize;
      activeWin.setPosition(x, Math.min(screenHeight - height, y + moveStep));
    }
  });

  // Auto-hide shortcut: cmd + 6 (STEALTH MODE - no focus stealing)
  globalShortcut.register('CommandOrControl+6', () => {
    // Try to show whichever window exists and is hidden WITHOUT stealing focus
    if (win && !win.isVisible()) {
      win.showInactive(); // Use showInactive() to prevent focus stealing
      // On macOS with panel type, focus webContents for keyboard input
      if (process.platform === 'darwin') {
        win.webContents.focus();
      }
    } else if (authWin && !authWin.isVisible()) {
      authWin.showInactive(); // Use showInactive() to prevent focus stealing
      // On macOS with panel type, focus webContents for keyboard input
      if (process.platform === 'darwin') {
        authWin.webContents.focus();
      }
    } else if (win && win.isVisible()) {
      win.hide();
    } else if (authWin && authWin.isVisible()) {
      authWin.hide();
    }
  });

  // Screenshot shortcut: cmd + shift + 1
  globalShortcut.register('CommandOrControl+Shift+1', async () => {
    console.log('Screenshot shortcut pressed');

    // Ask renderer which mode we're in and let it handle the screenshot
    if (win) {
      win.webContents.send('check-current-mode');
    }
  });

  // Global shortcut for Cmd+Enter: cmd + enter
  globalShortcut.register('CommandOrControl+Enter', async () => {
    console.log('Cmd+Enter shortcut pressed (global)');

    // Ask renderer to handle based on current mode
    if (win) {
      win.webContents.send('handle-cmd-enter');
    }
  });

  // Global shortcut for quick answer from transcription: cmd + shift + enter
  globalShortcut.register('CommandOrControl+Shift+Enter', async () => {
    console.log('Cmd+Shift+Enter shortcut pressed (quick answer from transcription)');

    // Ask renderer to generate quick answer from latest transcription
    if (win) {
      win.webContents.send('quick-answer-from-transcription');
    }
  });

  // Global shortcut for chat mode: cmd + shift + i (STEALTH MODE - no focus stealing)
  globalShortcut.register('CommandOrControl+Shift+I', async () => {
    console.log('Cmd+Shift+I shortcut pressed (global)');

    // Ensure window is visible WITHOUT stealing focus, then switch to chat mode
    if (win) {
      if (!win.isVisible()) {
        win.showInactive(); // Use showInactive() to prevent focus stealing
        // On macOS with panel type, focus webContents for keyboard input
        if (process.platform === 'darwin') {
          win.webContents.focus();
        }
      }
      // Remove win.focus() call to prevent focus stealing
      win.webContents.send('switch-to-chat-mode');
    }
  });

  // Create tray with simple text-based icon
  let tray;
  try {
    // Create a simple text-based icon using nativeImage
    const iconSize = 16;
    const icon = nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(`
      <svg width="${iconSize}" height="${iconSize}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#4682B4"/>
        <text x="50%" y="50%" text-anchor="middle" dy=".3em" fill="white" font-family="Arial" font-size="12" font-weight="bold">C</text>
      </svg>
    `).toString('base64')}`);

    tray = new Tray(icon);
    console.log('✅ Tray icon created successfully');
  } catch (error) {
    console.log('Could not create tray icon, using empty icon');
    tray = new Tray(nativeImage.createEmpty());
  }

  if (tray) {
    tray.setContextMenu(Menu.buildFromTemplate([
      {
        label: 'Show / Hide', click: () => {
          if (win) {
            if (win.isVisible()) {
              win.hide();
            } else {
              win.showInactive(); // Use showInactive() to prevent focus stealing
              // On macOS with panel type, focus webContents for keyboard input
              if (process.platform === 'darwin') {
                win.webContents.focus();
              }
            }
          }
        }
      },
      { label: 'Take Screenshot', click: () => takeScreenshot() },
      { type: 'separator' },
      {
        label: 'Logout', click: async () => {
          await removeStoredToken();
          if (win) win.close();
          createAuthWindow();
        }
      },
      { label: 'Quit', click: () => app.quit() }
    ]));
  }

  // Authentication IPC Handlers
  ipcMain.handle('auth:login', async (event, email, password) => {
    return await authenticateUser(email, password);
  });

  ipcMain.handle('auth:register', async (event, email, password) => {
    return await registerUser(email, password);
  });

  ipcMain.handle('auth:logout', async (event) => {
    const success = await removeStoredToken();
    if (win) {
      win.close();
    }
    createAuthWindow();
    return { success };
  });

  ipcMain.handle('auth:verify-token', async (event, token) => {
    try {
      const response = await makeRequest(`${BACKEND_URL}/api/auth/verify`, {
        method: 'POST',
        body: { token }
      });
      return response;
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('auth:get-current-user', async (event) => {
    if (currentUser) {
      return { success: true, user: currentUser };
    } else {
      return { success: false, error: 'No authenticated user' };
    }
  });

  ipcMain.handle('auth:get-token', async (event) => {
    if (jwtToken) {
      return { success: true, token: jwtToken };
    } else {
      // Try to get from secure storage
      const storedToken = await getStoredToken();
      if (storedToken) {
        return { success: true, token: storedToken };
      } else {
        return { success: false, error: 'No auth token available' };
      }
    }
  });

  // App navigation IPC handlers
  ipcMain.handle('app:open-main', async (event) => {
    if (authWin) {
      authWin.close();
    }
    createMainWindow();
    return { success: true };
  });

  ipcMain.handle('app:open-auth', async (event) => {
    if (win) {
      win.close();
    }
    await removeStoredToken();
    createAuthWindow();
    return { success: true };
  });

  ipcMain.handle('app:get-backend-url', async (event) => {
    return { success: true, url: BACKEND_URL };
  });

  ipcMain.handle('app:get-version', async (event) => {
    return app.getVersion();
  });

  // Permission status IPC handler
  ipcMain.handle('permissions:check-status', async (event) => {
    return checkPermissionStatus();
  });

  ipcMain.handle('permissions:request-all', async (event) => {
    return await requestAllPermissions();
  });

  // Helper to re-request screen recording permission specifically
  ipcMain.handle('permissions:request-screen-recording', async (event) => {
    try {
      console.log('🔐 Re-requesting screen recording permission...');
      
      if (process.platform !== 'darwin') {
        return { success: true, message: 'Permission requests only needed on macOS' };
      }

      // Check current status
      const currentStatus = systemPreferences.getMediaAccessStatus('screen');
      console.log(`Current screen recording status: ${currentStatus}`);

      if (currentStatus === 'granted') {
        return { success: true, message: 'Screen recording permission already granted' };
      }

      // Use enhanced permission dialog manager for manual permission request
      await permissionDialogManager.handleSystemDialog(async () => {
        return await desktopCapturer.getSources({
          types: ['screen'],
          thumbnailSize: { width: 150, height: 150 }
        });
      }, 'manual-screen-recording');

      // Check status again after request
      const newStatus = systemPreferences.getMediaAccessStatus('screen');
      console.log(`New screen recording status: ${newStatus}`);

      if (newStatus === 'granted') {
        return {
          success: true,
          message: 'Screen recording permission granted! You can now take screenshots.'
        };
      } else {
        return {
          success: false,
          message: 'Please grant screen recording permission in System Preferences > Security & Privacy > Privacy > Screen Recording, then restart Cluemore.'
        };
      }
    } catch (error) {
      console.error('Error requesting screen recording permission:', error);
      return { 
        success: false, 
        message: 'Could not request permission. Please manually grant screen recording access in System Preferences.' 
      };
    }
  });

  // Manual update check IPC handler
  ipcMain.handle('updater:check-for-updates', async (event) => {
    if (!app.isPackaged) {
      return { success: false, error: 'Updates only available in packaged app' };
    }
    
    try {
      console.log('🔄 Checking for updates...');
      const result = await autoUpdater.checkForUpdates();
      
      if (result && result.updateInfo) {
        const currentVersion = app.getVersion();
        const availableVersion = result.updateInfo.version;
        
        // Normalize versions (remove 'v' prefix)
        const normalizeVersion = (v) => v.replace(/^v/, '');
        const currentNormalized = normalizeVersion(currentVersion);
        const availableNormalized = normalizeVersion(availableVersion);
        
        if (currentNormalized === availableNormalized) {
          return { success: true, updateInfo: null, message: 'You are running the latest version!' };
        }
        
        console.log(`📥 Update v${availableVersion} found, downloading...`);
        return { success: true, updateInfo: result.updateInfo, message: `Update v${availableVersion} found. Downloading automatically...` };
      } else {
        return { success: true, updateInfo: null, message: 'You are running the latest version!' };
      }
    } catch (error) {
      console.error('Update check failed:', error.message);
      return { success: false, error: error.message };
    }
  });



  // Existing IPC Handlers for chat functionality
  ipcMain.handle('chat:send-message', async (event, text, imageData, model, chatHistory, customPrompt, reasoning, verbosity) => {
    // Add JWT token to authenticated requests
    await sendChatMessage(text, imageData, model, chatHistory, customPrompt, reasoning, verbosity);
    return true;
  });

  // IPC Handler for screenshot mode detection
  ipcMain.handle('screenshot:take-for-mode', async (event, mode) => {
    if (mode === 'chat') {
      await takeScreenshot(true);
    } else {
      await takeScreenshot(false);
    }
    return true;
  });

  // IPC Handler for processing accumulated screenshots
  ipcMain.handle('screenshot:process-accumulated', async (event, screenshots, model, customPrompt, reasoning, verbosity) => {
    await processAccumulatedScreenshots(screenshots, model, customPrompt, reasoning, verbosity);
    return true;
  });

  // IPC Handler for setting window opacity
  ipcMain.handle('window:set-opacity', async (event, opacity) => {
    if (win && opacity >= 0.2 && opacity <= 1.0) {
      win.setOpacity(opacity);
      return true;
    }
    return false;
  });

  // IPC Handlers for pin on top functionality
  ipcMain.handle('window:get-pin-status', async (event) => {
    return { pinned: isPinnedOnTop };
  });

  ipcMain.handle('window:toggle-pin', async (event, enabled) => {
    togglePinOnTop(enabled);
    return { success: true, pinned: isPinnedOnTop };
  });

  // Emergency window restoration IPC handler
  ipcMain.handle('window:emergency-restore', async (event) => {
    try {
      console.log('🚨 Emergency window restoration requested from renderer');
      await permissionDialogManager.emergencyRestore();
      return { success: true, message: 'Windows restored to correct levels' };
    } catch (error) {
      console.error('Emergency restore failed:', error);
      return { success: false, error: error.message };
    }
  });

  // Content protection IPC handlers
  ipcMain.handle('window:get-content-protection-status', async (event) => {
    return { enabled: isContentProtectionEnabled };
  });

  ipcMain.handle('window:toggle-content-protection', async (event, enabled) => {
    try {
      console.log(`🔒 Content protection toggle requested from renderer: ${enabled}`);
      toggleContentProtection(enabled);
      return { success: true, enabled: isContentProtectionEnabled };
    } catch (error) {
      console.error('Content protection toggle failed:', error);
      return { success: false, error: error.message };
    }
  });

  // Prompt Editor IPC Handlers
  ipcMain.handle('prompt-editor:open', async (event, mode, currentPrompt) => {
    try {
      if (!promptEditorWin) {
        promptEditorWin = createPromptEditorPanel();
      }

      // Show the panel without activating the app
      promptEditorWin.showInactive();
      
      // On macOS with panel type, we can focus webContents without activating the app
      if (process.platform === 'darwin') {
        promptEditorWin.webContents.focus();
      }

      // Send initialization data to the panel
      promptEditorWin.webContents.send('prompt-editor:init', {
        mode: mode,
        prompt: currentPrompt
      });

      return { success: true };
    } catch (error) {
      console.error('Error opening prompt editor:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('prompt-editor:close', async (event) => {
    try {
      if (promptEditorWin) {
        promptEditorWin.hide();
      }
      return { success: true };
    } catch (error) {
      console.error('Error closing prompt editor:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('prompt-editor:save', async (event, mode, prompt) => {
    try {
      // Send the saved prompt back to the main window
      if (win) {
        win.webContents.send('prompt-editor:saved', { mode, prompt });
      }
      
      // Hide the panel
      if (promptEditorWin) {
        promptEditorWin.hide();
      }
      
      return { success: true };
    } catch (error) {
      console.error('Error saving prompt:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('prompt-editor:get-default', async (event, mode) => {
    try {
      // Define default prompts
      const defaultPrompts = {
        interview: `You are an AI assistant helping with coding interviews and technical challenges. 

When analyzing screenshots of coding problems:
1. Identify the problem type and requirements
2. Suggest an efficient approach or algorithm
3. Provide step-by-step solution guidance
4. Include time/space complexity analysis
5. Offer optimization tips if applicable

Keep responses concise but comprehensive, focusing on practical problem-solving strategies.`,
        chat: `You are a helpful, concise chat assistant (ChatGPT-style). Each turn may include:

image: one screenshot (UI, doc, chart, code, error)

text: the user's message

Do:

Read visible text, labels, buttons, charts, states; infer simple causes; note uncertainty if unreadable

Combine screenshot info with the user's text to answer directly, then suggest 1–2 next steps

Be brief, friendly, and accurate; use bullets or short paragraphs; quote UI labels exactly

For code/errors: give minimal, correct fixes in code blocks

For data/charts: report key numbers, units, and timeframe

Flag missing info and proceed with a best-effort answer

Don't:

Invent elements not visible

Perform web browsing or real clicks; give instructions instead

Share sensitive PII seen in the image; summarize instead

Safety:

No disallowed content; give general info (not professional advice) for medical/legal/financial topics

Final rule: be useful in one message—answer first, steps second.`
      };

      return { success: true, prompt: defaultPrompts[mode] || defaultPrompts.interview };
    } catch (error) {
      console.error('Error getting default prompt:', error);
      return { success: false, error: error.message };
    }
  });

  // Audio capture IPC handlers
  ipcMain.handle('audio:start-capture', async (event) => {
    try {
      if (isAudioCapturing) {
        return { success: false, error: 'Audio capture already running' };
      }

      // Connect to unified WebSocket endpoint on the same backend port
      const wsUrl = `${BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/ws/audio`;
      audioWebSocket = new WebSocket(wsUrl);

      audioWebSocket.on('open', () => {
        console.log('🔊 WebSocket connection established for audio transcription');
        isAudioCapturing = true;
        // Client-side keepalive: send ping frames every 20s
        try {
          if (audioWsKeepaliveTimer) clearInterval(audioWsKeepaliveTimer);
          audioWsKeepaliveTimer = setInterval(() => {
            if (audioWebSocket && audioWebSocket.readyState === WebSocket.OPEN) {
              try { audioWebSocket.ping(); } catch (err) { console.warn('WS ping error:', err?.message || err); }
            }
          }, 20000);
        } catch (e) {
          console.warn('Failed to start WS keepalive timer', e);
        }
        if (win) {
          win.webContents.send('transcription:start');
        }
      });

      audioWebSocket.on('message', (data) => {
        try {
          const message = JSON.parse(data.toString());
          if (win) {
            switch (message.type) {
              case 'transcript':
                win.webContents.send('transcription:final', message);
                break;
              case 'voice_activity':
                win.webContents.send('transcription:voice-activity', message);
                break;
              case 'turn_detection':
                win.webContents.send('transcription:turn-detection', message);
                break;
            }
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      });

      audioWebSocket.on('error', (error) => {
        console.error('WebSocket error:', error);
        if (win) {
          win.webContents.send('transcription:error', error.message);
        }
        isAudioCapturing = false;
      });

      audioWebSocket.on('close', (code, reason) => {
        console.log('WebSocket connection closed', code, reason?.toString?.());
        isAudioCapturing = false;
        if (audioWsKeepaliveTimer) { clearInterval(audioWsKeepaliveTimer); audioWsKeepaliveTimer = null; }
      });

      return { success: true };
    } catch (error) {
      console.error('Error starting audio capture:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('audio:stop-capture', async (event) => {
    try {
      if (audioWebSocket) {
        audioWebSocket.close();
        audioWebSocket = null;
      }
      isAudioCapturing = false;
      return { success: true };
    } catch (error) {
      console.error('Error stopping audio capture:', error);
      return { success: false, error: error.message };
    }
  });

  ipcMain.on('audio:chunk', (event, chunk) => {
    if (audioWebSocket && audioWebSocket.readyState === WebSocket.OPEN) {
      try {
        // The WebSocket server expects exactly 640 bytes (320 samples * 2 bytes)
        const targetSamples = 320; // 20ms @ 16kHz
        const pcmData = chunk.pcm;

        if (pcmData && pcmData.length > 0) {
          // PCM data comes as Int16Array from frontend, but may need reconstruction
          let processedData;

          // Convert PCM data to Int16Array (data comes as regular array from IPC)
          if (Array.isArray(pcmData)) {
            processedData = new Int16Array(pcmData);
          } else if (pcmData instanceof Int16Array) {
            processedData = pcmData;
          } else {
            console.warn('Unexpected PCM data format:', typeof pcmData, pcmData.constructor?.name);
            return;
          }

          // Ensure correct size
          if (processedData.length !== targetSamples) {
            const resized = new Int16Array(targetSamples);
            if (processedData.length > targetSamples) {
              // Truncate
              resized.set(processedData.subarray(0, targetSamples));
            } else {
              // Pad with zeros
              resized.set(processedData);
            }
            processedData = resized;
          }

          // Convert to Buffer (Node.js Buffer from ArrayBuffer)
          const buffer = Buffer.from(processedData.buffer, processedData.byteOffset, processedData.byteLength);
          audioWebSocket.send(buffer);

          // Debug logging
          if (Math.random() < 0.02) { // 2% of packets
            const maxSample = Math.max(...processedData.map(Math.abs));
            console.log(`Sent audio chunk: ${buffer.length} bytes, ${processedData.length} samples, max=${maxSample}`);
          }
        }
      } catch (error) {
        console.error('Error processing audio chunk:', error);
      }
    }
  });
  // Desktop capturer for fallback screen capture
  ipcMain.handle('desktop:get-sources', async () => {
    try {
      const sources = await desktopCapturer.getSources({
        types: ['screen', 'window'],
        thumbnailSize: { width: 150, height: 150 }
      });

      return sources.map(source => ({
        id: source.id,
        name: source.name,
        thumbnail: source.thumbnail.toDataURL()
      }));
    } catch (error) {
      console.error('Error getting desktop sources:', error);
      return [];
    }
  });
});

app.on('window-all-closed', () => { /* keep running in tray */ });

app.on('will-quit', async () => {
  // Ensure windows are restored before quitting
  try {
    await permissionDialogManager.emergencyRestore();
  } catch (error) {
    console.error('Error during app quit restoration:', error);
  }

  // Unregister all shortcuts
  globalShortcut.unregisterAll();
});

// Global error handling to ensure windows are restored
process.on('uncaughtException', async (error) => {
  console.error('🚨 Uncaught exception:', error);
  try {
    await permissionDialogManager.emergencyRestore();
  } catch (restoreError) {
    console.error('Error during emergency restore:', restoreError);
  }
  // Don't exit the process, just log the error
});

process.on('unhandledRejection', async (reason, promise) => {
  console.error('🚨 Unhandled rejection at:', promise, 'reason:', reason);
  try {
    await permissionDialogManager.emergencyRestore();
  } catch (restoreError) {
    console.error('Error during emergency restore:', restoreError);
  }
// Don't exit the process, just log the error
}); 