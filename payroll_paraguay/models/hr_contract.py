from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrContract(models.Model):
    _inherit = "hr.contract"

    py_payment_scheme = fields.Selection(
        [
            ("ips_dependiente", "Dependiente IPS"),
            ("factura_proveedor", "Factura de Proveedor"),
        ],
        string="Esquema de pago",
        required=True,
        default="ips_dependiente",
    )
    py_vendor_partner_id = fields.Many2one(
        "res.partner",
        string="Proveedor para facturacion",
        help="Proveedor al que se le genera la factura cuando el esquema es "
        "'Factura de Proveedor'.",
    )
    py_vendor_product_id = fields.Many2one(
        "product.product",
        string="Producto para facturacion",
        domain=[("type", "=", "service")],
        help="Producto del concepto a facturar. Si se deja vacio se usa el "
        "producto por defecto configurado en Ajustes de Nomina.",
    )
    py_vendor_payable_account_id = fields.Many2one(
        "account.account",
        string="Cuenta por pagar (factura nomina)",
        domain=[("account_type", "=", "liability_payable"), ("deprecated", "=", False)],
        help="Si se define, se usara esta cuenta en la linea de pasivo de la "
        "factura proveedor generada desde nomina.",
    )
    py_vendor_journal_id = fields.Many2one(
        "account.journal",
        string="Diario factura proveedor",
        domain=[("type", "=", "purchase")],
        help="Diario para facturas de proveedor creadas desde nomina. "
        "Si no se define, se usa el diario por defecto de la compania.",
    )

    @api.onchange("employee_id", "py_payment_scheme", "company_id")
    def _onchange_py_vendor_partner(self):
        for contract in self:
            if contract.py_payment_scheme != "factura_proveedor":
                continue
            if contract.py_vendor_partner_id:
                continue
            partner = (
                contract.employee_id.work_contact_id
                or contract.employee_id.address_home_id
                or contract.employee_id.address_id
            )
            contract.py_vendor_partner_id = partner
            if (
                not contract.py_vendor_product_id
                and contract.company_id.py_default_vendor_product_id
            ):
                contract.py_vendor_product_id = contract.company_id.py_default_vendor_product_id
            if (
                not contract.py_vendor_journal_id
                and contract.company_id.py_default_vendor_journal_id
            ):
                contract.py_vendor_journal_id = contract.company_id.py_default_vendor_journal_id

    @api.constrains("py_payment_scheme", "py_vendor_partner_id")
    def _check_vendor_partner_required(self):
        for contract in self:
            if contract.py_payment_scheme == "factura_proveedor" and not contract.py_vendor_partner_id:
                raise ValidationError(
                    _(
                        "Debe configurar un proveedor para el contrato %(contract)s "
                        "cuando el esquema es Factura de Proveedor."
                    )
                    % {"contract": contract.display_name}
                )
