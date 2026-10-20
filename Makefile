.DEFAULT_GOAL := help
.PHONY: help install uninstall status dump

MAIN := ./.tools/main.sh

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install and configure Gitea or Forgejo
	@$(MAIN) install

uninstall: ## Remove the Git Local service and dump timer (keeps packages and data)
	@$(MAIN) uninstall

status: ## Show service, dump timer and nginx status
	@$(MAIN) status

dump: ## Create a dump now (stops the server while it runs)
	@$(MAIN) dump
