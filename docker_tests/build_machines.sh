#!/usr/bin/env bash

set -euo pipefail

for dockerfile in */dockerfile; do
    [ -f "$dockerfile" ] || continue

    dir=$(dirname "$dockerfile")
    name=$(basename "$dir")

    echo "Building $name from $dockerfile..."
    docker build -t "$name" "$dir"
done
