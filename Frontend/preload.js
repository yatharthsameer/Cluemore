const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to communicate
// with the main process securely
contextBridge.exposeInMainWorld('electronAPI', {
    // Listen for screenshot solution from main process
    onScreenshotSolution: (callback) => {
        console.log('Setting up screenshot-solution listener in preload.js');
        ipcRenderer.on('screenshot-solution', (event, solution) => {
            console.log('Preload.js received screenshot-solution event, solution length:', solution.length);
            callback(solution);
        });
    },

    // Listen for screenshot errors from main process
    onScreenshotError: (callback) => {
        ipcRenderer.on('screenshot-error', (event, error) => {
            callback(error);
        });
    },

    // Chat functionality with model parameter and custom prompt
    sendChatMessage: (text, imageData, model, chatHistory, customPrompt) => ipcRenderer.invoke('chat:send-message', text, imageData, model, chatHistory, customPrompt),

    onChatResponse: (callback) => {
        ipcRenderer.on('chat-response', (event, response) => {
            callback(response);
        });
    },

    onChatError: (callback) => {
        ipcRenderer.on('chat-error', (event, error) => {
            callback(error);
        });
    },

    // Screenshot functionality for chat
    onChatScreenshotCaptured: (callback) => {
        ipcRenderer.on('chat-screenshot-captured', (event, imageData) => {
            callback(imageData);
        });
    },

    // Screenshot functionality for LeetCode Helper
    onLeetcodeScreenshotCaptured: (callback) => {
        ipcRenderer.on('leetcode-screenshot-captured', (event, imageData) => {
            callback(imageData);
        });
    },

    // Process accumulated screenshots with model and custom prompt parameters
    processAccumulatedScreenshots: (screenshots, model, customPrompt) => ipcRenderer.invoke('screenshot:process-accumulated', screenshots, model, customPrompt),

    onCheckCurrentMode: (callback) => {
        ipcRenderer.on('check-current-mode', () => {
            callback();
        });
    },

    takeScreenshotForMode: (mode) => ipcRenderer.invoke('screenshot:take-for-mode', mode),

    // Handle global shortcut for processing accumulated screenshots
    onProcessAccumulatedScreenshots: (callback) => {
        ipcRenderer.on('process-accumulated-screenshots', () => {
            callback();
        });
    },

    // Handle global Cmd+Enter shortcut
    onHandleCmdEnter: (callback) => {
        ipcRenderer.on('handle-cmd-enter', () => {
            callback();
        });
    },

    // Handle global Cmd+Shift+I shortcut to switch to chat mode
    onSwitchToChatMode: (callback) => {
        ipcRenderer.on('switch-to-chat-mode', () => {
            callback();
        });
    },

    // Remove listeners when needed
    removeAllListeners: (channel) => {
        ipcRenderer.removeAllListeners(channel);
    },

    // Settings functionality
    setWindowOpacity: (opacity) => ipcRenderer.invoke('window:set-opacity', opacity),

    // Authentication functionality
    login: (email, password) => ipcRenderer.invoke('auth:login', email, password),
    register: (email, password) => ipcRenderer.invoke('auth:register', email, password),
    logout: () => ipcRenderer.invoke('auth:logout'),
    verifyToken: (token) => ipcRenderer.invoke('auth:verify-token', token),
    getCurrentUser: () => ipcRenderer.invoke('auth:get-current-user'),

    // App navigation
    openMainApp: () => ipcRenderer.invoke('app:open-main'),
    openAuthPage: () => ipcRenderer.invoke('app:open-auth'),

    // Token storage events
    onTokenStored: (callback) => {
        ipcRenderer.on('auth:token-stored', (event, token) => {
            callback(token);
        });
    },

    onTokenRemoved: (callback) => {
        ipcRenderer.on('auth:token-removed', () => {
            callback();
        });
    },

    // Get current auth token
    getAuthToken: () => ipcRenderer.invoke('auth:get-token'),

    // Get backend URL
    getBackendUrl: () => ipcRenderer.invoke('app:get-backend-url')
});

// nothing fancy yet – isolated world so the renderer is sandboxed 