#!/usr/bin/env bash

FORCE=false
for arg in "$@"; do
    if [ "$arg" == "-f" ]; then
        FORCE=true
        break
    fi
done

if [ "$(id -u)" -eq 0 ]; then
    if [ "$FORCE" = true ]; then
        echo "Warning: Running as root, but -f was specified. Proceeding..."
    else
        echo "Error: This script cannot be run as root. Use -f to override."
        exit 1
    fi
fi

add_to_path() {
   local DIR=$1
   if echo "$PATH" | grep -qE "(^|:)${DIR}(:|$)"; then
       echo "$DIR is already in PATH"
   else
       echo "" > "$HOME/.profile"
       echo "export PATH=\"\$PATH:$DIR" >> "$HOME/.profile"
       export PATH="$PATH:$DIR"
       echo "Added $DIR to PATH"
   fi
}

add_to_file() {
    local SOURCE_LINE="$1"
    local FILE_PATH="$2"

    if [[ -z "$SOURCE_LINE" ]]; then
        echo "Error: SOURCE_LINE is missing" >&2
        return 1
    fi

    if grep -qF "$SOURCE_LINE" "$FILE_PATH" 2>/dev/null; then
        echo "$SOURCE_LINE already added to $FILE_PATHG"
    else
        {
            echo ""
            echo "$SOURCE_LINE"
        } >> "$FILE_PATH"
    fi
}

add_to_path "$HOME/.local/bin"

# folder containing this script file
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

if ! command -v git &> /dev/null
then
	echo "Git is not installed! Aliases will no be added"
else
	GIT_CONFIG_PATH="$SCRIPT_DIR/git/myconfig.gitconfig"
	echo "Including file '$GIT_CONFIG_PATH' in the global git configuration... "
	git config --global include.path "$GIT_CONFIG_PATH"
fi


if command -v oh-my-posh &> /dev/null
then
	oh-my-posh upgrade
else
	echo "Installing oh-my-posh"
	curl -sk https://ohmyposh.dev/install.sh | bash -s
fi

CUSTOM_RC_FILE_PATH="$SCRIPT_DIR/bash/bashrc_kostam.sh"
SOURCE_LINE="source \"$CUSTOM_RC_FILE_PATH\""
add_to_file "$SOURCE_LINE" "$HOME/.bashrc"

CUSTOM_RC_FILE_PATH="$SCRIPT_DIR/bash/profile_kostam.sh"
SOURCE_LINE="source \"$CUSTOM_RC_FILE_PATH\""
add_to_file "$SOURCE_LINE" "$HOME/.profile"

if ! command -v pwsh &> /dev/null
then 
   if command -v yay &> /dev/null
   then
      PKG_MGR="yay"
      INSTALL_CMD="yay -Sy --noconfirm powershell-bin"
   elif command -v apt &> /dev/null
   then
      PKG_MGR="apt"
      INSTALL_CMD="sudo $SCRIPT_DIR/bash/ubuntu_pwsh_install_script.sh"
   fi

   if [[ -n "$PKG_MGR" ]]
   then
      read -p "Install PowerShell using $PKG_MGR? (y/n): " confirm
      if [[ $confirm == [yY] ]]; then
         eval "$INSTALL_CMD"
      fi
   fi
fi

echo "Basic installation for linux shell completed. The rest requires Pwsh."

if command -v pwsh &> /dev/null
then
	pwsh -noprofile "$SCRIPT_DIR/Setup.ps1"
fi
