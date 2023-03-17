PLATFORM=$(shell printf '%s_%s' "$$(uname -s | tr '[:upper:]' '[:lower:]')" "$$(uname -m)")
VERSION=$(shell git describe --tags)

PACKAGE_NAME=mut-${VERSION}-${PLATFORM}.zip

.PHONY: help build-dist package clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo 'Variables'
	@printf "  \033[36m%-18s\033[0m %s\n" 'ARGS' 'Arguments to pass to mut-publish'

build-dist:
	-rm -rf mut.dist dist
	mkdir dist
	echo 'from mut import stage; stage.main()' > mut-publish.py
	echo 'from mut.redirects import redirect_main; redirect_main.main()' > mut-redirects.py
	echo 'from mut.index import main; main.main()' > mut-index.py

	poetry run python3 -m PyInstaller mut.spec
	install -m644 LICENSE* dist/mut/

dist/${PACKAGE_NAME}: build-dist ## Build a binary tarball
	# Normalize the mtime, and zip in sorted order
	cd dist && find mut -print | sort | zip -X ../$@ -@
	# Ensure that the generated binary runs
	./dist/mut/mut-publish --help >/dev/null
	./dist/mut/mut-redirects --help >/dev/null
	./dist/mut/mut-index --help >/dev/null
	if [ -n "${GITHUB_OUTPUT}" ]; then echo "package_filename=${PACKAGE_NAME}" >> "${GITHUB_OUTPUT}"; fi


package: dist/${PACKAGE_NAME}

wheel:
	poetry build
	if [ -n "${GITHUB_OUTPUT}" ]; then echo "wheel_filename=mut-${VERSION}-py3-none-any.whl" >> "${GITHUB_OUTPUT}"; fi

clean:
	-rm -r dist mut-index.py mut-redirects.py mut-publish.py
