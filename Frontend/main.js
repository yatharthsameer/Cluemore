const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, desktopCapturer, ipcMain } = require('electron');
const path = require('path');
const http = require('http');
const keytar = require('keytar');

let win;
let authWin;
let currentUser = null;
let jwtToken = null;
// Backend URL configuration
const BACKEND_URL = 'http://localhost:3000';
const SERVICE_NAME = 'ChatAura';
const ACCOUNT_NAME = 'user_jwt_token';

// Helper function to make HTTP requests
function makeRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);

    const requestOptions = {
      hostname: urlObj.hostname,
      port: urlObj.port,
      path: urlObj.pathname,
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    };

    const req = http.request(requestOptions, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        try {
          const jsonData = JSON.parse(data);
          resolve(jsonData);
        } catch (error) {
          resolve({ error: 'Invalid JSON response', data });
        }
      });
    });

    req.on('error', (error) => {
      reject(error);
    });

    if (options.body) {
      req.write(JSON.stringify(options.body));
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
      console.log('Token verified, user:', currentUser.username);
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

async function authenticateUser(username, password) {
  try {
    const response = await makeRequest(`${BACKEND_URL}/api/auth/login`, {
      method: 'POST',
      body: { username, password }
    });

    if (response.success && response.token) {
      await storeToken(response.token);
      currentUser = response.user;
      console.log('User authenticated successfully:', currentUser.username);
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

async function registerUser(username, email, password) {
  try {
    const response = await makeRequest(`${BACKEND_URL}/api/auth/register`, {
      method: 'POST',
      body: { username, email, password }
    });

    if (response.success && response.token) {
      await storeToken(response.token);
      currentUser = response.user;
      console.log('User registered successfully:', currentUser.username);
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
    title: 'ChatAura - Login',
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
    authWin.show();
  });

  authWin.on('closed', () => {
    authWin = null;
  });
}

function createMainWindow() {
  if (win) {
    win.show();
    return;
  }

  win = new BrowserWindow({
    width: 600,
    height: 600,
    resizable: false,
    alwaysOnTop: true,
    title: 'ChatAura',
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
    win.show();
  });

  win.on('closed', () => {
    win = null;
  });
}

// Chat function
async function sendChatMessage(text, imageData = null, model = 'gemini-1.5-flash', chatHistory = []) {
  try {
    console.log('Sending chat message - Text:', !!text, 'Image:', !!imageData, 'Model:', model, 'History length:', chatHistory.length);

    const payload = {};
    if (text) payload.text = text;
    if (imageData) payload.image = imageData;
    payload.model = model;
    payload.chatHistory = chatHistory; // Include conversation history

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

  // Movement shortcuts: cmd + arrow keys
  globalShortcut.register('CommandOrControl+Left', () => {
    if (win && win.isVisible()) {
      const [x, y] = win.getPosition();
      win.setPosition(Math.max(0, x - moveStep), y);
    }
  });

  globalShortcut.register('CommandOrControl+Right', () => {
    if (win && win.isVisible()) {
      const [x, y] = win.getPosition();
      const { width: screenWidth } = require('electron').screen.getPrimaryDisplay().workAreaSize;
      win.setPosition(Math.min(screenWidth - 600, x + moveStep), y);
    }
  });

  globalShortcut.register('CommandOrControl+Up', () => {
    if (win && win.isVisible()) {
      const [x, y] = win.getPosition();
      win.setPosition(x, Math.max(0, y - moveStep));
    }
  });

  globalShortcut.register('CommandOrControl+Down', () => {
    if (win && win.isVisible()) {
      const [x, y] = win.getPosition();
      const { height: screenHeight } = require('electron').screen.getPrimaryDisplay().workAreaSize;
      win.setPosition(x, Math.min(screenHeight - 600, y + moveStep));
    }
  });

  // Auto-hide shortcut: cmd + 6
  globalShortcut.register('CommandOrControl+6', () => {
    if (win) {
      if (win.isVisible()) {
        win.hide();
      } else {
        win.show();
      }
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

  // Create tray with error handling for icon
  let tray;
  try {
    tray = new Tray(path.join(__dirname, 'iconTemplate.png'));
  } catch (error) {
    // Fallback: create tray without icon or use system icon
    console.log('Could not load tray icon, using default');
    tray = new Tray(nativeImage.createEmpty());
  }

  if (tray) {
    tray.setContextMenu(Menu.buildFromTemplate([
      {
        label: 'Show / Hide', click: () => {
          if (win) {
            win.isVisible() ? win.hide() : win.show();
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
  ipcMain.handle('auth:login', async (event, username, password) => {
    return await authenticateUser(username, password);
  });

  ipcMain.handle('auth:register', async (event, username, email, password) => {
    return await registerUser(username, email, password);
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

  // Existing IPC Handlers for chat functionality
  ipcMain.handle('chat:send-message', async (event, text, imageData, model, chatHistory) => {
    // Add JWT token to authenticated requests
    await sendChatMessage(text, imageData, model, chatHistory);
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
});

app.on('window-all-closed', () => { /* keep running in tray */ });

app.on('will-quit', () => {
  // Unregister all shortcuts
  globalShortcut.unregisterAll();
}); 