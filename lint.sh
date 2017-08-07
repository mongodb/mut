#!/bin/sh
run() {
    echo "$@"
    $@
}

export MYPYPATH=`pwd`/stubs
run pep8 --max-line-length=120 mut
run mypy --ignore-missing-imports --package mut 2>&1 | grep -v tuft
