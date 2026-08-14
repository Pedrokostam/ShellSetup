docker run --rm -it -v "$(pwd):/test" -w /test ubuntu_test /bin/bash -c  "./setup.sh; exec bash"
