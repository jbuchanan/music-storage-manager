# Music Storage Manager - Desktop App

Your Flask app has been converted to a native Mac desktop application using PyWebView.

## Usage

**Desktop Mode (Recommended):**
```bash
source venv/bin/activate
python desktop_app.py
```

**Web Mode (Original):**
```bash
source venv/bin/activate
python desktop_app.py --web
```

## Features

- **Native macOS Window**: Runs in its own window, not a browser tab
- **Proper Desktop Integration**: Appears in dock, cmd+tab switching
- **No Browser UI**: Clean interface without browser chrome
- **Automatic Server Management**: Flask server starts automatically
- **Graceful Shutdown**: Proper cleanup when closing

## Installation

1. Create virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Run the desktop app:
```bash
python desktop_app.py
```

## Files Added

- `desktop_app.py` - Main desktop wrapper application
- Updated `requirements.txt` with PyWebView dependencies

The original Flask app (`app.py`) remains unchanged and can still be used independently.