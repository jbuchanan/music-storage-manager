#!/usr/bin/env python3
"""
Music Storage Manager Desktop App
A desktop wrapper for the Flask web interface using PyWebView.
"""

import webview
import threading
import time
import sys
import os
import logging
from app import app

# Get logger for desktop app
logger = logging.getLogger('desktop_app')

class DesktopApp:
    def __init__(self):
        self.flask_thread = None
        self.server_started = False

    def start_flask(self):
        """Start Flask server in background thread"""
        try:
            # Disable Flask's reloader in desktop mode
            app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
        except Exception as e:
            logger.error(f"Flask server error: {e}", exc_info=True)

    def wait_for_server(self, timeout=10):
        """Wait for Flask server to start"""
        import requests
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get('http://127.0.0.1:5001', timeout=1)
                if response.status_code == 200:
                    self.server_started = True
                    return True
            except:
                time.sleep(0.5)

        return False

    def on_window_loaded(self):
        """Called when the webview window is loaded"""
        logger.info("Desktop app window loaded successfully")

    def on_closing(self):
        """Called when the window is about to close"""
        logger.info("Desktop app closing...")
        # Graceful shutdown would go here
        return True

    def run(self):
        """Start the desktop application"""
        # Start Flask in background thread
        self.flask_thread = threading.Thread(target=self.start_flask, daemon=True)
        self.flask_thread.start()

        # Wait for server to start
        logger.info("Starting Music Storage Manager...")
        if not self.wait_for_server():
            logger.error("Failed to start Flask server")
            sys.exit(1)

        logger.info("Server started, opening desktop window...")

        # Create desktop window
        window = webview.create_window(
            title='Music Storage Manager',
            url='http://127.0.0.1:5001',
            width=1400,
            height=900,
            min_size=(800, 600),
            resizable=True,
            on_top=False
        )

        # Configure webview settings
        webview.settings = {
            'ALLOW_DOWNLOADS': True,
            'ALLOW_FILE_URLS': True,
            'OPEN_EXTERNAL_LINKS_IN_BROWSER': True,
            'OPEN_DEVTOOLS_IN_DEBUG': False
        }

        # Start the webview
        try:
            webview.start(
                debug=False,
                http_server=False,  # We're using our own Flask server
                private_mode=False
            )
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
        except Exception as e:
            logger.error(f"Desktop app error: {e}", exc_info=True)
            sys.exit(1)

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == '--web':
        # Run in web mode (original Flask app)
        logger.info("Starting in web mode...")
        app.run(debug=True, host='127.0.0.1', port=5001)
    else:
        # Run in desktop mode
        logger.info("Starting in desktop mode...")
        desktop_app = DesktopApp()
        desktop_app.run()

if __name__ == '__main__':
    main()