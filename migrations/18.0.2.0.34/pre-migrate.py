import logging

_logger = logging.getLogger(__name__)


def _delete_module_views(cr, module):
    cr.execute(
        """
        SELECT d.id, d.res_id
        FROM ir_model_data d
        JOIN ir_ui_view v ON v.id = d.res_id
        WHERE d.module = %s
          AND d.model = 'ir.ui.view'
        """,
        (module,),
    )
    rows = cr.fetchall()
    if not rows:
        return 0
    cr.execute(
        "DELETE FROM ir_model_data WHERE id = ANY(%s)",
        ([row[0] for row in rows],),
    )
    cr.execute(
        "DELETE FROM ir_ui_view WHERE id = ANY(%s)",
        ([row[1] for row in rows],),
    )
    return len(rows)


def migrate(cr, version):
    removed = _delete_module_views(cr, 'cartona_odoo')
    _logger.info(
        'Cartona 18.0.2.0.34 view cleanup: removed %s cartona_odoo views for reload',
        removed,
    )
