from odoo import models


class BalanceGeneralReport(models.AbstractModel):
    _inherit = "report.reportes_financieros.balance_general_pdf"

    def _get_project_filter_domain(self):
        project_ids = self.env.context.get("balance_general_project_ids") or []
        if not project_ids:
            return []
        return [("move_id.project_id", "in", project_ids)]

    def _get_account_balances(self, account_ids, company_id, date_from, date_to):
        if not account_ids:
            return {}, {}, set()
        domain = [
            ("account_id", "in", account_ids),
            ("company_id", "=", company_id),
            ("move_id.state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ] + self._get_project_filter_domain()
        grouped = self.env["account.move.line"].read_group(
            domain=domain,
            fields=["account_id", "balance:sum", "debit:sum", "credit:sum"],
            groupby=["account_id"],
            lazy=False,
        )
        balances = {}
        debit_credit_map = {}
        moved_accounts = set()
        for item in grouped:
            if not item["account_id"]:
                continue
            account_id = item["account_id"][0]
            balances[account_id] = item.get("balance", 0.0)
            debit_credit_map[account_id] = {
                "debit": item.get("debit", 0.0),
                "credit": item.get("credit", 0.0),
            }
            moved_accounts.add(account_id)
        return balances, debit_credit_map, moved_accounts

    def _get_provisional_result(self, wizard):
        domain = [
            ("company_id", "=", wizard.company_id.id),
            ("move_id.state", "=", "posted"),
            ("date", ">=", wizard.date_from),
            ("date", "<=", wizard.date_to),
            (
                "account_id.account_type",
                "in",
                [
                    "income",
                    "income_other",
                    "expense",
                    "expense_depreciation",
                    "expense_direct_cost",
                ],
            ),
        ] + self._get_project_filter_domain()
        grouped = self.env["account.move.line"].read_group(
            domain=domain,
            fields=["account_id", "balance:sum"],
            groupby=["account_id"],
            lazy=False,
        )
        account_model = self.env["account.account"]
        account_ids = [line["account_id"][0] for line in grouped if line.get("account_id")]
        account_type_map = {
            acc.id: acc.account_type for acc in account_model.browse(account_ids)
        }

        total_ingreso = 0.0
        total_egreso = 0.0
        for line in grouped:
            if not line.get("account_id"):
                continue
            acc_id = line["account_id"][0]
            acc_type = account_type_map.get(acc_id, "")
            balance = line.get("balance", 0.0)
            if acc_type.startswith("income"):
                total_ingreso += -balance
            elif acc_type.startswith("expense"):
                total_egreso += balance

        return {
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "last_closing_date": self._get_last_closing_date(
                wizard.company_id, wizard.date_to
            ),
            "total_ingreso": total_ingreso,
            "total_egreso": total_egreso,
            "resultado": total_ingreso - total_egreso,
        }

    def _get_report_values(self, docids, data=None):
        data = data or {}
        wizard = self.env["balance.general.wizard"].browse(
            data.get("wizard_id") or docids[:1]
        )
        wizard.ensure_one()
        report = self.with_context(balance_general_project_ids=wizard.project_ids.ids)
        return super(BalanceGeneralReport, report)._get_report_values(docids, data)
