#!/bin/sh
run() {
    echo "$@"
    $@
}

run pycodestyle --max-line-length=120 mut
run mypy --ignore-missing-imports mut/
