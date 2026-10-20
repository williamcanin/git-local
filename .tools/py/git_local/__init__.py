"""Install and manage a self-hosted Git server (Forgejo or Gitea) on Arch Linux.

Run with: PYTHONPATH=.tools/py python3 -m git_local <command>

Standard library only. Modules, from the base up:
    paths      constants and the data-root layout
    util       output, command execution, backups
    text       pure text helpers (fstab, hosts, backups, units)
    state      the state of one run and the recorded data root
    config     Forgejo/Gitea config.ini (template, ROOT_URL, setup-safe rewrite)
    sshclient  the 'local' host in ~/.ssh/config, legacy Gitea key
    network    LAN address (fixed or DHCP), mDNS, firewall reminder
    system     host checks, /etc files, nginx, linger, avahi
    units      systemd user units and the dump script
    install    make install, step by step
    uninstall  make uninstall, status and check-ssh
    cli        command dispatch
"""
