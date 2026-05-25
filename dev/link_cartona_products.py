#!/usr/bin/env python3
"""Link Cartona ProductSupplier.internal_product_id to Odoo variant IDs via supplier-integrations API."""
import json
import sys
import time
from pathlib import Path

import requests

MAPPING_FILE = Path(__file__).with_name('cartona_odoo_mapping.json')
API_BASE = 'https://supplier-integrations.cartona.space/api/v1'
AUTH_TOKEN = sys.argv[1] if len(sys.argv) > 1 else None

if not AUTH_TOKEN:
    print('Usage: link_cartona_products.py <auth_token>', file=sys.stderr)
    sys.exit(1)

HEADERS = {
    'Authorization': AUTH_TOKEN,
    'Content-Type': 'application/json',
}


def api_get(params):
    r = requests.get(f'{API_BASE}/supplier-product', headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def api_bulk_update(payload):
    r = requests.post(f'{API_BASE}/supplier-product/bulk-update', headers=HEADERS, json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f'bulk-update failed ({r.status_code}): {r.text[:500]}')
    return r.json()


def move_conflicts(variant_id, target_ps_id):
    owners = api_get({'internal_product_id': str(variant_id)})
    for owner in owners:
        owner_id = owner['id']
        if owner_id == target_ps_id:
            continue
        api_bulk_update([{
            'supplier_product_id': owner_id,
            'internal_product_id': f'conflict-{owner_id}',
        }])
        print(f'  moved conflict ps {owner_id} away from {variant_id}')


def assign(target_ps_id, variant_id):
    api_bulk_update([{
        'supplier_product_id': int(target_ps_id),
        'internal_product_id': str(variant_id),
    }])


def verify(target_ps_id, variant_id):
    rows = api_get({'supplier_product_id': int(target_ps_id)})
    if not rows:
        return False, 'not found'
    actual = rows[0].get('internal_product_id')
    return actual == str(variant_id), actual


def main():
    mapping = json.loads(MAPPING_FILE.read_text())
    ok = fail = 0
    results = []

    for row in mapping:
        ps_id = int(row['ps_id'])
        variant_id = int(row['variant_id'])
        name = row['name']
        print(f'Linking ps {ps_id} -> {variant_id} ({name[:40]})')
        try:
            move_conflicts(variant_id, ps_id)
            assign(ps_id, variant_id)
            good, actual = verify(ps_id, variant_id)
            if good:
                ok += 1
                print(f'  OK')
            else:
                fail += 1
                print(f'  FAIL verify: got {actual!r}')
            results.append({'ps_id': ps_id, 'variant_id': variant_id, 'ok': good, 'actual': actual})
        except Exception as exc:
            fail += 1
            print(f'  ERROR: {exc}')
            results.append({'ps_id': ps_id, 'variant_id': variant_id, 'ok': False, 'error': str(exc)})
        time.sleep(0.15)

    out = {'ok': ok, 'fail': fail, 'results': results}
    out_path = Path(__file__).with_name('cartona_link_results.json')
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f'\nDone: {ok} ok, {fail} fail -> {out_path}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
