from odoo import models


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
