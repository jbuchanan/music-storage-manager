#!/usr/bin/env python3
"""
Music Storage Manager Web Interface
A Flask web application for managing music storage rules and monitoring operations.
"""

import os
import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'music-storage-manager-secret-key'

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(BASE_DIR, 'music-storage-rules-unified.csv')
LOG_FILE = os.path.join(BASE_DIR, 'music-storage-manager.log')
SCRIPT_PATH = os.path.join(BASE_DIR, 'music-storage-manager.zsh')

class RulesManager:
    def __init__(self, rules_file):
        self.rules_file = rules_file

    def load_rules(self):
        """Load rules from CSV file"""
        rules = []
        if not os.path.exists(self.rules_file):
            return rules

        with open(self.rules_file, 'r') as f:
            reader = csv.reader(f, delimiter='|')
            for i, row in enumerate(reader, 1):
                if not row or row[0].strip().startswith('#') or not row[0].strip():
                    continue

                if len(row) >= 4:
                    rules.append({
                        'line': i,
                        'source': row[0].strip(),
                        'target': row[1].strip(),
                        'subpath': row[2].strip(),
                        'mode': row[3].strip()
                    })
                elif len(row) >= 3:
                    rules.append({
                        'line': i,
                        'source': row[0].strip(),
                        'target': row[1].strip(),
                        'subpath': row[2].strip(),
                        'mode': 'move'
                    })
        return rules

    def save_rules(self, rules):
        """Save rules to CSV file"""
        # Read original file to preserve comments
        original_lines = []
        if os.path.exists(self.rules_file):
            with open(self.rules_file, 'r') as f:
                original_lines = f.readlines()

        # Create backup
        backup_file = f"{self.rules_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if original_lines:
            with open(backup_file, 'w') as f:
                f.writelines(original_lines)

        # Write new rules file
        with open(self.rules_file, 'w') as f:
            # Write header
            f.write("# Unified Music Storage Rules\n")
            f.write("# SOURCE_PATH|TARGET|DEST_SUBPATH|MODE\n")
            f.write("# TARGET: SSD, NAS, or Local\n")
            f.write("# MODE: move (migrate+symlink), copy (backup only)\n\n")

            # Group rules by category
            categories = {}
            for rule in rules:
                category = self._categorize_rule(rule)
                if category not in categories:
                    categories[category] = []
                categories[category].append(rule)

            # Write rules by category
            for category, category_rules in categories.items():
                f.write(f"# {category}\n")
                for rule in category_rules:
                    f.write(f"{rule['source']}|{rule['target']}|{rule['subpath']}|{rule['mode']}\n")
                f.write("\n")

    def _categorize_rule(self, rule):
        """Categorize a rule based on its source path"""
        source = rule['source'].lower()
        if 'native instruments' in source:
            return 'Native Instruments'
        elif 'uvi' in source:
            return 'UVI Products'
        elif 'arturia' in source:
            return 'Arturia'
        elif 'logic' in source:
            return 'Logic Pro'
        elif 'samples' in source:
            return 'Sample Libraries'
        elif 'projects' in source or 'music' in source:
            return 'Projects'
        elif '/library/application support' in source:
            return 'System Content'
        elif 'library/application support' in source or 'documents' in source:
            return 'User Settings'
        else:
            return 'Other'

class LogMonitor:
    def __init__(self, log_file):
        self.log_file = log_file

    def get_recent_logs(self, lines=50):
        """Get recent log entries"""
        if not os.path.exists(self.log_file):
            return []

        try:
            with open(self.log_file, 'r') as f:
                all_lines = f.readlines()
                return [line.strip() for line in all_lines[-lines:]]
        except Exception:
            return []

    def get_log_stats(self):
        """Get log statistics"""
        if not os.path.exists(self.log_file):
            return {'total_lines': 0, 'errors': 0, 'warnings': 0}

        total_lines = 0
        errors = 0
        warnings = 0

        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    total_lines += 1
                    if 'ERROR' in line:
                        errors += 1
                    elif 'WARN' in line:
                        warnings += 1
        except Exception:
            pass

        return {'total_lines': total_lines, 'errors': errors, 'warnings': warnings}

# Initialize managers
rules_manager = RulesManager(RULES_FILE)
log_monitor = LogMonitor(LOG_FILE)

@app.route('/')
def index():
    """Main dashboard"""
    rules = rules_manager.load_rules()
    log_stats = log_monitor.get_log_stats()
    recent_logs = log_monitor.get_recent_logs(10)

    # Group rules by target
    rules_by_target = {'SSD': [], 'NAS': [], 'Local': []}
    for rule in rules:
        target = rule['target'].upper()
        if target in rules_by_target:
            rules_by_target[target].append(rule)

    return render_template('index.html',
                         rules_by_target=rules_by_target,
                         log_stats=log_stats,
                         recent_logs=recent_logs)

