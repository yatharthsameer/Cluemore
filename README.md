# Cluemore - AI Stealth Mode

A desktop application that helps you during coding interviews by providing AI-powered assistance. Built with Electron and a unified Python ASGI backend (Flask HTTP + Starlette WebSocket) featuring real-time audio transcription and chat capabilities.

## Features

- 🖥️ **Desktop Application**: Cross-platform Electron app with system tray integration
- 📸 **Screenshot Analysis**: Capture and analyze screenshots with AI assistance
- 💬 **AI Chat**: Interactive chat with multiple AI models (Gemini, GPT-4, Claude)
- 🔐 **User Authentication**: Secure user management with JWT tokens
- 📊 **Token Tracking**: Monitor API usage and costs
- 🎯 **Stealth Mode**: Specialized for coding interview scenarios
- 🔍 **Always-on-Top**: Stays accessible during interviews
- 🔄 **Auto-Updates**: Seamless update system with GitHub Releases integration
- 🚀 **CI/CD**: Automated deployment with GitHub Actions and Heroku

## Project Structure

```
cluemore/
├── backend/             # Python backend (Flask HTTP + Starlette WS over ASGI)
│   ├── server.py        # Flask (HTTP routes)
│   ├── asgi_app.py      # Unified ASGI app (mounts Flask + /ws/audio WebSocket)
│   ├── auth.py          # Authentication logic
│   ├── database.py      # Database operations
│   ├── conversation.py  # Chat conversation handling
│   ├── gemsdk.py        # Gemini AI integration
│   ├── openai_client.py # OpenAI integration
│   ├── env.example      # Environment variables template
│   ├── requirements.txt # Backend dependencies
│   ├── Procfile         # Heroku deployment config (uvicorn on single port)
│   └── runtime.txt      # Python version for Heroku
├── frontend/            # Electron Mac application
│   ├── main.js          # Main Electron process
│   ├── preload.js       # Preload script for IPC
│   ├── index.html       # Main app interface
│   ├── auth.html        # Authentication interface
│   └── package.json     # Frontend dependencies
├── .github/workflows/   # CI/CD pipelines
├── deploy-heroku.sh     # Manual deployment script
├── heroku-setup.sh      # One-time Heroku setup
└── package.json        # Root monorepo configuration
```

## Prerequisites

- **Node.js** (v18 or higher)
- **Python** (3.11 or higher)  
- **npm** (comes with Node.js)
- **Git** (for cloning the repository)
- **Heroku CLI** (for deployment - optional)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/cluemore.git
cd cluemore
```

### 2. Install All Dependencies

```bash
# Install all dependencies (backend + frontend)
npm run install:all
```

### 3. Environment Configuration

Copy the example environment file and configure your API keys:

```bash
# Copy the example environment file
cp backend/env.example backend/.env
```

Then edit `backend/.env` with your API keys:

```bash
# backend/.env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
JWT_SECRET=your_jwt_secret_here
```

### 4. Run the Application (Unified backend)

```bash
# Start both backend and frontend
npm run dev

# Or run individually
# Backend (ASGI, single port for HTTP + WS)
cd backend
conda activate usualenv
pip install -r requirements.txt
uvicorn asgi_app:app --host 0.0.0.0 --port 3000 --reload

# Frontend (Electron)
cd ../Frontend
npm run dev
```

## 🚀 Deployment

For production deployment setup, see **[DEPLOYMENT-SETUP.md](./DEPLOYMENT-SETUP.md)** for:

- **Heroku backend deployment** with automated CI/CD
- **Mac app distribution** via GitHub Actions  
- **Environment configuration** for production
- **Troubleshooting guides** and best practices

### Manual Setup (Alternative)

If you prefer manual setup:

#### Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Install Python dependencies
pip install -r requirements.txt
```

#### Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install
```

#### Getting API Keys:

1. **Gemini API Key** (Required): 
   - Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create an API key for Gemini

2. **OpenAI API Key** (Optional):
   - Visit [OpenAI Platform](https://platform.openai.com/api-keys)
   - Create an API key
   - **Note**: Only needed if you want to use GPT models (gpt-4, gpt-3.5-turbo, etc.)

3. **JWT Secret** (Required for persistent login):
   - Use this fixed JWT secret for persistent login sessions:
   ```
   JWT_SECRET=a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456789012345678901234567890abcdef
   ```
   - **Important**: Without this, users will be logged out every time you restart the backend
   - This ensures login sessions persist indefinitely (no expiration)

## Running the Application

### Start Everything at Once (Recommended)

```bash
npm run dev
```

This starts both backend and frontend simultaneously.

### Start Individually

#### Backend Server (ASGI)
```bash
cd backend
conda activate usualenv
pip install -r requirements.txt
uvicorn asgi_app:app --host 0.0.0.0 --port 3000 --reload
```

The backend will start on `http://localhost:3000`

#### Frontend Application
```bash
npm run frontend:dev
# or manually:
# cd frontend && npm start
```

The Electron app will launch and connect to the backend.

## Usage

1. **First Launch**: Create an account or log in
2. **Screenshot Mode**: Press `Cmd+Shift+1` to capture screenshots
3. **Chat Mode**: Type messages and get AI assistance
4. **Window Controls**: Use keyboard shortcuts (see below)
5. **System Tray**: Access quick actions from the system tray

## Keyboard Shortcuts

All shortcuts work globally (even when the app is not in focus):

### Window Management
- **`Cmd+6`**: Hide/show the application window
- **`Cmd+Left`**: Move window 50 pixels to the left
- **`Cmd+Right`**: Move window 50 pixels to the right
- **`Cmd+Up`**: Move window 50 pixels up
- **`Cmd+Down`**: Move window 50 pixels down

### Core Features
- **`Cmd+Shift+1`**: Take screenshot and analyze with AI
- **`Cmd+Enter`**: Send message in chat mode or process screenshots in screenshot mode
- **`Cmd+Shift+I`**: Switch to chat mode and focus input field

### System Tray Actions
Right-click the system tray icon to access:
- **Show/Hide**: Toggle window visibility
- **Take Screenshot**: Capture and analyze screenshot
- **Logout**: Sign out and return to login screen
- **Quit**: Exit the application

### Usage Tips
- The app stays "always on top" for easy access during interviews
- Window movements are constrained to screen boundaries
- Screenshots are automatically analyzed based on the current mode (chat or screenshot accumulation)
- All shortcuts work system-wide, so you can use them while working in other applications

## Development

### Full Development Environment

```bash
# Install dependencies and start development servers
npm run install:all
npm run dev
```

### Individual Development

#### Backend Development
```bash
npm run backend:dev
```
The backend serves both HTTP and WebSocket on the same port via uvicorn.

### Realtime Audio/WebSocket
- WebSocket endpoint: `ws://localhost:3000/ws/audio`
- The Electron app connects to `BACKEND_URL/ws/audio` and streams 16kHz PCM (20ms frames).
- Keepalives are enabled on both client and server for long interviews.

## Troubleshooting

- Could not import module "asgi_app": run uvicorn from the `backend/` directory, or use `uvicorn --app-dir backend asgi_app:app`.
- 400 on /api/auth/register with empty body: ensure requests set `Content-Type: application/json` and proper `Content-Length`.
- WebSocket closes with 1011/internal error: ensure you are using the unified server (no separate ws process). The WebSocket path must be `/ws/audio` on the same port as HTTP.
- Long sessions dropping: keepalives are configured (server ping_interval/ping_timeout and client pings). If behind a proxy, keep WS and HTTP on the single `$PORT`.

#### Frontend Development  
```bash
npm run frontend:dev
```
This starts Electron with auto-reload on file changes.

### Project Scripts

Available npm scripts in the root `package.json`:

- `npm run install:all` - Install all dependencies (backend + frontend)
- `npm run dev` - Start both backend and frontend in development mode
- `npm run backend:dev` - Start only the backend server
- `npm run frontend:dev` - Start only the frontend app
- `npm run backend:install` - Install only backend dependencies
- `npm run frontend:install` - Install only frontend dependencies

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation
- Review the code comments

## Acknowledgments

- Built with Electron and Flask
- Uses Google Gemini and OpenAI APIs
- Inspired by the need for better coding interview tools 