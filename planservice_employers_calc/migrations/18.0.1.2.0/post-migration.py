# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def _fill_baseline_periods(cr):
    """Linha de base antiga, sem período, fica com o mês inteiro.

    Assim o previsto já travado continua distribuído como antes (pelos dias
    úteis do mês todo): a linha de base não muda de valor nem de distribuição.
    """
    cr.execute(
        """
        UPDATE planservice_employer_planned_cost
        SET date_start = date,
            date_end = (date + INTERVAL '1 month' - INTERVAL '1 day')::date
        WHERE date_start IS NULL OR date_end IS NULL
        """
    )


def migrate(cr, version):
    if not version:
        return
    _fill_baseline_periods(cr)
