from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_py_document_type = fields.Selection(
        selection=[
            ("electronic", "Factura electronica"),
            ("non_electronic", "Factura no electronica"),
        ],
        string="Tipo de Documento",
        default=lambda self: self._default_l10n_py_document_type(),
        copy=False,
    )
    l10n_py_cdc = fields.Char(
        string="CDC",
        copy=False,
    )

    @api.model
    def _default_l10n_py_document_type(self):
        move_type = self.env.context.get("default_move_type", "entry")
        if move_type in ("out_invoice", "out_refund", "out_receipt"):
            return "electronic"
        if move_type in ("in_invoice", "in_refund", "in_receipt"):
            return "non_electronic"
        return "non_electronic"

    @api.onchange("move_type")
    def _onchange_move_type_set_l10n_py_document_type(self):
        for move in self:
            if move.move_type in ("out_invoice", "out_refund", "out_receipt"):
                move.l10n_py_document_type = "electronic"
            elif move.move_type in ("in_invoice", "in_refund", "in_receipt"):
                move.l10n_py_document_type = "non_electronic"

    @api.onchange("l10n_py_document_type")
    def _onchange_l10n_py_document_type_clear_cdc(self):
        for move in self:
            if move.l10n_py_document_type != "electronic":
                move.l10n_py_cdc = False
