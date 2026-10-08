# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def migrate(cr, version):
    """Seed the numeric revision from the free-text one before it is computed."""
    cr.execute(
        "ALTER TABLE mgmtsystem_nonconformity "
        "ADD COLUMN IF NOT EXISTS revision_number integer"
    )
    cr.execute(
        """
        UPDATE mgmtsystem_nonconformity
           SET revision_number = CASE
                   WHEN revision ~ '^[0-9]+$' THEN revision::integer
                   ELSE 0
               END
         WHERE revision_number IS NULL
        """
    )
