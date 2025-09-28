    #!/bin/zsh
    # mount-nas.sh
    : ${NAS_URL:="smb://????"}
    : ${NAS_ROOT:="/Volumes/Music"}
    mkdir -p "$NAS_ROOT"
    /usr/bin/osascript <<-APPLESCRIPT
      try
        mount volume "${NAS_URL}"
      on error errMsg number errNum
        do shell script "exit 1"
      end try
APPLESCRIPT
