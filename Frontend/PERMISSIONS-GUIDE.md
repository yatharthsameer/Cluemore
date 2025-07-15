# Cluemore Permissions Guide

## Overview

Cluemore requests several macOS permissions upfront to ensure all features work seamlessly. This guide explains what permissions are needed and how to manage them.

## Required Permissions

### 📺 Screen Recording
**Purpose**: Capture screenshots for AI analysis and problem-solving assistance
**When prompted**: First app launch or when using screenshot features

### 📷 Camera Access  
**Purpose**: Image capture and analysis features
**When prompted**: First app launch or when using camera-related features

### 🎤 Microphone Access
**Purpose**: Voice input and audio-related AI features  
**When prompted**: First app launch or when using voice features

### 🔑 Keychain Access
**Purpose**: Securely store login credentials and tokens
**When prompted**: Automatically when the app needs to store/retrieve credentials

## Permission Request Flow

1. **First Launch**: Cluemore shows a permission explanation window
2. **System Prompts**: macOS will show individual permission dialogs
3. **App Continues**: Once permissions are handled, the app proceeds normally

## Managing Permissions Manually

If you need to change permissions later:

### Method 1: System Preferences
1. Open **System Preferences** > **Security & Privacy**
2. Click the **Privacy** tab
3. Select the permission type from the left sidebar
4. Find **Cluemore** in the list and check/uncheck as needed

### Method 2: System Settings (macOS Ventura+)
1. Open **System Settings** > **Privacy & Security**
2. Select the permission type you want to modify
3. Find **Cluemore** and toggle the permission on/off

## Troubleshooting

### Screen Recording Not Working
1. Go to **System Preferences** > **Security & Privacy** > **Privacy** > **Screen Recording**
2. Ensure **Cluemore** is checked ✅
3. If not listed, try taking a screenshot in the app to trigger the permission request

### Camera/Microphone Access Denied
1. Go to **System Preferences** > **Security & Privacy** > **Privacy** > **Camera** (or **Microphone**)
2. Check the box next to **Cluemore** ✅
3. Restart the app if needed

### Keychain Access Issues
1. Open **Keychain Access** app
2. Look for entries related to "Cluemore"
3. If prompted, click "Always Allow" when Cluemore requests keychain access

## Permission Status in App

You can check current permission status within the app:
- Open the app
- Check the console logs for permission status
- Look for 🔍 permission status messages

## Why These Permissions Are Needed

- **Screen Recording**: Core feature for capturing and analyzing code/problems
- **Camera**: Enhanced AI interactions with image input
- **Microphone**: Voice commands and audio features (planned)
- **Keychain**: Secure credential storage without exposing sensitive data

## Security Notes

- Cluemore only accesses these resources when actively using related features
- All data is processed securely and credentials are encrypted in keychain
- Screen recordings are only taken when explicitly requested by you
- No data is stored permanently without your knowledge

## Need Help?

If you're having permission issues:
1. Try restarting the app
2. Check the troubleshooting steps above
3. Review the console logs for specific error messages
4. Contact support with details about the specific permission issue 