@app.route('/rules')
def rules():
    """Rules management page"""
    rules = rules_manager.load_rules()
    return render_template('rules.html', rules=rules)

@app.route('/api/rules', methods=['GET', 'POST'])
def api_rules():
    """API endpoint for rules management"""
    if request.method == 'GET':
        rules = rules_manager.load_rules()
        return jsonify(rules)

    elif request.method == 'POST':
        try:
            new_rules = request.json
            rules_manager.save_rules(new_rules)
            flash('Rules saved successfully!', 'success')
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/execute', methods=['POST'])
def api_execute():
    """Execute the music storage manager script"""
    try:
        data = request.json
        dry_run = data.get('dry_run', True)
        verbose = data.get('verbose', False)
        only_filter = data.get('only_filter', '')
        skip_nas = data.get('skip_nas', False)

        cmd = [SCRIPT_PATH]
        if dry_run:
            cmd.append('-n')
        if verbose:
            cmd.append('-v')
        if only_filter:
            cmd.extend(['--only', only_filter])
        if skip_nas:
            cmd.append('--skip-nas')

        # Check if script exists
        if not os.path.exists(SCRIPT_PATH):
            return jsonify({'status': 'error', 'message': f'Script not found: {SCRIPT_PATH}'}), 404

        # Run the script with longer timeout and environment variables
        timeout = 180  # 3 minutes for all operations

        # Set environment variables to speed up dry runs
        env = os.environ.copy()
        if dry_run:
            # Skip NAS mounting for dry runs by setting a flag
            env['MSM_SKIP_NAS_MOUNT'] = '1'

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE_DIR, env=env)

        return jsonify({
            'status': 'success',
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'command': ' '.join(cmd)
        })

    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'message': 'Operation timed out'}), 408
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/logs')
def logs():
    """Log viewing page"""
    lines = request.args.get('lines', 100, type=int)
    recent_logs = log_monitor.get_recent_logs(lines)
    log_stats = log_monitor.get_log_stats()

    return render_template('logs.html',
                         logs=recent_logs,
                         log_stats=log_stats,
                         lines=lines)

@app.route('/api/logs')
def api_logs():
    """API endpoint for log data"""
    lines = request.args.get('lines', 50, type=int)
    logs = log_monitor.get_recent_logs(lines)
    stats = log_monitor.get_log_stats()

    return jsonify({'logs': logs, 'stats': stats})

@app.route('/api/test')
def api_test():
    """Test endpoint to verify script accessibility"""
    try:
        # Test if script exists and is executable
        script_exists = os.path.exists(SCRIPT_PATH)
        script_executable = os.access(SCRIPT_PATH, os.X_OK) if script_exists else False

        # Test basic command
        test_result = None
        if script_executable:
            try:
                test_result = subprocess.run([SCRIPT_PATH, '--help'],
                                           capture_output=True, text=True, timeout=10, cwd=BASE_DIR)
            except Exception as e:
                test_result = {'error': str(e)}

        return jsonify({
            'script_path': SCRIPT_PATH,
            'script_exists': script_exists,
            'script_executable': script_executable,
            'cwd': BASE_DIR,
            'test_result': {
                'returncode': getattr(test_result, 'returncode', None),
                'stdout': getattr(test_result, 'stdout', None),
                'stderr': getattr(test_result, 'stderr', None),
                'error': test_result.get('error') if isinstance(test_result, dict) else None
            } if test_result else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-logs', methods=['POST'])
def api_clear_logs():
    """Clear the log file and keep only last 5 backups"""
    try:
        if os.path.exists(LOG_FILE):
            # Create backup before clearing
            backup_file = f"{LOG_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(LOG_FILE, backup_file)

        # Clean up old backups - keep only last 5
        cleanup_old_backups()

        # Create new empty log file
        with open(LOG_FILE, 'w') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Log file cleared\n")

        return jsonify({
            'status': 'success',
            'message': 'Log file cleared successfully'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Failed to clear logs: {str(e)}'
        }), 500

def cleanup_old_backups():
    """Keep only the last 5 log backup files"""
    import glob

    # Find all backup files
    backup_pattern = f"{LOG_FILE}.backup.*"
    backup_files = glob.glob(backup_pattern)

    # Sort by modification time (newest first)
    backup_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

    # Remove files beyond the first 5
    files_to_remove = backup_files[5:]

    for file_path in files_to_remove:
        try:
            os.remove(file_path)
            print(f"Removed old backup: {file_path}")
        except Exception as e:
            print(f"Failed to remove backup {file_path}: {e}")

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    app.run(debug=True, host='127.0.0.1', port=5001)