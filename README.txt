Music Storage Manager — Quick Setup
===================================

Files included:
- music-storage-manager.zsh
- music-storage-rules.example.csv
- mount-unraid.scpt
- com.user.mount-unraid.plist
- mount-unraid.sh

Suggested steps:
1) Copy files to your Mac:
   - Place `music-storage-manager.zsh` anywhere (e.g., ~/bin) and `chmod +x` it.
   - Copy `music-storage-rules.example.csv` to `~/.music-storage-rules.csv` and edit.
   - Place `mount-unraid.scpt` in `~/Library/Scripts/` (create folder if missing).
   - Place `com.user.mount-unraid.plist` in `~/Library/LaunchAgents/`.

2) Set your volume names:
   - Ensure your SSD is mounted at /Volumes/Instruments (or export SSD_ROOT before running).
   - Ensure your Unraid share mounts to /Volumes/Unraid (the AppleScript uses Keychain).

3) Load the LaunchAgent:
   launchctl load ~/Library/LaunchAgents/com.user.mount-unraid.plist

4) Run a dry run first:
   ./music-storage-manager.zsh -n -v

5) Move for real:
   ./music-storage-manager.zsh -v

Notes:
- Rules format: SOURCE_PATH|TARGET|DEST_SUBPATH|MODE
  TARGET = SSD or UNRAID. MODE = move or copy.
- Override roots:
    SSD_ROOT="/Volumes/MySSD" UNRAID_ROOT="/Volumes/Media" ./music-storage-manager.zsh
