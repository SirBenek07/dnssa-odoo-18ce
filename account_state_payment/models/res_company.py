from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_in_payment_state_until_bank_match = fields.Boolean(
        string="Usar 'En proceso de pago' hasta conciliacion bancaria",
        default=True,
        help="Si esta activo, las facturas pagadas con pagos pendientes de conciliacion bancaria "
             "quedaran en 'En proceso de pago' en lugar de 'Pagado'.",
    )
