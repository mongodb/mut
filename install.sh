#!/usr/bin/env bash
set -e

MUT_PATH=~/.local/mut

_try_venv() {
    local name=$1
    if which "${name}" > /dev/null; then
        shift 1
        "${name}" "$@"
        return $!
    fi

    return 1
}

# Automatically choose an available pyvenv program
# venv(path)
venv() {
    if _try_venv pyvenv "$@"; then return; fi
    if _try_venv pyvenv-3.5 "$@"; then return; fi
    pyvenv-3.4 "$@"
}

# Ask the user for permission to do something
# ask(description)
ask() {
    local ok
    while true
    do
        read -rp "$1 (y/n) " ok

        case "${ok}" in
        y | yes)
          return 0
          ;;
        '')
            continue
            ;;
        *)
          return 1
          ;;
        esac
    done
}

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
    echo "Depends on: python 3.3+, pip3, git"

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

    if ! which inkscape > /dev/null ; then
        echo "Could not find inkscape; you will not be able to run mut-images"
    fi

    if ! which pngcrush > /dev/null ; then
        echo "Could not find pngcrush; you will not be able to run mut-images"
    fi

    if ! which scour > /dev/null ; then
        echo "Could not find scour; you will not be able to run mut-images"
    fi
}

dependencies_openbsd() {
    prompt 'Install dependencies' doas pkg_add libyaml py3-pip git
}

dependencies_debian() {
    prompt 'Install dependencies' sudo apt-get update && sudo apt-get install libyaml-dev python3 python3-pip python3-venv git
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
    venv "${MUT_PATH}/venv"
    . "${MUT_PATH}/venv/bin/activate"

    pip3 install --upgrade pip

    (   cd "${MUT_PATH}"
        rm -rf dev
        mkdir dev
        cd dev

        git clone https://github.com/cyborginstitute/rstcloth.git
        git clone --depth=1 https://github.com/i80and/mut.git
        git clone https://github.com/i80and/docs-tools.git
        git clone --depth=1 https://github.com/i80and/libgiza.git

        ( cd rstcloth && git checkout 2334986073f884d7dd51a8a52d381cf05859bb46 && pip install . )
        ( cd libgiza && pip install . )
        ( cd docs-tools/giza && git checkout giza3 && pip install . )
        ( cd mut && pip install -r requirements.txt . )
    )

    install_helper mut-build
    install_helper mut-images
    install_helper mut-intersphinx
    install_helper mut-lint
    install_helper mut-publish
    install_helper mut

    if ! echo "${PATH}" | grep -q "${MUT_PATH}/bin"; then
        local rc_files=()
        if [ -r ~/.bash_profile ]; then
            rc_files+=(~/.bash_profile)
        elif [ -r ~/.bashrc ]; then
            rc_files+=(~/.bashrc)
        fi

        if [ -r ~/.zshenv ]; then
            rc_files+=(~/.zshenv)
        elif [ -r ~/.zshrc ]; then
            rc_files+=(~/.zshrc)
        fi

        if [ ! -z "${rc_files[0]}" ] && ask 'Add PATH environment variable?'; then
            for rc in "${rc_files[@]}"; do
                printf "\nPATH=\$PATH:%s/bin\n" "${MUT_PATH}" >> "${rc}"
            done

            echo 'Open a new terminal to use the changes'
        else
            echo ''
            echo "Add \"export PATH=\$PATH:${MUT_PATH}/bin\" to your PATH environment variable"
        fi
    fi

    echo "Installed:"
    echo "  mut"
    echo "  mut-build"
    echo "  mut-images"
    echo "  mut-intersphinx"
    echo "  mut-lint"
    echo "  mut-publish"
}

case "$(uname -s)" in
Darwin)
  dependencies_osx
  ;;
Linux)
  if [ -x /usr/bin/apt-get ]; then
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
