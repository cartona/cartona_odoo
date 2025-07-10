# Odoo Queue Job Setup for Cartona Integration

This guide explains how to install/update the `queue_job` module and run the queue worker for both development and production environments.

---

## 1. Install/Update the `queue_job` Module

Run this command to ensure the `queue_job` module is installed and up-to-date:

```bash
odoo -d yourdbname -u queue_job --stop-after-init
```
- Replace `yourdbname` with your actual Odoo database name.
- Add `--addons-path=addons,custom_addons` if your addons are not in the default path.

---

## 2. Start the Queue Worker

### Development Environment

Run Odoo with the queue job module loaded (single process, suitable for development):

```bash
odoo --addons-path=addons,custom_addons --db-filter=yourdbname --load=web,queue_job
```
- Replace `addons,custom_addons` with your actual addons paths.
- Replace `yourdbname` with your database name.

### Production Environment (Recommended)

Run a dedicated queue job worker (separate from your main Odoo web workers):

```bash
odoo --addons-path=addons,custom_addons --db-filter=yourdbname --load=queue_job --workers=0 --max-cron-threads=0 --without-demo=all --log-level=info --logfile=queue_job.log --queue-job
```
- This starts a process that only processes queue jobs.
- You can run this as a background service (e.g., with systemd or supervisor).

---

## 3. Start the Main Odoo Server (Production)

Your main Odoo server (for web and normal operations) should be started as usual, e.g.:

```bash
odoo --addons-path=addons,custom_addons --db-filter=yourdbname --workers=4 --max-cron-threads=2
```
- Adjust `--workers` and `--max-cron-threads` as needed for your server.

---

## 4. Access the Queue Job UI

After running the above, you should see **Queue Jobs** under **Settings > Technical** in Odoo.

---

## 5. Troubleshooting

- If you do not see "Queue Jobs", ensure you have enabled Developer Mode and that the `queue_job` module is installed.
- Check your Odoo logs (e.g., `queue_job.log`) for errors if jobs are not being processed.

---

**If you need Docker, systemd, or other environment-specific instructions, let your admin or developer know!** 