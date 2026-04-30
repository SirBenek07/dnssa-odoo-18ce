import unicodedata

from odoo import models


def _normalize_payment_label(value):
    value = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in value if not unicodedata.combining(char)).casefold()


class AccountPaymentMethod(models.Model):
    _inherit = "account.payment.method"

    def _auto_link_payment_methods(self, payment_methods, methods_info):
        cheque_methods = payment_methods.filtered(lambda m: m.code == "dns_cheque")
        other_methods = payment_methods - cheque_methods
        if other_methods:
            super()._auto_link_payment_methods(other_methods, methods_info)
        return payment_methods

    def _get_payment_method_information(self):
        info = super()._get_payment_method_information()
        info["dns_cheque"] = {"mode": "multi", "type": ("bank",)}
        return info


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    def _is_dns_transfer_method_line(self):
        self.ensure_one()
        labels = (
            self.name,
            self.payment_method_id.name,
            self.code,
        )
        return (
            self.payment_type == "outbound"
            and self.code != "dns_cheque"
            and any("transfer" in _normalize_payment_label(label) for label in labels)
        )
