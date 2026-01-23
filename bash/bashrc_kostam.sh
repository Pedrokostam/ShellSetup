SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
CONFIG_FILE="$SCRIPT_DIR/../oh-my-posh/kostamfive.omp.json"
eval "$(oh-my-posh init bash --config "$CONFIG_FILE")"
eval "#(zoxide init bash)"
