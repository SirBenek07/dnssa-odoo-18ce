from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    employee_spend_refund_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de reembolso a empleados",
        domain="[('account_type', 'in', ('liability_payable', 'liability_current')), ('deprecated', '=', False)]",
        check_company=True,
        help="Cuenta por pagar opcional usada para reclasificar gastos de la empresa "
        "pagados personalmente por empleados.",
    )
