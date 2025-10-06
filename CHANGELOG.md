# Changelog

All notable changes to the Music Storage Manager project.

## [2.0.0] - 2025-10-05

### 🎉 Major Release: Desktop Application & Web Interface

#### ✨ New Features

**Desktop Application**
- **Native macOS App**: PyWebView-powered desktop application with native window controls
- **Multi-Interface Support**: Choose between desktop app, web interface, or command line
- **Real-time Monitoring**: Live execution output and log viewing in the UI

**Enhanced Command Line**
- **--skip-nas Option**: Skip NAS rules to avoid mounting issues (resolves permission errors)
- **Improved Help**: Comprehensive usage documentation with examples
- **Better Error Handling**: Clear error messages and recovery suggestions

**Web Interface Features**
- **Dashboard**: Quick actions, rules summary, and recent activity overview
- **Rule Management**: Visual editor with categorized rule organization
- **Log Monitoring**: Live log viewing with search, filtering, and statistics
- **Execution Control**: Safe dry-run defaults with verbose output options

**Log Management**
- **Clear Logs Function**: One-click log clearing with automatic backup creation
- **Log Rotation**: Automatically keeps only the last 5 log backups
- **Timestamped Backups**: All backups include creation timestamps

#### 🔧 Improvements

**Safety & Reliability**
- **Dry Run Default**: All interfaces default to safe testing mode
- **Skip NAS Default**: Web interface defaults to skip NAS rules
- **Automatic Backups**: Rule editing creates timestamped backups
- **Permission Validation**: Better detection of access issues

**User Experience**
- **Responsive UI**: Bootstrap-based interface works on all screen sizes
- **Real-time Feedback**: Live progress indicators and status updates
- **Intuitive Controls**: Clear labeling and helpful tooltips
- **Error Recovery**: Graceful handling of common issues

#### 📁 New Files
- `desktop_app.py` - Native desktop application wrapper
- `app.py` - Flask web interface backend
- `templates/` - Web interface HTML templates
- `requirements.txt` - Python dependency management
- `README_DESKTOP.md` - Desktop application documentation
- `venv/` - Python virtual environment

#### 🔄 Updated Files
- `music-storage-manager.zsh` - Added --skip-nas option and improved logging
- `music-storage-rules-unified.csv` - Reorganized and categorized rules
- `README.txt` - Comprehensive documentation with all new features

#### 🐛 Bug Fixes
- **Permission Errors**: --skip-nas option bypasses NAS mounting issues
- **Log Accumulation**: Automatic rotation prevents unlimited log growth
- **Rule Validation**: Better error checking and user feedback
- **Mount Detection**: More reliable storage availability checking

#### 🔧 Technical Changes
- **Python Backend**: Flask application with RESTful API endpoints
- **Virtual Environment**: Isolated Python dependency management
- **PyWebView Integration**: Native desktop app experience
- **Bootstrap UI**: Modern, responsive web interface
- **Log API**: Programmatic access to logs and statistics

### 📖 Usage Examples

**Desktop App:**
```bash
python desktop_app.py
```

**Command Line with New Options:**
```bash
./music-storage-manager.zsh -n -v --skip-nas
```

**Web Interface:**
```bash
python desktop_app.py --web
```

### 🚀 Migration Guide

1. **Install Dependencies**: `pip install -r requirements.txt`
2. **Test New Features**: Use `--skip-nas` for initial testing
3. **Backup Rules**: Existing rules are preserved and enhanced
4. **Choose Interface**: Desktop app, web interface, or command line

---

## [1.0.0] - Previous Version

### Initial Features
- Zsh-based file management script
- CSV-based rules system
- NAS and SSD support
- Symlink creation for moved files
- Basic logging functionality