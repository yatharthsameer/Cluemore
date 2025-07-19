const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, desktopCapturer, ipcMain, systemPreferences, dialog } = require('electron');
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
// Backend URL configuration
// Use environment variable or fallback to production URL
const BACKEND_URL = process.env.BACKEND_URL || 'https://cluemore-166792667b90.herokuapp.com';

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
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname + urlObj.search,
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
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

  authWin.setContentProtection(true);

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
    width: 600,
    height: 600,
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
      preload: path.join(__dirname, 'preload.js')
    }
  };

  // Use non-activating panel on macOS to prevent focus stealing for ALL interactions
  if (process.platform === 'darwin') {
    windowOptions.type = 'panel';  // Makes entire window non-activating
  }

  win = new BrowserWindow(windowOptions);

  win.setContentProtection(true);

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
async function sendChatMessage(text, imageData = null, model = 'gemini-1.5-flash', chatHistory = [], customPrompt = null) {
  try {
    console.log('Sending streaming chat message - Text:', !!text, 'Image:', !!imageData, 'Model:', model, 'History length:', chatHistory.length);
    console.log('Custom prompt:', customPrompt ? customPrompt.substring(0, 100) + '...' : 'None (using default)');

    const payload = {};
    if (text) payload.text = text;
    if (imageData) payload.image = imageData;
    payload.model = model;
    payload.chatHistory = chatHistory;
    payload.customPrompt = customPrompt;

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
async function processAccumulatedScreenshots(screenshots, model = 'gemini-1.5-flash', customPrompt = null) {
  try {
    console.log('Processing accumulated screenshots with streaming:', screenshots.length, 'Model:', model);
    console.log('Custom prompt:', customPrompt ? customPrompt.substring(0, 100) + '...' : 'None (using default)');

    const payload = {
      images: screenshots,
      model: model,
      customPrompt: customPrompt
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
  // Load pin on top setting
  isPinnedOnTop = getPinOnTopSetting();
  console.log(`📌 Pin on top setting loaded: ${isPinnedOnTop}`);

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
  ipcMain.handle('chat:send-message', async (event, text, imageData, model, chatHistory, customPrompt) => {
    // Add JWT token to authenticated requests
    await sendChatMessage(text, imageData, model, chatHistory, customPrompt);
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
  ipcMain.handle('screenshot:process-accumulated', async (event, screenshots, model, customPrompt) => {
    await processAccumulatedScreenshots(screenshots, model, customPrompt);
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
        chat: `You are ChatAura, a helpful AI assistant designed to provide intelligent support for various tasks. You excel at helping users with coding questions, problem-solving, explanations, and general assistance. Your responses should be clear, concise, and helpful. When helping with coding or technical topics, provide accurate information and explain concepts clearly. You can analyze screenshots, images, and text to provide contextual assistance. Keep your responses natural and conversational while being informative and useful. If you're unsure about something, it's okay to say so and suggest alternative approaches.`
      };

      return { success: true, prompt: defaultPrompts[mode] || defaultPrompts.interview };
    } catch (error) {
      console.error('Error getting default prompt:', error);
      return { success: false, error: error.message };
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