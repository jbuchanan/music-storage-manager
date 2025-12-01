#!/usr/bin/env python3
"""
Music Storage Manager Web Interface Runner
Simple script to start the Flask web application.
"""

import os
import sys
import logging
import webbrowser
from threading import Timer

# Configure basic logging before importing app
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def open_browser():
    """Open web browser after a short delay"""
    webbrowser.open('http://127.0.0.1:5000')

if __name__ == '__main__':
    # Add current directory to Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from app import app

    logger.info("Starting Music Storage Manager Web Interface...")
    logger.info("Web interface will be available at: http://127.0.0.1:5001")
    logger.info("Press Ctrl+C to stop")

    # Open browser after 1.5 seconds
    def open_browser_new():
        try:
            webbrowser.open('http://127.0.0.1:5001')
            logger.info("Opened web browser")
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")

    Timer(1.5, open_browser_new).start()

    # Run the Flask app
    try:
        app.run(debug=False, host='127.0.0.1', port=5001)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)