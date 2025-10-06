#!/bin/zsh
# music-storage-manager.zsh
# Move vendor/product folders to SSD or NAS and replace with symlinks.
# Usage:
#   ./music-storage-manager.zsh [-n] [-v] [-r RULES_FILE] [--only TARGET] [--since DAYS]
# Options:
#   -n            Dry run (no changes)
#   -v            Verbose logging
#   -r FILE       Rulesx file path (default: ~/.music-storage-rules.csv)
#   --only X      Only process rules whose source path contains substring X
#   --since DAYS  Only move items modified within last N days (find -mtime)
#
# RULES FILE FORMAT (pipe-delimited, comments start with #):
#   SOURCE_PATH | TARGET | DEST_SUBPATH | MODE
#     - SOURCE_PATH: absolute path to a folder (tilde OK)
#     - TARGET: SSD or NAS
#     - DEST_SUBPATH: subpath under the target root; if blank, uses the folder name
#     - MODE: move (default) or copy
#
# Configure your target roots here (or override with env vars before running):
: ${SSD_ROOT:="/Volumes/Instruments"}        # external SSD volume mountpoint
: ${NAS_ROOT:="/Volumes/Music"}          # NAS SMB mountpoint
: ${NAS_URL:="smb://192.168.50.3/Music"}   # Finder mount URL (relies on Keychain)
: ${LOG_FILE:="./music-storage-manager.log"}

set -o pipefail

dry_run=0
verbose=0
rules_file="./music-storage-rules-unified.csv"
only_substr=""
since_days=""
skip_nas=0

log() {
  local msg="$1"
  local ts="$(date '+%Y-%m-%d %H:%M:%S')"
  echo "[$ts] $msg" | tee -a "$LOG_FILE" >/dev/null
}

vlog() {
  [[ $verbose -eq 1 ]] && log "$1"
}

fail() {
  log "ERROR: $1"
  exit 1
}

# Cache mount status to avoid repeated checks
nas_mount_checked=0
nas_is_mounted=0

# Ensure mount for NAS using Finder/Keychain so credentials aren't in plain text.
ensure_nas_mounted() {
  # Use cached result if already checked
  if [[ $nas_mount_checked -eq 1 ]]; then
    [[ $nas_is_mounted -eq 1 ]] && return 0 || return 1
  fi

  if mount | grep -q "on ${NAS_ROOT} "; then
    vlog "NAS already mounted at ${NAS_ROOT}"
    nas_mount_checked=1
    nas_is_mounted=1
    return 0
  fi
  mkdir -p "${NAS_ROOT}" || fail "Could not create ${NAS_ROOT}"
  vlog "Attempting to mount NAS share ${NAS_URL} at ${NAS_ROOT}"
  # Try AppleScript (uses Keychain creds if previously saved in Finder)
  /usr/bin/osascript <<-APPLESCRIPT
    try
      mount volume "${NAS_URL}"
    on error errMsg number errNum
      do shell script "exit 89"
    end try
APPLESCRIPT
  if [[ $? -ne 0 ]]; then
    log "WARN: osascript mount failed; please mount ${NAS_URL} in Finder once and save password to Keychain."
  fi
  sleep 1
  if ! mount | grep -q "on ${NAS_ROOT} "; then
    # If Finder mounted to a different name, try to detect it
    if [[ -d "/Volumes/$(basename "${NAS_URL}")" ]]; then
      ln -sfn "/Volumes/$(basename "${NAS_URL}")" "${NAS_ROOT}"
      vlog "Linked ${NAS_ROOT} to /Volumes/$(basename "${NAS_URL}")"
    fi
  fi
  if ! [[ -d "${NAS_ROOT}" ]]; then
    nas_mount_checked=1
    nas_is_mounted=0
    fail "NAS mountpoint not available at ${NAS_ROOT}"
  fi
  nas_mount_checked=1
  nas_is_mounted=1
}

ensure_ssd_present() {
  if [[ -d "${SSD_ROOT}" ]]; then
    vlog "SSD detected at ${SSD_ROOT}"
  else
    fail "SSD_ROOT not found: ${SSD_ROOT} (mount your SSD)"
  fi
}

