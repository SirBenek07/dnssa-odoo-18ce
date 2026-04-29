from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    partner_timbrado_id = fields.Many2one(
        "res.partner.timbrado",
        string="Timbrado del contacto",
        copy=False,
    )
    timbrado = fields.Char(string="Timbrado", copy=False)
    validez_timbrado = fields.Date(string="Validez de timbrado", copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            self._prepare_create_timbrado_vals(vals.copy()) for vals in vals_list
        ]
        return super().create(vals_list)

    def write(self, vals):
        vals = vals.copy()
        if not {
            "partner_id",
            "partner_timbrado_id",
            "l10n_py_document_type",
            "move_type",
        } & vals.keys():
            return super().write(vals)

        for move in self:
            move_vals = vals.copy()
            move_type = move_vals.get("move_type", move.move_type)
            partner = (
                self.env["res.partner"].browse(move_vals["partner_id"])
                if "partner_id" in move_vals
                else move.partner_id
            )
            partner_timbrado = move.partner_timbrado_id
            if "partner_timbrado_id" in vals:
                partner_timbrado = self.env["res.partner.timbrado"].browse(
                    vals["partner_timbrado_id"]
                )
                if partner_timbrado:
                    move_vals["l10n_py_document_type"] = (
                        self._get_document_type_from_partner_timbrado(partner_timbrado)
                    )
            elif "l10n_py_document_type" in vals and move_type == "in_invoice":
                partner_timbrado = move._get_partner_timbrado_for_document_type(
                    partner,
                    vals["l10n_py_document_type"],
                    current_timbrado=partner_timbrado,
                )
                move_vals["partner_timbrado_id"] = partner_timbrado.id or False
            elif "partner_id" in vals or "move_type" in vals:
                if move_type == "in_invoice" and partner:
                    partner_timbrado = move._get_default_partner_timbrado(partner)
                    move_vals["partner_timbrado_id"] = partner_timbrado.id or False
                    if partner_timbrado:
                        move_vals["l10n_py_document_type"] = (
                            self._get_document_type_from_partner_timbrado(
                                partner_timbrado
                            )
                        )
                else:
                    partner_timbrado = self.env["res.partner.timbrado"]
                    move_vals["partner_timbrado_id"] = False

            if partner_timbrado:
                document_type = move_vals.get(
                    "l10n_py_document_type", move.l10n_py_document_type
                )
                move_vals.update(
                    move._get_timbrado_invoice_vals(
                        partner_timbrado,
                        document_type == "electronic",
                    )
                )
            elif vals.get("partner_timbrado_id") is False:
                move_vals.update({"timbrado": False, "validez_timbrado": False})
            elif move_vals.get("l10n_py_document_type") == "electronic":
                move_vals["validez_timbrado"] = False
            elif "partner_timbrado_id" in move_vals:
                move_vals.update({"timbrado": False, "validez_timbrado": False})

            super(AccountMove, move).write(move_vals)
        return True

    @api.model
    def _prepare_create_timbrado_vals(self, vals):
        move_type = vals.get("move_type") or self.env.context.get("default_move_type")
        if move_type != "in_invoice":
            return vals

        if vals.get("partner_timbrado_id"):
            partner_timbrado = self.env["res.partner.timbrado"].browse(
                vals["partner_timbrado_id"]
            )
            vals["l10n_py_document_type"] = self._get_document_type_from_partner_timbrado(
                partner_timbrado
            )
            vals.update(
                self._get_timbrado_invoice_vals(
                    partner_timbrado,
                    self._is_electronic_document_type_from_vals(vals),
                )
            )
            return vals

        if vals.get("partner_id") and not vals.get("timbrado"):
            partner = self.env["res.partner"].browse(vals["partner_id"])
            if vals.get("l10n_py_document_type"):
                partner_timbrado = self._get_default_partner_timbrado(
                    partner,
                    is_electronic=vals["l10n_py_document_type"] == "electronic",
                )
            else:
                partner_timbrado = self._get_default_partner_timbrado(partner)
            if partner_timbrado:
                vals["partner_timbrado_id"] = partner_timbrado.id
                vals["l10n_py_document_type"] = (
                    self._get_document_type_from_partner_timbrado(partner_timbrado)
                )
                vals.update(
                    self._get_timbrado_invoice_vals(
                        partner_timbrado,
                        self._is_electronic_document_type_from_vals(vals),
                    )
                )
        return vals

    @api.model
    def _is_electronic_document_type_from_vals(self, vals):
        document_type = vals.get("l10n_py_document_type")
        if not document_type:
            move_type = vals.get("move_type") or self.env.context.get(
                "default_move_type", "entry"
            )
            document_type = "electronic" if move_type in (
                "out_invoice",
                "out_refund",
                "out_receipt",
            ) else "non_electronic"
        return document_type == "electronic"

    @api.model
    def _get_default_partner_timbrado(self, partner, is_electronic=None):
        domain = [("partner_id", "=", partner.id)]
        if is_electronic is not None:
            domain.append(("is_electronic", "=", is_electronic))
        return self.env["res.partner.timbrado"].search(domain, limit=1)

    @api.model
    def _get_document_type_from_partner_timbrado(self, partner_timbrado):
        return "electronic" if partner_timbrado.is_electronic else "non_electronic"

    def _get_partner_timbrado_for_document_type(
        self, partner, document_type, current_timbrado=False
    ):
        if not partner:
            return self.env["res.partner.timbrado"]

        is_electronic = document_type == "electronic"
        if (
            current_timbrado
            and current_timbrado.partner_id == partner
            and current_timbrado.is_electronic == is_electronic
        ):
            return current_timbrado

        return self._get_default_partner_timbrado(
            partner,
            is_electronic=is_electronic,
        )

    @api.model
    def _get_timbrado_invoice_vals(self, partner_timbrado, is_electronic=False):
        return {
            "timbrado": partner_timbrado.name,
            "validez_timbrado": (
                False if is_electronic else partner_timbrado.validez_timbrado
            ),
        }

    def _apply_partner_timbrado(self):
        for move in self:
            if move.partner_timbrado_id:
                values = move._get_timbrado_invoice_vals(
                    move.partner_timbrado_id,
                    move.l10n_py_document_type == "electronic",
                )
                move.timbrado = values["timbrado"]
                move.validez_timbrado = values["validez_timbrado"]
            else:
                move.timbrado = False
                move.validez_timbrado = False

    def _set_default_partner_timbrado(self):
        for move in self:
            if move.move_type != "in_invoice" or not move.partner_id:
                move.partner_timbrado_id = False
                move._apply_partner_timbrado()
                continue

            move.partner_timbrado_id = move._get_default_partner_timbrado(move.partner_id)
            if move.partner_timbrado_id:
                move.l10n_py_document_type = move._get_document_type_from_partner_timbrado(
                    move.partner_timbrado_id
                )
            move._apply_partner_timbrado()

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        res = super()._onchange_partner_id()
        self._set_default_partner_timbrado()
        return res

    @api.onchange("move_type")
    def _onchange_move_type_set_default_partner_timbrado(self):
        self._set_default_partner_timbrado()

    @api.onchange("l10n_py_document_type")
    def _onchange_l10n_py_document_type_set_timbrado_validity(self):
        for move in self:
            if move.move_type != "in_invoice" or not move.partner_id:
                if move.l10n_py_document_type == "electronic":
                    move.validez_timbrado = False
                continue

            move.partner_timbrado_id = move._get_partner_timbrado_for_document_type(
                move.partner_id,
                move.l10n_py_document_type,
                current_timbrado=move.partner_timbrado_id,
            )
            move._apply_partner_timbrado()

    @api.onchange("partner_timbrado_id")
    def _onchange_partner_timbrado_id(self):
        for move in self:
            if move.partner_timbrado_id:
                move.l10n_py_document_type = move._get_document_type_from_partner_timbrado(
                    move.partner_timbrado_id
                )
        self._apply_partner_timbrado()

    @api.constrains("timbrado", "move_type", "state")
    def _check_timbrado_required_for_vendor_bill(self):
        for move in self:
            if (
                move.move_type == "in_invoice"
                and move.state == "posted"
                and not (move.partner_timbrado_id or move.timbrado)
            ):
                raise ValidationError(_("El timbrado es obligatorio en facturas de proveedor."))

    @api.constrains(
        "validez_timbrado",
        "l10n_py_document_type",
        "move_type",
        "state",
    )
    def _check_validez_timbrado_required_for_vendor_bill(self):
        for move in self:
            if (
                move.move_type == "in_invoice"
                and move.state == "posted"
                and move.l10n_py_document_type != "electronic"
                and not move.validez_timbrado
            ):
                raise ValidationError(
                    _("La validez de timbrado es obligatoria en facturas de proveedor.")
                )

    @api.constrains(
        "partner_timbrado_id",
        "l10n_py_document_type",
        "move_type",
        "state",
    )
    def _check_timbrado_matches_document_type_for_vendor_bill(self):
        for move in self:
            if (
                move.move_type == "in_invoice"
                and move.state == "posted"
                and move.partner_timbrado_id
                and (
                    move.partner_timbrado_id.is_electronic
                    != (move.l10n_py_document_type == "electronic")
                )
            ):
                raise ValidationError(
                    _(
                        "El timbrado seleccionado no corresponde al tipo de documento de la factura."
                    )
                )

    @api.constrains("partner_timbrado_id", "partner_id")
    def _check_partner_timbrado_contact(self):
        for move in self:
            if (
                move.partner_timbrado_id
                and move.partner_id
                and move.partner_timbrado_id.partner_id != move.partner_id
            ):
                raise ValidationError(
                    _("El timbrado seleccionado no pertenece al contacto de la factura.")
                )

    @api.constrains(
        "validez_timbrado",
        "l10n_py_document_type",
        "invoice_date",
        "move_type",
    )
    def _check_validez_timbrado_after_invoice_date(self):
        """Keep timbrado validity aligned with the invoice date on vendor bills."""
        for move in self:
            if (
                move.move_type == "in_invoice"
                and move.l10n_py_document_type != "electronic"
                and move.validez_timbrado
                and move.invoice_date
                and move.validez_timbrado < move.invoice_date
            ):
                raise ValidationError(
                    _("La validez de timbrado no puede ser anterior a la fecha de la factura.")
                )
