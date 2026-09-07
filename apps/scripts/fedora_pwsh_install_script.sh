#!/usr/bin/env bash

# pwsh is not in Fedora repos; register the Microsoft RHEL repo. Writing the .repo
# file directly avoids the dnf4/dnf5 config-manager syntax split.
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
curl -sSL https://packages.microsoft.com/config/rhel/9.0/prod.repo | sudo tee /etc/yum.repos.d/microsoft-prod.repo > /dev/null
sudo dnf install -y powershell
