docker run --rm -it -v "$(pwd):/test" -w /test script_windows /bin/bash -c  "./setup.sh; stty echo; exec bash"
