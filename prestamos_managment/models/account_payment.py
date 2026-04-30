from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    prestamos_loan_id = fields.Many2one(
        "prestamos.loan",
        string="Prestamo",
        copy=False,
        index=True,
        ondelete="set null",
    )
    prestamos_schedule_line_id = fields.Many2one(
        "prestamos.loan.line",
        string="Cuota de prestamo",
        copy=False,
        index=True,
        ondelete="set null",
    )
    prestamos_payment_id = fields.Many2one(
        "prestamos.loan.payment",
        string="Tablero de pago de prestamo",
        copy=False,
        index=True,
        ondelete="set null",
    )
