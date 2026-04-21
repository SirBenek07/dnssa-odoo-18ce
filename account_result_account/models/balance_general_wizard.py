from odoo import fields, models


class BalanceGeneralWizard(models.TransientModel):
    _inherit = "balance.general.wizard"

    show_result_accounts = fields.Boolean(
        string="Mostrar cuentas de Resultado",
        default=False,
    )
