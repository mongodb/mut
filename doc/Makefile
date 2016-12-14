GIT_BRANCH=`git rev-parse --abbrev-ref HEAD`

.PHONY: help html stage

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo 'Variables'
	@printf "  \033[36m%-18s\033[0m %s\n" 'ARGS' 'Arguments to pass to mut-publish'

html: ## Builds this branch's HTML under build/<branch>/html
	mut-build

stage: ## Host online for review
	mut-publish build/$(GIT_BRANCH)/html docs-mongodb-org-staging --all-subdirectories --prefix=mut --stage ${ARGS}
