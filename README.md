# ChatAura - AI Interview Helper

A desktop application that helps you during coding interviews by providing AI-powered assistance. Built with Electron and Python Flask backend, featuring real-time screenshot analysis and chat capabilities.

## Features

- 🖥️ **Desktop Application**: Cross-platform Electron app with system tray integration
- 📸 **Screenshot Analysis**: Capture and analyze screenshots with AI assistance
- 💬 **AI Chat**: Interactive chat with multiple AI models (Gemini, GPT-4, Claude)
- 🔐 **User Authentication**: Secure user management with JWT tokens
- 📊 **Token Tracking**: Monitor API usage and costs
- 🎯 **Interview Focus**: Specialized for coding interview scenarios
- 🔍 **Always-on-Top**: Stays accessible during interviews

## Project Structure

```
chataura/
├── Frontend/            # Electron frontend application
│   ├── main.js          # Main Electron process
│   ├── preload.js       # Preload script for IPC
│   ├── index.html       # Main app interface
│   ├── auth.html        # Authentication interface
│   └── package.json     # Frontend dependencies
└── Backend/             # Python Flask backend
    ├── server.py        # Main Flask server
    ├── auth.py          # Authentication logic
    ├── database.py      # Database operations
    ├── conversation.py  # Chat conversation handling
    ├── gemsdk.py        # Gemini AI integration
    ├── openai_client.py # OpenAI integration
    ├── env.example      # Environment variables template
    └── requirements.txt # Backend dependencies
```

## Prerequisites

- **Node.js** (v20 or higher)
- **Python** (3.11 or higher)
- **npm** (comes with Node.js)
- **Git** (for cloning the repository)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/chataura.git
cd chataura
```

### 2. Backend Setup

```bash
# Navigate to backend directory
cd Backend

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd Frontend

# Install Node.js dependencies
npm install
```

### 4. Environment Configuration

Copy the example environment file and configure your API keys:

```bash
# Copy the example environment file
cp Backend/env.example Backend/.env
```

Then edit `Backend/.env` with your API keys:

```bash
# Backend/.env
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
JWT_SECRET=your_jwt_secret_here
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
   - This ensures login sessions persist across app restarts

## Running the Application

### Start the Backend Server

```bash
cd Backend
python server.py
```

The backend will start on `http://localhost:3000`

### Start the Frontend Application

In a new terminal:

```bash
cd Frontend
npm start
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

### Backend Development

```bash
cd Backend
python server.py
```

The Flask server runs with debug mode enabled for development.

### Frontend Development

```bash
cd Frontend
npm run dev
```

This starts Electron with auto-reload on file changes.

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