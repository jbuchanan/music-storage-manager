#!/usr/bin/env python3
"""
Music Storage Manager Web Interface
A Flask web application for managing music storage rules and monitoring operations.
"""

import os
import csv
import json
import logging
import subprocess
import secrets
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, g

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, continue with system env vars only

app = Flask(__name__)

# Security: Load secret key from environment or generate a temporary one
app.secret_key = os.getenv('FLASK_SECRET_KEY')
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    import sys
    if not sys.stdout.isatty():
        # Only log warning in non-interactive mode
        pass
    else:
        print("WARNING: FLASK_SECRET_KEY not set. Using temporary key. Set FLASK_SECRET_KEY in .env for production.")

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(BASE_DIR, 'music-storage-rules-unified.csv')
LOG_FILE = os.getenv('MSM_LOG_FILE', os.path.join(BASE_DIR, 'music-storage-manager.log'))
APP_LOG_FILE = os.getenv('MSM_APP_LOG_FILE', os.path.join(BASE_DIR, 'music-storage-manager-app.log'))
SCRIPT_PATH = os.path.join(BASE_DIR, 'music-storage-manager.zsh')

# Storage paths (from environment or defaults matching shell script)
SSD_ROOT = os.getenv('SSD_ROOT', '/Volumes/Instruments')
NAS_ROOT = os.getenv('NAS_ROOT', '/Volumes/Music')

# Error alerting configuration
ALERT_WEBHOOK_URL = os.getenv('ALERT_WEBHOOK_URL')
ALERT_WEBHOOK_ENABLED = os.getenv('ALERT_WEBHOOK_ENABLED', 'false').lower() == 'true'

# Utility functions
def sanitize_path_for_logging(path):
    """Sanitize paths in logs to avoid exposing sensitive information"""
    if not path:
        return path

    # Replace user home directory with ~
    home = os.path.expanduser('~')
    if path.startswith(home):
        return path.replace(home, '~', 1)

    return path

