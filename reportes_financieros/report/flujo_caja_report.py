from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero


class FlujoCajaReport(models.AbstractModel):
    _name = "report.reportes_financieros.flujo_caja_pdf"
    _description = "Reporte PDF Flujo de Caja"

    def _get_cash_accounts(self, company):
        return self.env["account.account"].search(
            [
                ("company_ids", "in", [company.id]),
                ("account_type", "=", "asset_cash"),
                ("deprecated", "=", False),
            ],
            order="code, id",
        )

    def _get_balance_for_accounts(self, account_ids, company_id, date_from=None, date_to=None):
        if not account_ids:
            return 0.0
        domain = [
            ("company_id", "=", company_id),
            ("move_id.state", "=", "posted"),
            ("account_id", "in", account_ids),
        ]
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        result = self.env["account.move.line"].read_group(
            domain=domain,
            fields=["balance:sum"],
            groupby=[],
            lazy=False,
        )
        return result[0]["balance"] if result else 0.0

    def _get_cash_flow_display_name(self, account):
        return (account.cash_flow_display_name or account.name or account.code or "Sin nombre").strip()

    def _add_group_amount(self, groups, key, label, amount, detail_name=None):
        group = groups.setdefault(
            key,
            {"key": key, "label": label, "amount": 0.0, "details": defaultdict(float)},
        )
        group["amount"] += amount
        if detail_name:
            group["details"][detail_name] += amount

    def _prepare_grouped_lines(self, grouped_data):
        lines = []
        for group in grouped_data.values():
            details = [
                {"name": name, "amount": amount}
                for name, amount in sorted(
                    group["details"].items(), key=lambda item: abs(item[1]), reverse=True
                )
            ]
            lines.append(
                {
                    "key": group["key"],
                    "label": group["label"],
                    "amount": group["amount"],
                    "details": details,
                }
            )
        lines.sort(key=lambda line: (-abs(line["amount"]), line["label"]))
        return lines

    def _collect_configured_cash_flow_groups(self, company, date_from, date_to, cash_accounts):
        aml_model = self.env["account.move.line"]
        cash_lines = aml_model.search(
            [
                ("company_id", "=", company.id),
                ("move_id.state", "=", "posted"),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("account_id", "in", cash_accounts.ids),
            ],
            order="date, move_id, id",
        )
        grouped_moves = defaultdict(lambda: self.env["account.move.line"])
        for line in cash_lines:
            grouped_moves[line.move_id.id] |= line

        income_groups = {}
        expense_groups = {}
        rounding = company.currency_id.rounding
        cash_account_ids = set(cash_accounts.ids)

        for cash_move_lines in grouped_moves.values():
            move = cash_move_lines[:1].move_id
            cash_delta = sum(cash_move_lines.mapped("balance"))
            if float_is_zero(cash_delta, precision_rounding=rounding):
                continue

            configured_lines = move.line_ids.filtered(
                lambda line: line.account_id.id not in cash_account_ids
                and line.account_id.include_in_cash_flow
                and line.balance
            )
            if not configured_lines:
                continue

            total_weight = sum(abs(line.balance) for line in configured_lines) or len(
                configured_lines
            )
            pending = abs(cash_delta)
            for index, line in enumerate(configured_lines, start=1):
                account = line.account_id
                if index == len(configured_lines):
                    current_amount = pending
                else:
                    weight = abs(line.balance) or 1.0
                    current_amount = abs(cash_delta) * weight / total_weight
                    pending -= current_amount

                behavior = False
                if line.credit:
                    behavior = account.cash_flow_credit_behavior
                elif line.debit:
                    behavior = account.cash_flow_debit_behavior

                if not behavior:
                    continue

                display_name = self._get_cash_flow_display_name(account)
                detail_name = f"{account.code or ''} {account.name or ''}".strip()
                if behavior == "income" and cash_delta > 0:
                    self._add_group_amount(
                        income_groups,
                        f"income_label_{display_name}",
                        display_name,
                        current_amount,
                        detail_name,
                    )
                elif behavior == "expense" and cash_delta < 0:
                    self._add_group_amount(
                        expense_groups,
                        f"expense_label_{display_name}",
                        display_name,
                        current_amount,
                        detail_name,
                    )

        return {
            "income_lines": self._prepare_grouped_lines(income_groups),
            "expense_lines": self._prepare_grouped_lines(expense_groups),
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        wizard = self.env["flujo.caja.wizard"].browse(data.get("wizard_id") or docids[:1])
        wizard.ensure_one()

        cash_accounts = self._get_cash_accounts(wizard.company_id)
        opening_date = wizard.date_from - timedelta(days=1)
        opening_balance = self._get_balance_for_accounts(
            cash_accounts.ids, wizard.company_id.id, date_to=opening_date
        )

        configured_groups = self._collect_configured_cash_flow_groups(
            wizard.company_id,
            wizard.date_from,
            wizard.date_to,
            cash_accounts,
        )
        income_lines = configured_groups["income_lines"]
        expense_lines = configured_groups["expense_lines"]

        if not wizard.include_zero_lines:
            income_lines = [
                line
                for line in income_lines
                if not float_is_zero(
                    line["amount"],
                    precision_rounding=wizard.company_id.currency_id.rounding,
                )
            ]
            expense_lines = [
                line
                for line in expense_lines
                if not float_is_zero(
                    line["amount"],
                    precision_rounding=wizard.company_id.currency_id.rounding,
                )
            ]

        total_income = sum(line["amount"] for line in income_lines)
        total_expense = sum(line["amount"] for line in expense_lines)
        net_change = total_income - total_expense
        closing_balance = opening_balance + net_change
        main_message = (
            "El reporte usa exclusivamente cuentas marcadas para flujo de caja."
            if income_lines or expense_lines
            else "No hay movimientos configurados para flujo de caja en el periodo."
        )

        period_label = (
            wizard.date_range_id.name
            if wizard.date_range_id
            else f"Desde {fields.Date.to_string(wizard.date_from)} Hasta {fields.Date.to_string(wizard.date_to)}"
        )

        return {
            "doc_ids": wizard.ids,
            "doc_model": "flujo.caja.wizard",
            "docs": wizard,
            "company": wizard.company_id,
            "currency": wizard.company_id.currency_id,
            "period_label": period_label,
            "cash_accounts": cash_accounts,
            "opening_balance": opening_balance,
            "income_lines": income_lines,
            "expense_lines": expense_lines,
            "total_income": total_income,
            "total_expense": total_expense,
            "net_change": net_change,
            "closing_balance": closing_balance,
            "main_message": main_message,
            "show_details": wizard.show_details,
        }
