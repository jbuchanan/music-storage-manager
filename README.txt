Music Storage Manager — Complete Guide
======================================

A comprehensive tool for managing music libraries across SSD, NAS, and local storage with both command-line and desktop interfaces.

## What's New (Latest Version)

### ✅ Desktop Application
- **Native macOS app** using PyWebView
- **Web interface** with Bootstrap UI
- **Real-time monitoring** and log viewing
- **Rule management** with visual interface

### ✅ Enhanced Features
- **--skip-nas option** to avoid mounting issues
- **Clear logs functionality** with automatic rotation (keeps last 5 backups)
- **Improved error handling** and user feedback
- **Live execution output** in web interface

## Files Included

### Core Components
- `music-storage-manager.zsh` - Main script for file operations
- `music-storage-rules-unified.csv` - Rule definitions
- `app.py` - Flask web interface
- `desktop_app.py` - Native desktop wrapper
- `templates/` - Web interface templates

### Optional Legacy Files
- `mount-nas.scpt` - AppleScript for NAS mounting
- `com.user.mount-nas.plist` - LaunchAgent for auto-mounting
- `mount-nas.sh` - Shell script for mounting

## Quick Start

### 1. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Choose Your Interface

**Desktop App (Recommended):**
```bash
source venv/bin/activate
python desktop_app.py
```

**Command Line:**
```bash
./music-storage-manager.zsh -n -v --skip-nas
```

**Web Interface:**
```bash
source venv/bin/activate
python desktop_app.py --web
```

### 3. Configure Storage Locations
- **SSD**: `/Volumes/Instruments` (or set `SSD_ROOT` env var)
- **NAS**: `/Volumes/Music` (or set `NAS_ROOT` env var)
- **Rules**: Edit `music-storage-rules-unified.csv`

## New Command Line Options

```bash
./music-storage-manager.zsh [options]

Options:
  -n              Dry run (no changes)
  -v              Verbose logging
  --skip-nas      Skip all NAS rules (avoid mounting issues)
  --only X        Only process rules containing substring X
  --since DAYS    Only process files modified in last N days
  -r FILE         Use custom rules file
  -h, --help      Show help
```

## Web Interface Features

### Dashboard
- **Quick Actions**: Dry run and execute buttons
- **Rules Summary**: Count by target (SSD/NAS/Local)
- **Recent Activity**: Latest log entries

### Rule Management
- **Visual Editor**: Add, edit, delete rules
- **Categorized View**: Organized by vendor/type
- **Validation**: Real-time rule checking

### Log Monitoring
- **Live Logs**: Real-time operation monitoring
- **Clear Logs**: One-click log clearing with backup
- **Filtering**: Search and filter log entries
- **Statistics**: Error/warning counts

### Execution Control
- **Dry Run Mode**: Safe testing (default)
- **Verbose Output**: Detailed operation logs
- **Skip NAS Option**: Avoid mounting issues (default enabled)
- **Filter Options**: Process specific subsets

## Safety Features

### Automatic Backups
- **Log Rotation**: Keeps last 5 log backups automatically
- **Rule Backups**: Timestamped backups when editing rules
- **Dry Run Default**: All interfaces default to safe mode

### Error Handling
- **Permission Checks**: Validates access before operations
- **Mount Detection**: Checks storage availability
- **Rollback Support**: Undo capability for failed operations

## Rules Format

```csv
SOURCE_PATH|TARGET|DEST_SUBPATH|MODE
```

- **SOURCE_PATH**: Absolute path (`~` and `$HOME` supported)
- **TARGET**: `SSD`, `NAS`, or `Local`
- **DEST_SUBPATH**: Subdirectory under target root
- **MODE**: `move` (migrate+symlink) or `copy` (backup only)

### Example Rules
```csv
# High-performance libraries on SSD
$HOME/Music/Samples/Native Instruments|SSD|Samples/NI|move

# Large libraries to NAS
$HOME/Native Instruments/Kontakt Factory Library|NAS|NI/Libraries|move

# Keep local for performance
$HOME/Native Instruments/Battery 4|Local|N/A|copy
```

## Environment Variables

```bash
# Override default storage locations
export SSD_ROOT="/Volumes/MySSD"
export NAS_ROOT="/Volumes/MyNAS"

# Skip NAS mounting (for dry runs)
export MSM_SKIP_NAS_MOUNT=1
```

## Troubleshooting

### Common Issues

**Permission Denied:**
```bash
# Use --skip-nas to avoid mounting issues
./music-storage-manager.zsh -n -v --skip-nas
```

**Desktop App Won't Start:**
```bash
# Install PyWebView dependencies
source venv/bin/activate
pip install -r requirements.txt
```

**NAS Mount Issues:**
```bash
# Mount manually first
open "smb://your-nas-server/Music"
# Then save credentials to Keychain
```

### Log Files
- **Main Log**: `music-storage-manager.log`
- **Backups**: `music-storage-manager.log.backup.YYYYMMDD_HHMMSS`
- **Rollback**: `music-storage-manager.rollback` (if available)

## Migration from Previous Version

1. **Backup your rules**: Copy existing `.music-storage-rules.csv`
2. **Update rules format**: Use new unified CSV format
3. **Install new dependencies**: Run `pip install -r requirements.txt`
4. **Test with dry run**: Use `--skip-nas` for initial testing
