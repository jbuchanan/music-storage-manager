#!/usr/bin/env python3
"""
Music Storage Manager Web Interface Runner
Simple script to start the Flask web application.
"""

import os
import sys
import webbrowser
from threading import Timer

def open_browser():
    """Open web browser after a short delay"""
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from app import app

    print("Starting Music Storage Manager Web Interface...")
    print("Web interface will be available at: http://127.0.0.1:5001")
    print("Press Ctrl+C to stop")

    # Open browser after 1.5 seconds
    def open_browser_new():
        webbrowser.open('http://127.0.0.1:5001')

    Timer(1.5, open_browser_new).start()

    # Run the Flask app
    app.run(debug=False, host='127.0.0.1', port=5001)