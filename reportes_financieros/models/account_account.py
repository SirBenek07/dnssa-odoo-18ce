from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    include_in_cash_flow = fields.Boolean(
        string="Incluir movimientos en flujo de caja",
        default=False,
        help="Si esta activo, los movimientos de esta cuenta podran clasificarse explicitamente en el reporte de flujo de caja.",
    )
    cash_flow_credit_behavior = fields.Selection(
        selection=[("income", "Ingreso"), ("expense", "Gasto")],
        string="Credito es",
    )
    cash_flow_debit_behavior = fields.Selection(
        selection=[("income", "Ingreso"), ("expense", "Gasto")],
        string="Debito es",
    )
    cash_flow_display_name = fields.Char(
        string="Nombre a mostrar en flujo de caja",
        help="Etiqueta que se mostrara en el reporte de flujo de caja. Si varias cuentas usan el mismo nombre, sus movimientos se sumaran en una sola linea.",
    )