usage() {
  cat <<-EOF
Music Storage Manager - Move music libraries to SSD/NAS with symlinks

USAGE:
  $0 [-n] [-v] [-r RULES_FILE] [--only TARGET] [--since DAYS] [--skip-nas] [-h|--help]

OPTIONS:
  -n            Dry run (no changes, shows what would happen)
  -v            Verbose logging
  -r FILE       Rules file path (default: $rules_file)
  --only X      Only process rules whose source path contains substring X
  --since DAYS  Only move items modified within last N days
  --skip-nas    Skip all NAS rules (only process SSD and Local rules)
  -h, --help    Show this help

CURRENT CONFIGURATION:
  SSD Root:     $SSD_ROOT
  NAS Root:     $NAS_ROOT
  NAS URL:      $NAS_URL
  Rules File:   $rules_file
  Log File:     $LOG_FILE

EXAMPLES:
  $0 -n -v                    # Dry run with verbose output
  $0 --only "Native"          # Only process Native Instruments libraries
  $0 --since 30               # Only process files modified in last 30 days
  $0 -r custom-rules.csv      # Use different rules file

RULES FORMAT (pipe-delimited):
  SOURCE_PATH | TARGET | DEST_SUBPATH | MODE
  - SOURCE_PATH: absolute path (~ and \$HOME supported)
  - TARGET: SSD, NAS, or Local
  - DEST_SUBPATH: subpath under target root (blank = use folder name)
  - MODE: move (migrate+symlink) or copy (backup only)

NOTE: Mount your NAS in Finder once and save credentials to Keychain.
EOF
  exit 0
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n) dry_run=1; shift ;;
    -v) verbose=1; shift ;;
    -r) rules_file="$2"; shift 2 ;;
    --only) only_substr="$2"; shift 2 ;;
    --since) since_days="$2"; shift 2 ;;
    --skip-nas) skip_nas=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

[[ -f "$rules_file" ]] || fail "Rules file not found: $rules_file"

touch "$LOG_FILE" 2>/dev/null || echo "WARN: cannot write to $LOG_FILE"

# Preflight
ensure_ssd_present

# Skip NAS mounting if environment variable is set (for dry runs) or --skip-nas flag is used
if [[ -z "${MSM_SKIP_NAS_MOUNT}" && $skip_nas -eq 0 ]]; then
  ensure_nas_mounted
else
  if [[ $skip_nas -eq 1 ]]; then
    vlog "Skipping NAS mount check (--skip-nas flag is set)"
  else
    vlog "Skipping NAS mount check (MSM_SKIP_NAS_MOUNT is set)"
  fi
fi

move_with_rsync() {
  local src="$1"       # original source dir (expanded)
  local dest="$2"      # destination dir
  local mode="$3"      # "move" or "copy"
  local rsync_cmd="${RSYNC_CMD:-/opt/homebrew/bin/rsync}"
  [[ -x "$rsync_cmd" ]] || rsync_cmd="rsync"

  # rsync options: archive, preserve hardlinks & mac perms, protect spaces, show stats
  local rsync_opts=(-aEH --protect-args --info=stats1,progress2)

  # Optimize for NAS transfers
  case "$dest" in
    "${NAS_ROOT}"*) rsync_opts+=(--compress --partial --inplace) ;;
    "${SSD_ROOT}"*) rsync_opts+=(--partial) ;;
  esac

  # Add progress indicator for large transfers
  local total_size=$(du -sk "$src" 2>/dev/null | cut -f1)
  if [[ -n "$total_size" && $total_size -gt 1048576 ]]; then  # > 1GB
    log "Processing large library (${total_size}KB): $src"
    rsync_opts+=(--progress)
  fi

  # If --since was used, honor it via a file list
  if [[ -n "$since_days" ]]; then
    local filelist
    filelist="$(mktemp)"
    find "$src" -type f -mtime -"$since_days" -print0 >"$filelist"
    if [[ $dry_run -eq 1 ]]; then
      "$rsync_cmd" -n "${rsync_opts[@]}" --files-from="$filelist" --from0 "$src/" "$dest/"
    else
      "$rsync_cmd"    "${rsync_opts[@]}" --files-from="$filelist" --from0 "$src/" "$dest/"
    fi
    rm -f "$filelist"
  else
    if [[ $dry_run -eq 1 ]]; then
      "$rsync_cmd" -n "${rsync_opts[@]}" "$src/" "$dest/"
    else
      "$rsync_cmd"    "${rsync_opts[@]}" "$src/" "$dest/"
    fi
  fi
  local rc=$?
  [[ $rc -eq 0 ]] || fail "rsync failed ($rc) for $src -> $dest"

  # For "move": atomically swap the source dir with a symlink to dest
  if [[ "$mode" == "move" && $dry_run -eq 0 ]]; then
    local backup="${src}.prelink.$$"
    local rollback_file="${LOG_FILE%.log}.rollback"

    # Log rollback info before operation
    echo "MOVE|$(date '+%Y-%m-%d %H:%M:%S')|$src|$backup|$dest" >> "$rollback_file"

    mv "$src" "$backup" || fail "Cannot rename $src (is it open in a DAW?)"
    if ln -sfn "$dest" "$src"; then
      rm -rf "$backup"
      # Remove rollback entry on success
      grep -v "^MOVE|.*|$src|" "$rollback_file" > "${rollback_file}.tmp" 2>/dev/null && mv "${rollback_file}.tmp" "$rollback_file"
    else
      mv "$backup" "$src"
      fail "Failed to link $src -> $dest"
    fi
  fi
}

