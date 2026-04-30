from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_bank_or_financial_entity = fields.Boolean(
        string="Es entidad bancaria o financiera",
        help="Define si los prestamos de este contacto usan las cuentas bancarias/financieras o las no bancarias.",
    )

    def _is_loan_owner_or_partner(self):
        self.ensure_one()
        if not self:
            return False
        return bool(
            self.env["res.users"].sudo().search_count(
                [
                    ("partner_id", "=", self.id),
                    ("active", "=", True),
                    ("share", "=", False),
                ]
            )
        )
