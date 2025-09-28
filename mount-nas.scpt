-- mount-nas.scpt
-- Uses Keychain-stored SMB creds (connect once in Finder and save password)
set nasURL to "smb://???"
tell application "Finder"
    try
        mount volume nasURL
    on error errMsg number errNum
        display dialog "Failed to mount: " & errMsg
    end try
end tell
