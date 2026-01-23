#!/usr/bin/env bash
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
echo "Installing font..."
oh-my-posh font install FantasqueSansMono

CUSTOM_RC_FILE_PATH="$SCRIPT_DIR/bash/bashrc_kostam.sh"
SOURCE_LINE="source \"$CUSTOM_RC_FILE_PATH\""
if grep -qF "$SOURCE_LINE" "$HOME/.profile"
then
	echo "Custom profile already added to user's profile"
else
	{
		echo ""
		echo "$SOURCE_LINE"
	} >> "$HOME/.profile"
fi

if command -v pwsh &> /dev/null
then
	pwsh "$SCRIPT_DIR/Setup.ps1"
fi
