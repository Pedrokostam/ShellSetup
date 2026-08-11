#!/usr/bin/env bash

tmp=$(mktemp -d)
sudo pacman -S --needed git base-devel "$temp/yay"
git clone https://aur.archlinux.org/yay.git
pushd "$temp/yay"
makepkg -si
popd
rm -rf "$tmp"
