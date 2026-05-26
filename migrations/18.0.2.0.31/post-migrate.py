import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        UPDATE cartona_config
        SET company_id = (
            SELECT id FROM res_company
            ORDER BY id
            LIMIT 1
        )
        WHERE company_id IS NULL
    """)
    _logger.info('Cartona multi-company migration: backfilled company_id on cartona.config')
