#!/usr/bin/env python3
"""
Simple Music Storage Manager Web Interface
Minimal Flask app without heavy templates
"""

import os
import subprocess
from flask import Flask, jsonify, request

app = Flask(__name__)

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(BASE_DIR, 'music-storage-manager.zsh')

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Music Storage Manager</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            button { padding: 10px 20px; margin: 10px; font-size: 16px; }
            #output { border: 1px solid #ccc; padding: 20px; margin: 20px 0;
                     background: #f5f5f5; white-space: pre-wrap;
                     max-height: 400px; overflow-y: auto; }
        </style>
    </head>
    <body>
        <h1>Music Storage Manager</h1>

        <button onclick="runDryRun()">Dry Run</button>
        <button onclick="runWithFilter()">Run UVI Only</button>

        <div>
            <label>Filter: <input type="text" id="filter" placeholder="e.g., UVI"></label>
            <button onclick="runCustom()">Run Custom</button>
        </div>

        <div id="output" style="display:none;"></div>

        <script>
        async function runCommand(dryRun, filter = '') {
            const output = document.getElementById('output');
            output.style.display = 'block';
            output.textContent = 'Running...';

            try {
                const response = await fetch('/api/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        dry_run: dryRun,
                        verbose: true,
                        only_filter: filter
                    })
                });

                const result = await response.json();

                if (result.status === 'success') {
                    output.textContent = result.stdout + (result.stderr ? '\\n\\nErrors:\\n' + result.stderr : '');
                } else {
                    output.textContent = 'Error: ' + result.message;
                }
            } catch (error) {
                output.textContent = 'Error: ' + error.message;
            }
        }

        function runDryRun() { runCommand(true); }
        function runWithFilter() { runCommand(true, 'UVI'); }
        function runCustom() {
            const filter = document.getElementById('filter').value;
            runCommand(true, filter);
        }
        </script>
    </body>
    </html>
    '''

@app.route('/api/execute', methods=['POST'])
def api_execute():
    try:
        data = request.json
        dry_run = data.get('dry_run', True)
        verbose = data.get('verbose', False)
        only_filter = data.get('only_filter', '')

        cmd = [SCRIPT_PATH]
        if dry_run:
            cmd.append('-n')
        if verbose:
            cmd.append('-v')
        if only_filter:
            cmd.extend(['--only', only_filter])

        env = os.environ.copy()
        if dry_run:
            env['MSM_SKIP_NAS_MOUNT'] = '1'

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=BASE_DIR, env=env)

        return jsonify({
            'status': 'success',
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        })

    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Operation timed out'}), 408
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5001)