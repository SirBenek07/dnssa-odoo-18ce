from odoo import api, models
from odoo.tools.float_utils import float_is_zero
from odoo.tools import float_round


class BalanceGeneralReport(models.AbstractModel):
    _inherit = "report.reportes_financieros.balance_general_pdf"

    def _get_year_result_account(self, wizard):
        account = wizard.company_id.year_result_account_id
        if account:
            return account
        return self.env["account.account"].search(
            [
                ("company_ids", "in", [wizard.company_id.id]),
                ("is_year_result_account", "=", True),
            ],
            limit=1,
        )

    def _code_is_in_range(self, account_code, code_from, code_to):
        if not account_code or not code_from or not code_to:
            return False
        from_parts = code_from.split(".")
        to_parts = code_to.split(".")
        depth = min(len(from_parts), len(to_parts))
        account_parts = account_code.split(".")
        comparable_code = ".".join(account_parts[:depth]) if len(account_parts) >= depth else account_code
        return self._code_sort_key(code_from) <= self._code_sort_key(comparable_code) <= self._code_sort_key(code_to)

    def _get_range_accounts(self, company_id, code_from, code_to):
        account_model = self.env["account.account"]
        company_accounts = account_model.search([("company_ids", "in", [company_id])])
        return company_accounts.filtered(
            lambda account: self._code_is_in_range(account.code, code_from, code_to)
        )

    def _get_partial_result_lines(self, wizard):
        if not wizard.show_result_accounts:
            return []
        account_model = self.env["account.account"]
        result_accounts = account_model.search(
            [
                ("company_ids", "in", [wizard.company_id.id]),
                ("is_result_account", "=", True),
            ]
        )
        result_accounts = result_accounts.filtered(
            lambda a: not a.is_year_result_account and a.result_range_ids
        )
        if not result_accounts:
            return []

        source_accounts = account_model.browse()
        for result_account in result_accounts:
            for range_line in result_account.result_range_ids:
                source_accounts |= self._get_range_accounts(
                    wizard.company_id.id, range_line.code_from, range_line.code_to
                )
        if not source_accounts:
            return []

        grouped = self.env["account.move.line"].read_group(
            domain=[
                ("company_id", "=", wizard.company_id.id),
                ("move_id.state", "=", "posted"),
                ("date", ">=", wizard.date_from),
                ("date", "<=", wizard.date_to),
                ("account_id", "in", source_accounts.ids),
            ],
            fields=["account_id", "balance:sum"],
            groupby=["account_id"],
            lazy=False,
        )
        raw_balance_map = {
            line["account_id"][0]: line.get("balance", 0.0)
            for line in grouped
            if line.get("account_id")
        }
        display_balance_map = {}
        for source_account in source_accounts:
            multiplier = self._sign_multiplier_for_account_type(source_account.account_type)
            display_balance_map[source_account.id] = (
                raw_balance_map.get(source_account.id, 0.0) * multiplier
            )

        partial_lines = []
        rounding = wizard.company_id.currency_id.rounding
        computed_result_balance_map = {}
        for result_account in result_accounts.sorted(key=lambda a: self._code_sort_key(a.code)):
            total = 0.0
            range_labels = []
            for range_line in result_account.result_range_ids.sorted(
                key=lambda r: (r.sequence, r.id)
            ):
                range_accounts = self._get_range_accounts(
                    wizard.company_id.id, range_line.code_from, range_line.code_to
                )
                subtotal = 0.0
                for range_account in range_accounts:
                    if range_account.id in computed_result_balance_map:
                        subtotal += computed_result_balance_map[range_account.id]
                    else:
                        subtotal += display_balance_map.get(range_account.id, 0.0)
                sign = -1 if range_line.sign == "minus" else 1
                total += sign * subtotal
                range_labels.append(
                    f"{'-' if sign < 0 else '+'} {range_line.code_from}..{range_line.code_to}"
                )
            if result_account.is_renta_account:
                total *= 0.10
            total = float_round(total, precision_rounding=1.0)
            computed_result_balance_map[result_account.id] = total

            if (
                not wizard.show_accounts_without_moves
                and float_is_zero(total, precision_rounding=rounding)
            ):
                continue
            partial_lines.append(
                {
                    "code": result_account.code,
                    "name": result_account.name,
                    "balance": total,
                    "formula": " ".join(range_labels),
                }
            )
        return partial_lines

    @api.model
    def _get_report_values(self, docids, data=None):
        values = super()._get_report_values(docids, data=data)
        wizard = values.get("docs")
        partial_lines = self._get_partial_result_lines(wizard)
        existing_by_code = {line.get("code"): line for line in values.get("lines", [])}

        def _sum_child_accounts_display(code):
            prefix = f"{code}."
            child_accounts = [
                line
                for line in values.get("lines", [])
                if line.get("line_type") == "account"
                and str(line.get("code") or "").startswith(prefix)
            ]
            total = 0.0
            for line in child_accounts:
                account_type = line.get("account_type") or ""
                display_value = line.get("display_balance", 0.0)
                # For partial result parent lines, treat expenses as negative and
                # income as positive when aggregating visible children.
                if account_type.startswith("expense"):
                    total += -abs(display_value)
                elif account_type.startswith("income"):
                    total += abs(display_value)
                else:
                    total += display_value
            return child_accounts, total

        for partial in partial_lines:
            code = partial["code"]
            child_accounts, child_display_total = _sum_child_accounts_display(code)
            child_debit_total = sum(
                line.get("debit", line.get("display_debit", 0.0)) for line in child_accounts
            )
            child_credit_total = sum(
                line.get("credit", line.get("display_credit", 0.0))
                for line in child_accounts
            )
            if child_accounts:
                # If there are visible child accounts, force parent partial line to
                # be the arithmetic sum of those displayed children.
                balance = child_display_total
                display_balance = child_display_total
                debit = child_debit_total
                credit = child_credit_total
            else:
                balance = partial["balance"]
                display_balance = (
                    partial["balance"] * self._sign_multiplier_for_group_code(code)
                )
                debit = 0.0
                credit = 0.0
            line_vals = {
                "line_type": "group",
                "code": code,
                "name": partial["name"],
                "balance": balance,
                "display_balance": display_balance,
                "debit": debit,
                "credit": credit,
                "display_debit": debit,
                "display_credit": credit,
                "is_top_level": True,
                "level": 0,
                "account_type": False,
            }
            if code in existing_by_code:
                existing_by_code[code].update(line_vals)
            else:
                values["lines"].append(line_vals)

        if not wizard.show_result_accounts:
            values["lines"] = [
                line
                for line in values.get("lines", [])
                if self._get_section_key(line.get("code"), line.get("account_type"))
                != "estado_resultado"
            ]
        values["lines"] = sorted(values["lines"], key=lambda line: self._code_sort_key(line["code"]))
        values["sections"] = self._prepare_sections(values["lines"])
        values["partial_result_lines"] = partial_lines
        return values
