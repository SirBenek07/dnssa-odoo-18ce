import re
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero


class BalanceGeneralReport(models.AbstractModel):
    _name = "report.reportes_financieros.balance_general_pdf"
    _description = "Reporte PDF Balance General"

    def _code_sort_key(self, code):
        parts = re.split(r"(\d+)", code or "")
        key = []
        for part in parts:
            if not part:
                continue
            key.append(int(part) if part.isdigit() else part.lower())
        return key

    def _is_top_level_group(self, code):
        return bool(code) and code.isdigit()

    def _is_report_root(self, code):
        return bool(code)

    def _sign_multiplier_for_account_type(self, account_type):
        if not account_type:
            return 1
        if (
            account_type.startswith("liability")
            or account_type.startswith("equity")
            or account_type.startswith("income")
        ):
            return -1
        return 1

    def _sign_multiplier_for_group_code(self, code):
        top_code = (code or "").split(".")[0]
        if top_code in {"2", "3", "4"}:
            return -1
        return 1

    def _code_belongs_to_group(self, account_code, group_code):
        if not account_code or not group_code:
            return False
        return account_code == group_code or account_code.startswith(group_code + ".")

    def _get_last_closing_date(self, company, date_to):
        # Prefer real lock dates configured in Odoo accounting settings.
        lock_candidates = []
        for field_name in ("fiscalyear_lock_date", "period_lock_date"):
            value = getattr(company, field_name, False)
            if value and value <= date_to:
                lock_candidates.append(value)
        if lock_candidates:
            return max(lock_candidates)
        # Fallback when lock dates are not configured.
        return date(date_to.year - 1, 12, 31)

    def _get_provisional_result(self, wizard):
        last_closing_date = self._get_last_closing_date(wizard.company_id, wizard.date_to)
        provisional_from = max(wizard.date_from, last_closing_date + timedelta(days=1))
        provisional_to = wizard.date_to

        domain = [
            ("company_id", "=", wizard.company_id.id),
            ("move_id.state", "=", "posted"),
            ("date", ">=", provisional_from),
            ("date", "<=", provisional_to),
            ("account_id.account_type", "in", ["income", "income_other", "expense", "expense_depreciation", "expense_direct_cost"]),
        ]
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
            "date_from": provisional_from,
            "date_to": provisional_to,
            "last_closing_date": last_closing_date,
            "total_ingreso": total_ingreso,
            "total_egreso": total_egreso,
            "resultado": total_ingreso - total_egreso,
        }

    def _get_account_balances(self, account_ids, company_id, date_from, date_to):
        if not account_ids:
            return {}, {}, set()
        domain = [
            ("account_id", "in", account_ids),
            ("company_id", "=", company_id),
            ("move_id.state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
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

    def _prepare_lines(self, wizard):
        group_model = self.env["account.group"]
        account_model = self.env["account.account"]
        currency = wizard.company_id.currency_id

        groups = group_model.search([], order="code_prefix_start").filtered(
            lambda g: self._is_report_root(g.code_prefix_start)
        )
        accounts = account_model.search(
            [
                ("company_ids", "in", [wizard.company_id.id]),
                ("group_id", "in", groups.ids),
            ]
        )

        account_balance_map, account_debit_credit_map, moved_accounts = self._get_account_balances(
            accounts.ids,
            wizard.company_id.id,
            wizard.date_from,
            wizard.date_to,
        )
        if wizard.show_accounts_without_moves:
            visible_accounts = accounts
        else:
            visible_accounts = accounts.filtered(lambda a: a.id in moved_accounts)
        visible_accounts = visible_accounts.filtered(
            lambda a: self._is_report_root(a.code)
        )

        lines = []
        for group in groups:
            group_code = group.code_prefix_start or ""
            group_has_visible_accounts = any(
                self._code_belongs_to_group(account.code, group_code)
                for account in visible_accounts
            )
            group_balance = sum(
                account_balance_map.get(account.id, 0.0)
                for account in visible_accounts
                if self._code_belongs_to_group(account.code, group_code)
            )
            group_debit = sum(
                account_debit_credit_map.get(account.id, {}).get("debit", 0.0)
                for account in visible_accounts
                if self._code_belongs_to_group(account.code, group_code)
            )
            group_credit = sum(
                account_debit_credit_map.get(account.id, {}).get("credit", 0.0)
                for account in visible_accounts
                if self._code_belongs_to_group(account.code, group_code)
            )
            if (
                not wizard.show_accounts_without_moves
                and not group_has_visible_accounts
                and float_is_zero(group_balance, precision_rounding=currency.rounding)
            ):
                continue
            lines.append(
                {
                    "line_type": "group",
                    "code": group_code,
                    "name": group.name,
                    "balance": group_balance,
                    "is_top_level": self._is_top_level_group(group_code),
                    "level": group_code.count(".") if group_code else 0,
                    "account_type": False,
                    "debit": group_debit,
                    "credit": group_credit,
                }
            )

        for account in visible_accounts:
            balance = account_balance_map.get(account.id, 0.0)
            if (
                not wizard.show_accounts_without_moves
                and account.id not in moved_accounts
                and float_is_zero(balance, precision_rounding=currency.rounding)
            ):
                continue
            lines.append(
                {
                    "line_type": "account",
                    "code": account.code,
                    "name": account.name,
                    "balance": balance,
                    "is_top_level": False,
                    "level": account.code.count(".") if account.code else 0,
                    "account_type": account.account_type,
                    "debit": account_debit_credit_map.get(account.id, {}).get("debit", 0.0),
                    "credit": account_debit_credit_map.get(account.id, {}).get("credit", 0.0),
                }
            )

        lines.sort(key=lambda line: self._code_sort_key(line["code"]))
        return lines, visible_accounts, account_balance_map

    def _prepare_summary(self, lines, provisional):
        top_line_map = {
            line["code"]: line
            for line in lines
            if line.get("line_type") == "group" and line.get("is_top_level")
        }
        return {
            "total_activo": top_line_map.get("1", {}).get("display_balance", 0.0),
            "total_pasivo": top_line_map.get("2", {}).get("display_balance", 0.0),
            "total_patrimonio_neto": top_line_map.get("3", {}).get("display_balance", 0.0),
            "total_ingreso": provisional["total_ingreso"],
            "total_egreso": provisional["total_egreso"],
            "resultado": provisional["resultado"],
        }

    def _inject_provisional_into_resultado_ejercicio(self, lines, provisional_result, wizard):
        target_code = "3.03.02"
        # Convert P&L result (income-expense) into equity-normalized raw balance.
        raw_result_delta = -provisional_result
        target_line = next(
            (
                line
                for line in lines
                if line.get("line_type") == "account" and line.get("code") == target_code
            ),
            None,
        )
        if target_line is None:
            account_result = self.env["account.account"].search(
                [
                    ("code", "=", target_code),
                    ("company_ids", "in", [wizard.company_id.id]),
                ],
                limit=1,
            )
            target_line = {
                "line_type": "account",
                "code": target_code,
                "name": account_result.name if account_result else "RESULTADO DEL EJERCICIO",
                "balance": 0.0,
                "is_top_level": False,
                "level": target_code.count("."),
                "account_type": account_result.account_type if account_result else "equity",
            }
            lines.append(target_line)

        if target_line:
            target_line["balance"] = target_line.get("balance", 0.0) + raw_result_delta
            # Ensure parent groups (e.g. 3.03) exist so hierarchy is complete.
            parent_codes = []
            code_parts = target_code.split(".")
            for idx in range(1, len(code_parts)):
                parent_codes.append(".".join(code_parts[:idx]))
            group_lines_by_code = {
                line.get("code"): line
                for line in lines
                if line.get("line_type") == "group"
            }
            missing_parent_codes = [code for code in parent_codes if code not in group_lines_by_code]
            if missing_parent_codes:
                missing_groups = self.env["account.group"].search(
                    [("code_prefix_start", "in", missing_parent_codes)]
                )
                for group in missing_groups:
                    code = group.code_prefix_start
                    group_line = {
                        "line_type": "group",
                        "code": code,
                        "name": group.name,
                        "balance": 0.0,
                        "is_top_level": self._is_top_level_group(code),
                        "level": code.count(".") if code else 0,
                        "account_type": False,
                    }
                    lines.append(group_line)
                    group_lines_by_code[code] = group_line
            for line in lines:
                if line.get("line_type") == "group":
                    group_code = line.get("code") or ""
                    if group_code and (
                        target_code == group_code
                        or target_code.startswith(group_code + ".")
                    ):
                        line["balance"] = line.get("balance", 0.0) + raw_result_delta

    def _apply_display_sign(self, lines):
        for line in lines:
            if line.get("line_type") == "account":
                mult = self._sign_multiplier_for_account_type(line.get("account_type"))
            else:
                mult = self._sign_multiplier_for_group_code(line.get("code"))
            line["display_balance"] = line.get("balance", 0.0) * mult
            line["display_debit"] = line.get("debit", 0.0)
            line["display_credit"] = line.get("credit", 0.0)

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        wizard = self.env["balance.general.wizard"].browse(data.get("wizard_id") or docids[:1])
        wizard.ensure_one()

        period_label = (
            wizard.date_range_id.name
            if wizard.date_range_id
            else f"Desde {fields.Date.to_string(wizard.date_from)} Hasta {fields.Date.to_string(wizard.date_to)}"
        )

        lines, visible_accounts, account_balance_map = self._prepare_lines(wizard)
        provisional = self._get_provisional_result(wizard)
        self._inject_provisional_into_resultado_ejercicio(
            lines, provisional["resultado"], wizard
        )
        lines.sort(key=lambda line: self._code_sort_key(line["code"]))
        self._apply_display_sign(lines)

        summary = self._prepare_summary(lines, provisional)

        return {
            "doc_ids": wizard.ids,
            "doc_model": "balance.general.wizard",
            "docs": wizard,
            "company": wizard.company_id,
            "currency": wizard.company_id.currency_id,
            "period_label": period_label,
            "lines": lines,
            "summary": summary,
            "show_debit_credit_columns": wizard.show_debit_credit_columns,
        }
