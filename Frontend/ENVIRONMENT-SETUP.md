# Environment Setup Guide

This document explains how to configure the Cluemore app for different environments (development and production).

## Environment Configuration

The app uses environment variables to switch between development and production backends.

### Development Environment

**File:** `.env.development`
```
NODE_ENV=development
BACKEND_URL=http://localhost:3000
```

**Usage:**
```bash
npm start          # Starts in development mode
npm run dev        # Starts in development mode with debugging
```

### Production Environment

**File:** `.env.production`
```
NODE_ENV=production
BACKEND_URL=https://cluemore-166792667b90.herokuapp.com
```

**Usage:**
```bash
npm run start:prod # Starts in production mode
```

## Setup Instructions

### 1. Development Setup

1. **Start the local backend:**
   ```bash
   cd backend
   python server.py
   ```

2. **Start the frontend in development mode:**
   ```bash
   cd frontend
   npm start
   ```

   The app will automatically connect to `http://localhost:3000`

### 2. Production Setup

1. **Start the frontend in production mode:**
   ```bash
   cd frontend
   npm run start:prod
   ```

   The app will automatically connect to the Heroku backend

### 3. Building for Distribution

```bash
npm run build-production  # Builds with production environment
npm run build            # Builds the distributable
```

## Environment Variables

| Variable | Development | Production | Description |
|----------|-------------|------------|-------------|
| `NODE_ENV` | `development` | `production` | Environment identifier |
| `BACKEND_URL` | `http://localhost:3000` | `https://cluemore-166792667b90.herokuapp.com` | Backend API URL |

## Troubleshooting

### App connects to wrong backend

1. Check that the correct environment file exists
2. Verify the `NODE_ENV` is set correctly
3. Check the console logs for the backend URL being used

### Backend not responding

1. **Development:** Ensure the local backend is running on port 3000
2. **Production:** Check if the Heroku app is online

### Environment files not loading

1. Ensure `dotenv` is installed: `npm install dotenv`
2. Check that the environment files are in the correct location
3. Verify the file permissions

## Notes

- The app automatically loads the correct environment file based on `NODE_ENV`
- If no environment file is found, it defaults to production settings
- All API calls (auth, chat, notes) use the configured backend URL
- Environment configuration is logged to the console on startup 