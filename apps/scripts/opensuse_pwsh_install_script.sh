#!/usr/bin/env bash
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
sudo zypper --non-interactive addrepo --refresh "https://packages.microsoft.com/config/opensuse/15/prod.repo" microsoft
sudo zypper --non-interactive --gpg-auto-import-keys install powershell
