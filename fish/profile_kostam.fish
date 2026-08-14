set SCRIPT_DIR (dirname (realpath (status --current-filename)))
set CONFIG_FILE "$SCRIPT_DIR/../oh-my-posh/kostamfive.omp.json"
if command -vq oh-my-posh
   oh-my-posh init fish --config "$CONFIG_FILE" | source
end
if command -vq zoxide
   zoxide init fish | source
end
