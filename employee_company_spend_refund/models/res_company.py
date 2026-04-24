from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    employee_spend_refund_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de reembolso a empleados",
        domain="[('account_type', '=', 'liability_payable'), ('deprecated', '=', False)]",
        check_company=True,
        help="Cuenta por pagar opcional usada para reclasificar gastos de la empresa "
        "pagados personalmente por empleados.",
    )
    company_spend_refund_default = fields.Boolean(
        string="Gasto de empresa pagado por empleado por defecto",
        help="Activa por defecto el flujo de reembolso de gastos de empresa pagados por empleados.",
    )
