from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    prestamos_interest_loan_id = fields.Many2one(
        "prestamos.loan",
        string="Prestamo de intereses",
        copy=False,
        index=True,
        ondelete="set null",
    )
    prestamos_other_interest_loan_id = fields.Many2one(
        "prestamos.loan",
        string="Prestamo - otros intereses",
        copy=False,
        index=True,
        ondelete="set null",
    )
