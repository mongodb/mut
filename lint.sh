#!/bin/sh
run() {
    echo "$@"
    $@
}

run pep8 --max-line-length=120 mut
run mypy -s --package mut
