#!/usr/bin/env bash
set -e

MUT_PATH=~/.local/mut

# Ask the user for permission before running a command
# prompt(description, args...)
prompt() {
    printf "%s:  " "$1"
    shift 1
    echo "$@"
    read -rp 'OK? ' _

    /bin/sh -c "$*"
}

# Install a program wrapper
# install_helper(name)
install_helper() {
    if [ -z "$1" ]; then
        echo "No helper given to install_helper"
        exit 1
    fi

    printf '#!/bin/sh\n' > "${MUT_PATH}/bin/$1"
    printf '. %s/venv/bin/activate\n' "${MUT_PATH}" >> "${MUT_PATH}/bin/$1"
    printf '%s/venv/bin/%s $@\n' "${MUT_PATH}" "$1" >> "${MUT_PATH}/bin/$1"
    chmod 755 "${MUT_PATH}/bin/$1"
}

dependencies_unknown() {
    echo "Unable to setup dependencies automatically on this system"

    if ! which pyvenv > /dev/null ; then
        echo "Could not find pyvenv; please install Python 3.3 or later"
        exit 1
    fi

    if ! which pip3 > /dev/null ; then
        echo "Could not find pip3; please install it"
        exit 1
    fi

    if ! which git > /dev/null ; then
        echo "Could not find git; please install it"
        exit 1
    fi
}

dependencies_openbsd() {
    prompt 'Install dependencies' doas pkg_add libyaml py3-pip git
}

dependencies_debian() {
    prompt 'Install dependencies' sudo apt-get update && sudo apt-get install libyaml-dev python3 python3-pip git
}

dependencies_osx() {
    INSTALL_PYTHON=''
    if ! which python3 > /dev/null; then
        INSTALL_PYTHON='python3'
    fi

    prompt 'Setup Xcode command line tools' sudo xcode-select -r
    prompt 'Install dependencies' "brew update && brew install libyaml ${INSTALL_PYTHON}"

    if ! which pip3 > /dev/null; then
        prompt 'Install pip' sudo python3 -m ensurepip
    fi
}

create_venv() {
    mkdir -p "${MUT_PATH}/bin"
    rm -rf "${MUT_PATH}/venv"
    pyvenv "${MUT_PATH}/venv"
    . "${MUT_PATH}/venv/bin/activate"

    pip3 install --upgrade pip

    (   cd "${MUT_PATH}"
        rm -rf dev
        mkdir dev
        cd dev

        git clone https://github.com/cyborginstitute/rstcloth.git
        git clone https://github.com/i80and/mut.git

        ( cd rstcloth && git checkout 2334986073f884d7dd51a8a52d381cf05859bb46 && pip install . )
        ( cd mut && pip install -r requirements.txt . )
    )

    # We do NOT want to call our built-in version of sphinx; giza is
    # incompatible with Py3
    rm -f "${MUT_PATH}/venv/bin/sphinx-build"

    install_helper mut-build
    install_helper mut-publish
    install_helper mut-lint

    if ! echo "${PATH}" | grep -q "${MUT_PATH}/bin"; then
        echo ''
        echo "Add ${MUT_PATH}/bin to your PATH environment variable"
    fi
}

case "$(uname -s)" in
Darwin)
  dependencies_osx
  ;;
Linux)
  if [ ! -x /usr/bin/apt-get ]; then
    dependencies_debian
  else
    dependencies_unknown
  fi
  ;;
OpenBSD)
  dependencies_openbsd
  ;;
*)
  dependencies_unknown
  ;;
esac

create_venv
