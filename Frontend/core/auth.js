// Authentication module for Cluemore frontend
const keytar = require('keytar');

// Constants
const SERVICE_NAME = 'CluemoreStealth';
const ACCOUNT_NAME = 'jwt_token';
let BACKEND_URL;

// State
let jwtToken = null;
let currentUser = null;

// Initialize backend URL
function initializeAuth(backendUrl) {
    BACKEND_URL = backendUrl;
}

// Helper function for making requests
async function makeRequest(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (options.body) {
        options.body = JSON.stringify(options.body);
    }

    const finalOptions = { ...defaultOptions, ...options };
    
    // Add authorization header if we have a token
    if (jwtToken && !url.includes('/auth/')) {
        finalOptions.headers.Authorization = `Bearer ${jwtToken}`;
    }

    const response = await fetch(url, finalOptions);
    
    if (!response.ok && response.status !== 401) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
}

// Token storage functions
async function storeToken(token) {
    try {
        // Store token directly - permission dialog handling moved to main process
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
        // Retrieve token directly - permission dialog handling moved to main process
        const token = await keytar.getPassword(SERVICE_NAME, ACCOUNT_NAME);
        
        if (token) {
            jwtToken = token;
            console.log('JWT token retrieved from keychain');
        }
        return token;
    } catch (error) {
        console.error('Failed to retrieve token:', error);
        return null;
    }
}

async function removeStoredToken() {
    try {
        // Delete token directly - permission dialog handling moved to main process
        await keytar.deletePassword(SERVICE_NAME, ACCOUNT_NAME);

        jwtToken = null;
        currentUser = null;
        console.log('JWT token removed from keychain');
        return true;
    } catch (error) {
        console.error('Failed to remove token:', error);
        return false;
    }
}

// Authentication functions
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

async function logout() {
    const success = await removeStoredToken();
    return { success };
}

// Getters
function getCurrentUser() {
    return currentUser;
}

function getJwtToken() {
    return jwtToken;
}

module.exports = {
    initializeAuth,
    storeToken,
    getStoredToken,
    removeStoredToken,
    verifyStoredToken,
    authenticateUser,
    registerUser,
    logout,
    getCurrentUser,
    getJwtToken,
    makeRequest
}; 