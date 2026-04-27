from odoo import fields, models


class BalanceGeneralWizard(models.TransientModel):
    _inherit = "balance.general.wizard"

    project_ids = fields.Many2many(
        comodel_name="project.project",
        relation="balance_general_wizard_project_rel",
        column1="wizard_id",
        column2="project_id",
        string="Filtrar por proyecto",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