def send_error_alert(error_type, message, details=None):
    """Send error alert to configured webhook (Slack, Discord, etc.)"""
    if not ALERT_WEBHOOK_ENABLED or not ALERT_WEBHOOK_URL:
        return

    try:
        import requests

        payload = {
            'text': f'🚨 Music Storage Manager Alert: {error_type}',
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'*{error_type}*\n{message}'
                    }
                }
            ]
        }

        if details:
            payload['blocks'].append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f'*Details:*\n```{details}```'
                }
            })

        payload['blocks'].append({
            'type': 'context',
            'elements': [{
                'type': 'mrkdwn',
                'text': f'Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            }]
        })

        response = requests.post(
            ALERT_WEBHOOK_URL,
            json=payload,
            timeout=5
        )

        if response.status_code != 200:
            app.logger.warning(f'Failed to send alert: HTTP {response.status_code}')

    except Exception as e:
        # Don't let alerting errors break the application
        app.logger.debug(f'Error sending alert: {e}')

# Configure logging
def setup_logging():
    """Configure application logging with file and console handlers"""
    # Create formatters
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Configure Flask logger
    app.logger.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

    # Reduce noise from werkzeug
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    app.logger.info('Logging configured successfully')
    app.logger.debug(f'Log file: {APP_LOG_FILE}')

setup_logging()

# Request/Response logging middleware
@app.before_request
def log_request_info():
    """Log incoming request details"""
    g.start_time = datetime.now()
    app.logger.debug(f'Request: {request.method} {request.path}')
    if request.method in ['POST', 'PUT', 'PATCH']:
        # Log request body for non-GET requests (but sanitize sensitive data)
        if request.is_json:
            app.logger.debug(f'Request JSON: {request.get_json()}')
        elif request.form:
            app.logger.debug(f'Request Form: {dict(request.form)}')

@app.after_request
def log_response_info(response):
    """Log response details and request duration"""
    if hasattr(g, 'start_time'):
        duration = (datetime.now() - g.start_time).total_seconds()
        app.logger.info(
            f'{request.method} {request.path} - {response.status_code} '
            f'({duration:.3f}s)'
        )
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    """Log unhandled exceptions"""
    app.logger.error(f'Unhandled exception: {str(e)}', exc_info=True)

    # Send alert for unhandled exceptions
    import traceback
    send_error_alert(
        'Unhandled Exception',
        f'An unhandled exception occurred in the web application',
        traceback.format_exc()
    )

    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

class RulesManager:
    def __init__(self, rules_file):
        self.rules_file = rules_file

    def load_rules(self):
        """Load rules from CSV file"""
        rules = []
        if not os.path.exists(self.rules_file):
            app.logger.warning(f'Rules file not found: {self.rules_file}')
            return rules

        try:
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
            app.logger.debug(f'Loaded {len(rules)} rules from {self.rules_file}')
        except Exception as e:
            app.logger.error(f'Error loading rules: {e}', exc_info=True)

        return rules

    def save_rules(self, rules):
        """Save rules to CSV file"""
        try:
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
                app.logger.info(f'Created rules backup: {backup_file}')

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

            app.logger.info(f'Saved {len(rules)} rules to {self.rules_file}')
        except Exception as e:
            app.logger.error(f'Error saving rules: {e}', exc_info=True)
            raise

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
        # Available log files
        self.log_files = {
            'script': LOG_FILE,
            'app': APP_LOG_FILE,
            'simple-app': os.path.join(BASE_DIR, 'music-storage-manager-simple-app.log')
        }

    def get_recent_logs(self, lines=50, log_source='script'):
        """Get recent log entries from specified log source"""
        log_file = self.log_files.get(log_source, self.log_file)

        if not os.path.exists(log_file):
            app.logger.debug(f'Log file not found: {log_file}')
            return []

        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                return [line.strip() for line in all_lines[-lines:]]
        except Exception as e:
            app.logger.error(f'Error reading log file: {e}', exc_info=True)
            return []

    def get_log_stats(self, log_source='script'):
        """Get log statistics for specified log source"""
        log_file = self.log_files.get(log_source, self.log_file)

        if not os.path.exists(log_file):
            app.logger.debug(f'Log file not found for stats: {log_file}')
            return {'total_lines': 0, 'errors': 0, 'warnings': 0}

        total_lines = 0
        errors = 0
        warnings = 0

        try:
            with open(log_file, 'r') as f:
                for line in f:
                    total_lines += 1
                    if 'ERROR' in line:
                        errors += 1
                    elif 'WARN' in line:
                        warnings += 1
        except Exception as e:
            app.logger.error(f'Error getting log stats: {e}', exc_info=True)

        return {'total_lines': total_lines, 'errors': errors, 'warnings': warnings}

    def get_available_logs(self):
        """Get list of available log files with metadata"""
        import glob
        logs = []

        for name, path in self.log_files.items():
            log_info = {
                'name': name,
                'path': path,
                'exists': os.path.exists(path),
                'size': 0,
                'size_human': '0 B',
                'backups': 0
            }

            if os.path.exists(path):
                size = os.path.getsize(path)
                log_info['size'] = size
                log_info['size_human'] = self._format_size(size)

                # Count backup files
                backup_pattern = f"{path}.*"
                backups = glob.glob(backup_pattern)
                log_info['backups'] = len(backups)

            logs.append(log_info)

        return logs

    def get_rotation_status(self):
        """Get rotation status for all log files"""
        import glob

        rotation_info = []

        for name, path in self.log_files.items():
            if not os.path.exists(path):
                continue

            size = os.path.getsize(path)
            max_size = 10 * 1024 * 1024  # 10MB
            percentage = (size / max_size) * 100

            # Count backups
            backup_pattern = f"{path}.*"
            backups = glob.glob(backup_pattern)
            backup_files = sorted(backups, key=lambda x: os.path.getmtime(x), reverse=True)

            rotation_info.append({
                'name': name,
                'path': sanitize_path_for_logging(path),
                'size': size,
                'size_human': self._format_size(size),
                'max_size': max_size,
                'max_size_human': self._format_size(max_size),
                'percentage': round(percentage, 1),
                'backups': len(backup_files),
                'max_backups': 5,
                'backup_files': [
                    {
                        'path': sanitize_path_for_logging(bf),
                        'size': self._format_size(os.path.getsize(bf)),
                        'modified': datetime.fromtimestamp(os.path.getmtime(bf)).isoformat()
                    }
                    for bf in backup_files[:5]  # Show only latest 5
                ]
            })

        return rotation_info

    @staticmethod
    def _format_size(bytes):
        """Format bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"

class OperationMetrics:
    """Track operation metrics and statistics"""

    def __init__(self):
        self.metrics_file = os.path.join(BASE_DIR, 'metrics.json')
        self._ensure_metrics_file()

    def _ensure_metrics_file(self):
        """Create metrics file if it doesn't exist"""
        if not os.path.exists(self.metrics_file):
            self._save_metrics({
                'operations': [],
                'summary': {
                    'total': 0,
                    'success': 0,
                    'failed': 0,
                    'timeouts': 0
                }
            })

    def _load_metrics(self):
        """Load metrics from file"""
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            app.logger.error(f'Error loading metrics: {e}', exc_info=True)

        return {'operations': [], 'summary': {'total': 0, 'success': 0, 'failed': 0, 'timeouts': 0}}

    def _save_metrics(self, metrics):
        """Save metrics to file"""
        try:
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
        except Exception as e:
            app.logger.error(f'Error saving metrics: {e}', exc_info=True)

    def record_operation(self, command, returncode, duration, dry_run=True):
        """Record an operation execution"""
        metrics = self._load_metrics()

        operation = {
            'timestamp': datetime.now().isoformat(),
            'command': command,
            'returncode': returncode,
            'duration': round(duration, 2),
            'success': returncode == 0,
            'dry_run': dry_run
        }

        # Add to operations list (keep last 100)
        metrics['operations'].insert(0, operation)
        metrics['operations'] = metrics['operations'][:100]

        # Update summary
        metrics['summary']['total'] += 1
        if returncode == 0:
            metrics['summary']['success'] += 1
        else:
            metrics['summary']['failed'] += 1

        self._save_metrics(metrics)

    def record_timeout(self, command):
        """Record an operation timeout"""
        metrics = self._load_metrics()

        operation = {
            'timestamp': datetime.now().isoformat(),
            'command': command,
            'returncode': -1,
            'duration': None,
            'success': False,
            'timeout': True
        }

        metrics['operations'].insert(0, operation)
        metrics['operations'] = metrics['operations'][:100]

        metrics['summary']['total'] += 1
        metrics['summary']['timeouts'] += 1
        metrics['summary']['failed'] += 1

        self._save_metrics(metrics)

    def get_metrics(self, limit=50):
        """Get recent metrics"""
        metrics = self._load_metrics()
        return {
            'operations': metrics['operations'][:limit],
            'summary': metrics['summary'],
            'success_rate': round(
                (metrics['summary']['success'] / metrics['summary']['total'] * 100)
                if metrics['summary']['total'] > 0 else 0,
                1
            )
        }

    def get_dashboard_stats(self):
        """Get aggregated stats for dashboard"""
        metrics = self._load_metrics()
        operations = metrics['operations']

        # Calculate time-based statistics
        now = datetime.now()
        today_ops = [op for op in operations if
                     datetime.fromisoformat(op['timestamp']).date() == now.date()]
        week_ops = [op for op in operations if
                    (now - datetime.fromisoformat(op['timestamp'])).days <= 7]

        # Calculate average duration (excluding timeouts)
        durations = [op['duration'] for op in operations if op.get('duration')]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Find most common errors (non-zero return codes)
        error_codes = {}
        for op in operations:
            if op['returncode'] != 0:
                code = op['returncode']
                error_codes[code] = error_codes.get(code, 0) + 1

        return {
            'all_time': metrics['summary'],
            'today': {
                'total': len(today_ops),
                'success': sum(1 for op in today_ops if op['success']),
                'failed': sum(1 for op in today_ops if not op['success'])
            },
            'this_week': {
                'total': len(week_ops),
                'success': sum(1 for op in week_ops if op['success']),
                'failed': sum(1 for op in week_ops if not op['success'])
            },
            'avg_duration': round(avg_duration, 2),
            'common_errors': sorted(error_codes.items(), key=lambda x: x[1], reverse=True)[:5]
        }

# Initialize managers
rules_manager = RulesManager(RULES_FILE)
log_monitor = LogMonitor(LOG_FILE)
operation_metrics = OperationMetrics()

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
            app.logger.error(f'Script not found: {SCRIPT_PATH}')
            return jsonify({'status': 'error', 'message': f'Script not found: {SCRIPT_PATH}'}), 404

        # Run the script with longer timeout and environment variables
        timeout = 180  # 3 minutes for all operations

        # Set environment variables to speed up dry runs
        env = os.environ.copy()
        if dry_run:
            # Skip NAS mounting for dry runs by setting a flag
            env['MSM_SKIP_NAS_MOUNT'] = '1'

        app.logger.info(f'Executing script: {" ".join(cmd)}')
        start_time = datetime.now()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE_DIR, env=env)
        duration = (datetime.now() - start_time).total_seconds()

        app.logger.info(f'Script completed with return code: {result.returncode} in {duration:.2f}s')

        # Record metrics
        operation_metrics.record_operation(' '.join(cmd), result.returncode, duration, dry_run)

        if result.returncode != 0:
            app.logger.warning(f'Script exited with non-zero status: {result.returncode}')
            if result.stderr:
                app.logger.warning(f'Script stderr: {result.stderr}')

            # Send alert for script failures (non-dry-run only)
            if not dry_run:
                send_error_alert(
                    'Script Execution Failed',
                    f'Music storage manager script failed with exit code {result.returncode}',
                    result.stderr[:500] if result.stderr else 'No error output'
                )

        return jsonify({
            'status': 'success',
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'command': ' '.join(cmd),
            'duration': duration
        })

    except subprocess.TimeoutExpired:
        app.logger.error(f'Script execution timed out after {timeout}s')

        # Record timeout in metrics
        operation_metrics.record_timeout(' '.join(cmd))

        send_error_alert(
            'Script Timeout',
            f'Music storage manager script timed out after {timeout} seconds',
            f'Command: {" ".join(cmd)}'
        )
        return jsonify({'status': 'error', 'message': 'Operation timed out'}), 408
    except Exception as e:
        app.logger.error(f'Script execution error: {e}', exc_info=True)
        send_error_alert(
            'Script Execution Error',
            f'Failed to execute music storage manager script',
            str(e)
        )
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
    log_source = request.args.get('source', 'script', type=str)
    logs = log_monitor.get_recent_logs(lines, log_source)
    stats = log_monitor.get_log_stats(log_source)

    return jsonify({'logs': logs, 'stats': stats, 'source': log_source})

@app.route('/api/logs/sources')
def api_log_sources():
    """Get available log sources"""
    return jsonify({
        'sources': log_monitor.get_available_logs()
    })

@app.route('/api/logs/rotation')
def api_log_rotation():
    """Get log rotation status"""
    return jsonify({
        'rotation_status': log_monitor.get_rotation_status()
    })

@app.route('/api/metrics')
def api_metrics():
    """Get operation metrics"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(operation_metrics.get_metrics(limit))

@app.route('/api/metrics/dashboard')
def api_metrics_dashboard():
    """Get aggregated metrics for dashboard"""
    return jsonify(operation_metrics.get_dashboard_stats())

@app.route('/health')
@app.route('/api/health')
def health():
    """Health check endpoint for monitoring"""
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }

        # Check script accessibility
        script_exists = os.path.exists(SCRIPT_PATH)
        script_executable = os.access(SCRIPT_PATH, os.X_OK) if script_exists else False
        health_status['checks']['script'] = {
            'exists': script_exists,
            'executable': script_executable,
            'path': SCRIPT_PATH,
            'healthy': script_exists and script_executable
        }

        # Check SSD mount
        ssd_mounted = os.path.exists(SSD_ROOT) and os.path.ismount(SSD_ROOT)
        health_status['checks']['ssd'] = {
            'path': SSD_ROOT,
            'mounted': ssd_mounted,
            'exists': os.path.exists(SSD_ROOT),
            'healthy': os.path.exists(SSD_ROOT)
        }

        # Check NAS mount (optional)
        nas_mounted = os.path.exists(NAS_ROOT) and os.path.ismount(NAS_ROOT)
        health_status['checks']['nas'] = {
            'path': NAS_ROOT,
            'mounted': nas_mounted,
            'exists': os.path.exists(NAS_ROOT),
            'healthy': True,  # NAS is optional
            'optional': True
        }

        # Check log files writability
        log_writable = os.access(os.path.dirname(LOG_FILE), os.W_OK)
        app_log_writable = os.access(os.path.dirname(APP_LOG_FILE), os.W_OK)
        health_status['checks']['logging'] = {
            'script_log_writable': log_writable,
            'app_log_writable': app_log_writable,
            'healthy': log_writable and app_log_writable
        }

        # Check rules file
        rules_readable = os.path.exists(RULES_FILE) and os.access(RULES_FILE, os.R_OK)
        health_status['checks']['rules'] = {
            'exists': os.path.exists(RULES_FILE),
            'readable': rules_readable,
            'path': RULES_FILE,
            'healthy': rules_readable
        }

        # Overall health
        all_critical_healthy = (
            health_status['checks']['script']['healthy'] and
            health_status['checks']['logging']['healthy'] and
            health_status['checks']['rules']['healthy']
        )

        health_status['status'] = 'healthy' if all_critical_healthy else 'degraded'

        status_code = 200 if all_critical_healthy else 503
        return jsonify(health_status), status_code

    except Exception as e:
        app.logger.error(f'Health check error: {e}', exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

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
            app.logger.info(f'Created log backup before clearing: {backup_file}')

        # Clean up old backups - keep only last 5
        cleanup_old_backups()

        # Create new empty log file
        with open(LOG_FILE, 'w') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Log file cleared\n")

        app.logger.info('Log file cleared successfully')
        return jsonify({
            'status': 'success',
            'message': 'Log file cleared successfully'
        })
    except Exception as e:
        app.logger.error(f'Failed to clear logs: {e}', exc_info=True)
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
            app.logger.info(f"Removed old backup: {file_path}")
        except Exception as e:
            app.logger.error(f"Failed to remove backup {file_path}: {e}")

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    app.run(debug=True, host='127.0.0.1', port=5001)