from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

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
    prestamos_component = fields.Selection(
        [
            ("capital", "Capital"),
            ("interest", "Interes"),
            ("reclassification", "Reclasificacion"),
        ],
        string="Componente prestamo",
        copy=False,
    )
