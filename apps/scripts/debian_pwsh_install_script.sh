#!/usr/bin/env bash
###################################

set -euo pipefail

# Prerequisites

# Update the list of packages
sudo apt-get update

# Install pre-requisite packages.
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y apt-utils wget apt-transport-https software-properties-common

# Get the version of Ubuntu
source /etc/os-release

# Download the Microsoft repository keys
directory=$(mktemp -d)
trap 'rm -rf "$directory"' EXIT
deb_file="$directory/packages-microsoft-prod.deb"
wget -q -O "$deb_file" "https://packages.microsoft.com/config/$ID/$VERSION_ID/packages-microsoft-prod.deb"

# Register the Microsoft repository keys
sudo dpkg -i "$deb_file"

# Delete the Microsoft repository keys file
rm $directory/packages-microsoft-prod.deb

# Update the list of packages after we added packages.microsoft.com
sudo apt-get update

###################################
# Install PowerShell
sudo apt-get install -y powershell