process_rule() {
  local src="$1"
  local target="$2"
  local subpath="$3"
  local mode="$4"
  [[ -z "$mode" ]] && mode="move"

  # Expand ~ and resolve
  src_expanded="$src"
  src_expanded="${src_expanded/#\~/$HOME}"
  src_expanded="${src_expanded//\$HOME/$HOME}"

  if [[ ! -d "$src_expanded" ]]; then
    log "SKIP (missing): $src_expanded"
    return
  fi

  if [[ -n "$only_substr" && "$src_expanded" != *"$only_substr"* ]]; then
    vlog "Skip due to --only filter: $src_expanded"
    return
  fi

  local dest_root
  case "$target" in
    SSD|ssd) dest_root="$SSD_ROOT" ;;
    NAS|nas)
      dest_root="$NAS_ROOT"
      # Skip NAS rules if --skip-nas flag is used
      if [[ $skip_nas -eq 1 ]]; then
        log "SKIP (NAS rules disabled): $src_expanded"
        return
      fi
      # Skip NAS rules if NAS mounting was skipped
      if [[ -n "${MSM_SKIP_NAS_MOUNT}" ]]; then
        log "SKIP (NAS mount skipped for dry run): $src_expanded"
        return
      fi
      ;;
    Local|local) log "SKIP (keeping local): $src_expanded"; return ;;
    *) log "SKIP (bad target): $src_expanded -> $target"; return ;;
  esac

  local folder_name="$(basename "$src_expanded")"
  local dest="${dest_root}/${subpath:-$folder_name}"
  mkdir -p "$dest" || fail "Cannot create $dest"

  log "Processing: $src_expanded  ->  $dest  (mode=$mode)"
  move_with_rsync "$src_expanded" "$dest" "$mode"

  # Create symlink at original location to destination
  if [[ $dry_run -eq 1 ]]; then
    vlog "DRY RUN: would ln -sfn \"$dest\" \"$src_expanded\""
  else
    # If src_expanded still exists but empty, remove before linking
    if [[ -d "$src_expanded" && -z "$(ls -A "$src_expanded" 2>/dev/null)" ]]; then
      rmdir "$src_expanded" 2>/dev/null
    fi
    ln -sfn "$dest" "$src_expanded" || fail "Failed to link $src_expanded -> $dest"
  fi
}

# Validate rules file first
validate_rules() {
  local -A seen_paths
  local line_num=0
  while IFS='|' read -r raw_src raw_target raw_subpath raw_mode; do
    ((line_num++))
    # Trim whitespace
    local src="$(echo "$raw_src" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    local target="$(echo "$raw_target" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    # Skip comments/blank
    [[ -z "$src" ]] && continue
    [[ "$src" = \#* ]] && continue

    # Expand path for validation
    local src_expanded="$src"
    src_expanded="${src_expanded/#\~/$HOME}"
    src_expanded="${src_expanded//\$HOME/$HOME}"

    # Check for duplicate paths
    if [[ -n "${seen_paths[$src_expanded]}" ]]; then
      fail "Duplicate source path at line $line_num: $src_expanded (also at line ${seen_paths[$src_expanded]})"
    fi
    seen_paths[$src_expanded]=$line_num

    # Validate target
    case "$target" in
      SSD|ssd|NAS|nas|Local|local) ;;
      *) log "WARN: Invalid target '$target' at line $line_num: $src" ;;
    esac
  done < "$rules_file"
  vlog "Rules validation completed"
}

vlog "Validating rules file..."
validate_rules

# Read rules file
while IFS='|' read -r raw_src raw_target raw_subpath raw_mode; do
  # Trim whitespace
  src="$(echo "$raw_src" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  target="$(echo "$raw_target" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  subpath="$(echo "$raw_subpath" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  mode="$(echo "$raw_mode" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  # Skip comments/blank
  [[ -z "$src" ]] && continue
  [[ "$src" = \#* ]] && continue
  process_rule "$src" "$target" "$subpath" "$mode"
done < "$rules_file"

log "Done."
