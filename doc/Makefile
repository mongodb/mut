.PHONY: build stage fake-deploy

build:
	mut-build --use-builder=sphinx

stage:
	mut-publish build/output/html docs-mongodb-org-staging --all-subdirectories --prefix=mut --stage ${ARGS}

fake-deploy:
	mut-publish build/output/html docs-mongodb-org-staging --all-subdirectories --prefix=mut --deploy ${ARGS}
