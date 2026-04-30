from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    loan_default_short_term_account_id = fields.Many2one(
        related="company_id.loan_default_short_term_account_id",
        readonly=False,
        string="Cuenta de corto plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_default_long_term_account_id = fields.Many2one(
        related="company_id.loan_default_long_term_account_id",
        readonly=False,
        string="Cuenta de largo plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_default_expense_account_id = fields.Many2one(
        related="company_id.loan_default_expense_account_id",
        readonly=False,
        string="Cuenta de gastos",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'expense')]",
    )
    loan_bank_payable_account_id = fields.Many2one(
        related="company_id.loan_bank_payable_account_id",
        readonly=False,
        string="Cuenta pasivo de prestamos bancarios",
        check_company=True,
        domain="[('deprecated', '=', False), ('internal_group', '=', 'liability')]",
    )
    loan_non_bank_payable_account_id = fields.Many2one(
        related="company_id.loan_non_bank_payable_account_id",
        readonly=False,
        string="Cuenta pasivo de prestamos no bancarios",
        check_company=True,
        domain="[('deprecated', '=', False), ('internal_group', '=', 'liability')]",
    )
    loan_bank_short_term_account_id = fields.Many2one(
        related="company_id.loan_bank_short_term_account_id",
        readonly=False,
        string="Cuenta de corto plazo bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_bank_long_term_account_id = fields.Many2one(
        related="company_id.loan_bank_long_term_account_id",
        readonly=False,
        string="Cuenta de largo plazo bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_owner_short_term_account_id = fields.Many2one(
        related="company_id.loan_owner_short_term_account_id",
        readonly=False,
        string="Cuenta de corto plazo dueno/socio",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_owner_long_term_account_id = fields.Many2one(
        related="company_id.loan_owner_long_term_account_id",
        readonly=False,
        string="Cuenta de largo plazo dueno/socio",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_non_bank_short_term_account_id = fields.Many2one(
        related="company_id.loan_non_bank_short_term_account_id",
        readonly=False,
        string="Cuenta de corto plazo no bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_non_bank_long_term_account_id = fields.Many2one(
        related="company_id.loan_non_bank_long_term_account_id",
        readonly=False,
        string="Cuenta de largo plazo no bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_short_interest_payable_account_id = fields.Many2one(
        related="company_id.loan_short_interest_payable_account_id",
        readonly=False,
        string="Cuenta de intereses a pagar a corto plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'liability_payable')]",
    )
    loan_long_interest_payable_account_id = fields.Many2one(
        related="company_id.loan_long_interest_payable_account_id",
        readonly=False,
        string="Cuenta de intereses a pagar a largo plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'liability_payable')]",
    )
    loan_interest_product_id = fields.Many2one(
        related="company_id.loan_interest_product_id",
        readonly=False,
        string="Producto de intereses",
        domain="[('purchase_ok', '=', True)]",
    )
    loan_bank_interest_expense_account_id = fields.Many2one(
        related="company_id.loan_bank_interest_expense_account_id",
        readonly=False,
        string="Cuenta de gastos de intereses bancarios/financieros",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'expense')]",
    )
    loan_non_bank_interest_expense_account_id = fields.Many2one(
        related="company_id.loan_non_bank_interest_expense_account_id",
        readonly=False,
        string="Cuenta de gastos de intereses no bancarios",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'expense')]",
    )
