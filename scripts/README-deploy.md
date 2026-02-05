Quick deployment files for powering /prod/autotech_ai on poweredge2

Files in this folder:
- open-webui-local.service.template - systemd unit template (edit User= and optionally ExecStart)
- deploy-open-webui-local.sh - build + install + create env file + create unit + migrate + enable/start
- switch-open-webui.sh - toggle between pip-installed and local repo services
- deploy-poweredge2.sh - run from your dev machine to rsync into /prod/autotech_ai and restart the service
- build-repo-on-server.sh - run on the server to rebuild frontend + python deps without touching systemd

Typical usage (on poweredge2):
1. Copy scripts to server or run them from the repo as the repo owner.
2. Make deploy script executable:
   chmod +x scripts/deploy-open-webui-local.sh
3. Run deploy (you will be prompted for sudo during the script):
   sudo --tt ./scripts/deploy-open-webui-local.sh
4. After deploy, switch between versions:
   sudo --tt ./scripts/switch-open-webui.sh local  # to run repo build
   sudo --tt ./scripts/switch-open-webui.sh pip    # to revert to pip-installed

Notes & hints:
- The scripts assume the conda env name is "open-webui" (you can change CONDA_ENV_NAME in the script to your env name).
- The systemd unit uses the python binary from the conda env if detected, otherwise it falls back to running via `conda run` at ExecStart.
- Ensure FRONTEND_BUILD_DIR is set to /prod/autotech_ai/build in /etc/default/open-webui-local (the deploy script writes this file for you).
- After switching services, you might need to restart cloudflared if you're using a tunnel:
  sudo systemctl restart cloudflared

Test deploy notes:
- By default `deploy-open-webui-test.sh` copies the production sqlite DB to `/prod/autotech_ai/backend/data/db-test.sqlite3` so you can test safely without touching production.
- If you want the test instance to use the *production* DB directly (NOT recommended unless you know what you're doing), pass `--use-prod-db`. The script will ask you to type `YES` to confirm (use `--force` to skip interactive confirmation).
  - By default, when using `--use-prod-db` the script will NOT run database migrations. If you want to allow migrations against the production DB, pass `--allow-migrations` (only do this if you have a fresh backup).
- For Postgres or other non-sqlite DBs, create a test database manually (pg_dump / pg_restore) and pass its path via `--test-db`.

Remote rsync deploy (from your dev machine):
1. Ensure you can ssh to poweredge2 (keys recommended):
   ssh YOUR_USER@poweredge2
2. From the repo root on your dev machine, run:
   ./scripts/deploy-poweredge2.sh --user YOUR_USER --wipe-data

Notes:
- `--wipe-data` will delete `/prod/autotech_ai/backend/data/*` on the server before redeploying.
- The deploy script defaults `--service auto` and will try `autotech_ai`, then `open-webui-local`, then `open-webui`.
- You can always override with `--service YOUR_SERVICE_NAME`.
- By default the deploy script runs `./scripts/build-repo-on-server.sh` on the server after rsync (safe: does not modify systemd units).
- If you want the older behavior that (re)creates a systemd unit, pass: `--remote-deploy ./scripts/deploy-open-webui-local.sh`
