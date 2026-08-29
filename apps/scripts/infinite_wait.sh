#!/usr/bin/env bash

while true; do
    sleep 0.25
    printf "OutputOutputOutputOutputOutputOutputOutputOutputOutputOutputOutputOutputOutputOutputOutputOutput"
    sleep 0.25
    printf "ErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorErrorError" >&2
done
