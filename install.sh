#!/usr/bin/env bash
set -e

MUT_PATH=~/.local/mut

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
    echo "Depends on: python 3.5+, git, libxml2, libyaml"

    if ! command -v git > /dev/null ; then
        echo "Could not find git; please install it"
        exit 1
    fi

    if ! command -v inkscape > /dev/null ; then
        echo "Could not find inkscape; you will not be able to run mut-images"
    fi

    if ! command -v pngcrush > /dev/null ; then
        echo "Could not find pngcrush; you will not be able to run mut-images"
    fi

    if ! command -v svgo > /dev/null ; then
        echo "Could not find svgo; you will not be able to run mut-images"
    fi
}

dependencies_debian() {
    prompt 'Install dependencies' "sudo apt-get update && sudo apt-get install libyaml-dev python3 python3-pip python3-venv git pkg-config libxml2-dev"
}

dependencies_osx() {
    INSTALL_PYTHON=''
    if ! command -v python3 > /dev/null; then
        INSTALL_PYTHON='python'
    fi

    set +e
    prompt 'Setup Xcode command line tools' "sudo xcode-select --install; sudo xcode-select -r"
    set -e

    prompt 'Install dependencies' "brew update && brew install libyaml libxml2 pkgconfig ${INSTALL_PYTHON}"
}

create_venv() {
    mkdir -p "${MUT_PATH}/bin"
    rm -rf "${MUT_PATH}/venv"
    python3 -m venv "${MUT_PATH}/venv"
    . "${MUT_PATH}/venv/bin/activate"

    python3 -m pip install -qqq --upgrade pip || true

    (   cd "${MUT_PATH}"
        rm -rf dev
        mkdir dev
        cd dev

        git clone --depth=1 https://github.com/mongodb/mut.git

        ( cd mut && python3 -m pip install -r requirements.txt . )
    )

    install_helper mut
    install_helper mut-convert-redirects
    install_helper mut-images
    install_helper mut-index
    install_helper mut-intersphinx
    install_helper mut-publish
    install_helper mut-redirects

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

        if [ -n "${rc_files[0]}" ] && ask 'Add PATH environment variable?'; then
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
    echo "  mut-convert-redirects"
    echo "  mut-images"
    echo "  mut-index"
    echo "  mut-intersphinx"
    echo "  mut-publish"
    echo "  mut-redirects"
}

case "$(uname -s)" in
Darwin)
  dependencies_osx
  # Starting in Mojave, XCode starts bundling libxml2 in a way that breaks
  # builds. Workaround.
  export CPPFLAGS="-I/usr/local/opt/libxml2/include/libxml2"
  ;;
Linux)
  if [ -x /usr/bin/apt-get ]; then
    dependencies_debian
  else
    dependencies_unknown
  fi
  ;;
*)
  dependencies_unknown
  ;;
esac

create_venv
