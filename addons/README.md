# Bundled Odoo Addons

Third-party Odoo modules vendored for self-contained installs.

| Module | Version | Source | License |
|---|---|---|---|
| `queue_job` | 18.0 (OCA) | https://github.com/OCA/queue/tree/18.0/queue_job | LGPL-3 |

## Updating queue_job

```bash
rm -rf addons/queue_job
git clone --depth 1 --branch 18.0 --single-branch \
  https://github.com/OCA/queue.git /tmp/oca-queue
cp -r /tmp/oca-queue/queue_job addons/queue_job
rm -rf /tmp/oca-queue
```

Retain OCA copyright headers and README in the vendored tree.
