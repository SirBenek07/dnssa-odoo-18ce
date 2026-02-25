from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BalanceGeneralWizard(models.TransientModel):
    _name = "balance.general.wizard"
    _description = "Wizard Balance General"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    date_range_id = fields.Many2one(comodel_name="date.range", string="Periodo")
    date_from = fields.Date(
        string="Desde",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string="Hasta",
        required=True,
        default=fields.Date.context_today,
    )
    show_accounts_without_moves = fields.Boolean(
        string="Mostrar cuentas sin movimientos",
        default=False,
    )
    show_debit_credit_columns = fields.Boolean(
        string="Mostrar Debito y Credito",
        default=False,
    )

    @api.onchange("date_range_id")
    def _onchange_date_range_id(self):
        if self.date_range_id:
            self.date_from = self.date_range_id.date_start
            self.date_to = self.date_range_id.date_end

    @api.onchange("company_id")
    def _onchange_company_id(self):
        if (
            self.company_id
            and self.date_range_id
            and self.date_range_id.company_id
            and self.date_range_id.company_id != self.company_id
        ):
            self.date_range_id = False

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("La fecha Desde no puede ser mayor que Hasta."))

    @api.constrains("company_id", "date_range_id")
    def _check_company_date_range(self):
        for rec in self:
            if (
                rec.company_id
                and rec.date_range_id
                and rec.date_range_id.company_id
                and rec.company_id != rec.date_range_id.company_id
            ):
                raise ValidationError(
                    _("La empresa del periodo debe coincidir con la empresa del reporte.")
                )

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "reportes_financieros.action_report_balance_general"
        ).report_action(self, data={"wizard_id": self.id})
