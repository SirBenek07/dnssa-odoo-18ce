from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    _inherit = "account.tax"

    is_impuesto_inmobiliario = fields.Boolean(
        string="Es impuesto inmobiliario",
        help=(
            "Aplica una distribucion fija de 70% exenta y 30% gravada con IVA 5%. "
            "Si el impuesto esta incluido en el precio, el total ingresado se divide "
            "entre 1,015 antes de repartir la base."
        ),
    )

    @api.onchange("is_impuesto_inmobiliario")
    def _onchange_is_impuesto_inmobiliario(self):
        for tax in self:
            if tax.is_impuesto_inmobiliario:
                tax.amount_type = "percent"
                tax.amount = 5.0

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._normalize_impuesto_inmobiliario_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("is_impuesto_inmobiliario"):
            vals = self._normalize_impuesto_inmobiliario_vals(vals)
        return super().write(vals)

    @api.constrains("is_impuesto_inmobiliario", "amount_type", "amount")
    def _check_impuesto_inmobiliario_config(self):
        for tax in self.filtered("is_impuesto_inmobiliario"):
            if tax.amount_type != "percent":
                raise ValidationError(
                    _("El impuesto inmobiliario debe usar el tipo de calculo Porcentaje.")
                )
            if tax.amount != 5.0:
                raise ValidationError(
                    _("El impuesto inmobiliario siempre utiliza IVA 5%.")
                )

    def _normalize_impuesto_inmobiliario_vals(self, vals):
        if vals.get("is_impuesto_inmobiliario"):
            vals = dict(vals)
            vals["amount_type"] = "percent"
            vals["amount"] = 5.0
        return vals

    def _is_impuesto_inmobiliario_price_included(self, special_mode):
        self.ensure_one()
        if special_mode == "total_included":
            return True
        if special_mode == "total_excluded":
            return False
        return self.price_include

    def _compute_impuesto_inmobiliario_tax_details(
        self,
        price_unit,
        quantity,
        special_mode=False,
        manual_tax_amounts=None,
        filter_tax_function=None,
    ):
        self.ensure_one()

        if filter_tax_function and not filter_tax_function(self):
            raw_base = price_unit * quantity
            return {
                "total_excluded": raw_base,
                "total_included": raw_base,
                "taxes_data": [],
            }

        total_input = price_unit * quantity
        price_is_included = self._is_impuesto_inmobiliario_price_included(special_mode)

        if price_is_included:
            total_excluded = total_input / 1.015 if total_input else 0.0
            total_included = total_input
        else:
            total_excluded = total_input
            total_included = total_input

        taxable_base = total_excluded * 0.30
        tax_amount = taxable_base * 0.05

        manual_tax_data = manual_tax_amounts and manual_tax_amounts.get(str(self.id), {}) or {}
        if "base_amount_currency" in manual_tax_data:
            taxable_base = manual_tax_data["base_amount_currency"]
        if "tax_amount_currency" in manual_tax_data:
            tax_amount = manual_tax_data["tax_amount_currency"]

        if not price_is_included:
            total_included = total_excluded + tax_amount

        return {
            "total_excluded": total_excluded,
            "total_included": total_included,
            "taxes_data": [
                {
                    "tax": self,
                    "taxes": self.env["account.tax"],
                    "group": self.env["account.tax"],
                    "batch": self,
                    "tax_amount": tax_amount,
                    "price_include": price_is_included,
                    "base_amount": taxable_base,
                    "is_reverse_charge": False,
                }
            ],
        }

    def _get_tax_details(
        self,
        price_unit,
        quantity,
        precision_rounding=0.01,
        rounding_method="round_per_line",
        product=None,
        product_uom=None,
        special_mode=False,
        manual_tax_amounts=None,
        filter_tax_function=None,
    ):
        if len(self) == 1 and self.is_impuesto_inmobiliario:
            return self._compute_impuesto_inmobiliario_tax_details(
                price_unit=price_unit,
                quantity=quantity,
                special_mode=special_mode,
                manual_tax_amounts=manual_tax_amounts,
                filter_tax_function=filter_tax_function,
            )
        return super()._get_tax_details(
            price_unit=price_unit,
            quantity=quantity,
            precision_rounding=precision_rounding,
            rounding_method=rounding_method,
            product=product,
            product_uom=product_uom,
            special_mode=special_mode,
            manual_tax_amounts=manual_tax_amounts,
            filter_tax_function=filter_tax_function,
        )
