#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
if ! command -v git &> /dev/null
then
	echo "Git is not installed!!!"
else
	GIT_CONFIG_PATH="$SCRIPT_DIR/git/myconfig.gitconfig"
	echo "Including file '$GIT_CONFIG_PATH' in the global git configuration... "
	git config --global include.path "$GIT_CONFIG_PATH"
fi


if ! command -v oh-my-posh &> /dev/null
then
	echo "Installing oh-my-posh"
	curl -s https://ohmyposh.dev/install.sh | bash -s
else
	oh-my-posh upgrade
fi
echo "Installing font..."
oh-my-posh font install FantasqueSansMono

CUSTOM_RC_FILE_PATH="$SCRIPT_DIR/bash/bashrc_kostam.sh"
SOURCE_LINE="source \"$CUSTOM_RC_FILE_PATH\""
if grep -qF "$SOURCE_LINE" "$HOME/.bashrc"
then
	echo "Custom profile already added to user's profile"
else
	{
		echo ""
		echo "$SOURCE_LINE"
	} >> "$HOME/.bashrc"
fi
