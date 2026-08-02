SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
CONFIG_FILE="$SCRIPT_DIR/../oh-my-posh/kostamfive.omp.json"
eval "$(oh-my-posh init bash --config "$CONFIG_FILE")"
eval "$(zoxide init bash)"
