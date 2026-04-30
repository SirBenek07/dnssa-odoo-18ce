from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    loan_default_short_term_account_id = fields.Many2one(
        "account.account",
        string="Prestamos - cuenta de corto plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_default_long_term_account_id = fields.Many2one(
        "account.account",
        string="Prestamos - cuenta de largo plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_default_expense_account_id = fields.Many2one(
        "account.account",
        string="Prestamos - cuenta de gastos",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'expense')]",
    )
    loan_bank_payable_account_id = fields.Many2one(
        "account.account",
        string="Pasivo de prestamos bancarios",
        check_company=True,
        domain="[('deprecated', '=', False), ('internal_group', '=', 'liability')]",
    )
    loan_non_bank_payable_account_id = fields.Many2one(
        "account.account",
        string="Pasivo de prestamos no bancarios",
        check_company=True,
        domain="[('deprecated', '=', False), ('internal_group', '=', 'liability')]",
    )
    loan_bank_short_term_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de corto plazo bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_bank_long_term_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de largo plazo bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_owner_short_term_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de corto plazo dueno/socio",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_owner_long_term_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de largo plazo dueno/socio",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_non_bank_short_term_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de corto plazo no bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_current', 'liability_payable'))]",
    )
    loan_non_bank_long_term_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de largo plazo no bancario",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', 'in', ('liability_non_current', 'liability_payable'))]",
    )
    loan_short_interest_payable_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de intereses a pagar a corto plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'liability_payable')]",
    )
    loan_long_interest_payable_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de intereses a pagar a largo plazo",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'liability_payable')]",
    )
    loan_interest_product_id = fields.Many2one(
        "product.product",
        string="Producto de intereses",
        domain="[('purchase_ok', '=', True)]",
    )
    loan_bank_interest_expense_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de gastos de intereses bancarios/financieros",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'expense')]",
    )
    loan_non_bank_interest_expense_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de gastos de intereses no bancarios",
        check_company=True,
        domain="[('deprecated', '=', False), ('account_type', '=', 'expense')]",
    )
