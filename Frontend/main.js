const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, desktopCapturer, ipcMain } = require('electron');
const path = require('path');
const https = require('https');
const http = require('http');
const keytar = require('keytar');

// Load environment variables
require('dotenv').config({
  path: process.env.NODE_ENV === 'production' ? '.env.production' : '.env.development'
});

let win;
let authWin;
let promptEditorWin; // Add prompt editor panel window
let currentUser = null;
let jwtToken = null;
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
    await keytar.setPassword(SERVICE_NAME, ACCOUNT_NAME, token);
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
    const token = await keytar.getPassword(SERVICE_NAME, ACCOUNT_NAME);
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
    await keytar.deletePassword(SERVICE_NAME, ACCOUNT_NAME);
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

function createAuthWindow() {
  authWin = new BrowserWindow({
    width: 500,
    height: 700,
    resizable: false,
    alwaysOnTop: true,
    title: 'Cluemore - Login',
    transparent: true,
    frame: false,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  authWin.setContentProtection(true);
  authWin.setAlwaysOnTop(true, 'screen-saver');
  authWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  authWin.setFullScreenable(false);

  authWin.loadFile('auth.html');
  authWin.once('ready-to-show', () => {
    authWin.setOpacity(1.0);
    // Use showInactive() to prevent focus stealing
    authWin.showInactive();
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

  win = new BrowserWindow({
    width: 600,
    height: 600,
    resizable: false,
    alwaysOnTop: true,
    title: 'Cluemore',
    skipTaskbar: true,
    transparent: true,
    frame: false,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  win.setContentProtection(true);
  win.setAlwaysOnTop(true, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.setFullScreenable(false);

  win.loadFile('index.html');
  win.once('ready-to-show', () => {
    win.setOpacity(1.0);
    // Use showInactive() to prevent focus stealing
    win.showInactive();
  });

  win.on('closed', () => {
    win = null;
  });
}

// Create non-activating panel for prompt editing (macOS only)
function createPromptEditorPanel() {
  // Only use panel type on macOS to prevent focus stealing
  const windowOptions = {
    width: 500,
    height: 400,
    frame: false,
    resizable: false,
    transparent: true,
    alwaysOnTop: true,
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
  promptEditorWin.setAlwaysOnTop(true, 'screen-saver');

  promptEditorWin.loadFile('prompt-editor.html');

  promptEditorWin.on('closed', () => {
    promptEditorWin = null;
  });

  return promptEditorWin;
}

// Chat function
async function sendChatMessage(text, imageData = null, model = 'gemini-1.5-flash', chatHistory = [], customPrompt = null) {
  try {
    console.log('Sending chat message - Text:', !!text, 'Image:', !!imageData, 'Model:', model, 'History length:', chatHistory.length);
    console.log('Custom prompt:', customPrompt ? customPrompt.substring(0, 100) + '...' : 'None (using default)');

    const payload = {};
    if (text) payload.text = text;
    if (imageData) payload.image = imageData;
    payload.model = model;
    payload.chatHistory = chatHistory; // Include conversation history
    payload.customPrompt = customPrompt; // Include custom system prompt

    // Use protected endpoint with JWT token
    const response = await makeRequest(`${BACKEND_URL}/api/chat_protected`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`
      },
      body: payload
    });

    console.log('Chat response received:', response);

    if (response.success && response.response) {
      console.log('Received chat response from backend');
      // Send response to renderer process to display
      win.webContents.send('chat-response', response.response);
    } else {
      console.error('Chat backend error:', response.error);
      win.webContents.send('chat-error', response.error || 'Unknown chat error');
    }

  } catch (error) {
    console.error('Chat error:', error);
    win.webContents.send('chat-error', error.message);
  }
}

// Screenshot function
async function takeScreenshot(forChat = false) {
  try {
    console.log('Taking screenshot...', forChat ? 'for chat' : 'for analysis');

    // Get all available sources (screens) with smaller thumbnail for faster processing
    const sources = await desktopCapturer.getSources({
      types: ['screen'],
      thumbnailSize: { width: 1280, height: 720 }  // Reduced size for faster processing
    });

    if (sources.length === 0) {
      console.error('No screens found');
      return;
    }

    // Use the first screen (primary display)
    const primaryScreen = sources[0];
    const screenshot = primaryScreen.thumbnail;

    // Convert to base64
    const base64Data = screenshot.toPNG().toString('base64');
    console.log(`Screenshot captured, size: ${base64Data.length} characters`);

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
    if (forChat) {
      win.webContents.send('chat-error', 'Failed to capture screenshot: ' + error.message);
    } else {
      win.webContents.send('screenshot-error', error.message);
    }
  }
}

// Process accumulated screenshots
async function processAccumulatedScreenshots(screenshots, model = 'gemini-1.5-flash', customPrompt = null) {
  try {
    console.log('Processing accumulated screenshots:', screenshots.length, 'Model:', model);
    console.log('Custom prompt:', customPrompt ? customPrompt.substring(0, 100) + '...' : 'None (using default)');

    // Use protected endpoint with JWT token
    const response = await makeRequest(`${BACKEND_URL}/api/screenshot_protected`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${jwtToken}`
      },
      body: { images: screenshots, model: model, customPrompt: customPrompt }
    });

    console.log('Backend response received:', response);

    if (response.success && response.solution) {
      console.log('Received solution from backend, length:', response.solution.length);
      // Send solution to renderer process to display
      win.webContents.send('screenshot-solution', response.solution);
    } else {
      console.error('Backend error:', response.error);
      win.webContents.send('screenshot-error', response.error || 'Unknown error');
    }

  } catch (error) {
    console.error('Screenshot processing error:', error);
    console.error('Error details:', error.message);
    win.webContents.send('screenshot-error', error.message);
  }
}

app.whenReady().then(async () => {
  // Check if user is already authenticated
  const isAuthenticated = await verifyStoredToken();

  if (isAuthenticated) {
    console.log('User already authenticated, opening main app');
    createMainWindow();
  } else {
    console.log('No valid authentication, showing login');
    createAuthWindow();
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
    } else if (authWin && !authWin.isVisible()) {
      authWin.showInactive(); // Use showInactive() to prevent focus stealing
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
            win.isVisible() ? win.hide() : win.showInactive(); // Use showInactive() to prevent focus stealing
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

app.on('will-quit', () => {
  // Unregister all shortcuts
  globalShortcut.unregisterAll();
}); 