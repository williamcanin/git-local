.DEFAULT_GOAL := help
.PHONY: help install uninstall status check-ssh dump

MAIN := PYTHONPATH=.tools/py python3 -m git_local

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Install and configure Gitea or Forgejo
	@$(MAIN) install

uninstall: ## Remove services, timer, nginx files and dump script (keeps data)
	@$(MAIN) uninstall

status: ## Show service, dump timer and nginx status
	@$(MAIN) status

dump: ## Create a dump now (stops the server while it runs)
	@$(MAIN) dump

check-ssh: ## Check that ~/.ssh/config has the local host alias with port 2222
	@$(MAIN) check-ssh
