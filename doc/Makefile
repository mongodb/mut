GIT_BRANCH=`git rev-parse --abbrev-ref HEAD`

.PHONY: build stage fake-deploy

build:
	mut-build

stage:
	mut-publish build/$(GIT_BRANCH)/html docs-mongodb-org-staging --all-subdirectories --prefix=mut --stage ${ARGS}

fake-deploy:
	mut-publish build/$(GIT_BRANCH)/html docs-mongodb-org-staging --all-subdirectories --prefix=mut --deploy ${ARGS}
