set SCRIPT_DIR (dirname (realpath (status --current-filename)))
set CONFIG_FILE "$SCRIPT_DIR/../oh-my-posh/kostamfive.omp.json"
oh-my-posh init fish --config "$CONFIG_FILE" | source
zoxide init fish | source
