from odoo import api, models
from odoo.tools.float_utils import float_is_zero


class BalanceGeneralReport(models.AbstractModel):
    _inherit = "report.reportes_financieros.balance_general_pdf"

    def _get_range_accounts(self, company_id, code_from, code_to):
        account_model = self.env["account.account"]
        if code_from and code_to and code_from == code_to:
            return account_model.search(
                [
                    ("company_ids", "in", [company_id]),
                    "|",
                    ("code", "=", code_from),
                    ("code", "=like", f"{code_from}%"),
                ]
            )
        return account_model.search(
            [
                ("company_ids", "in", [company_id]),
                ("code", ">=", code_from),
                ("code", "<=", code_to),
            ]
        )

    def _get_partial_result_lines(self, wizard):
        account_model = self.env["account.account"]
        result_accounts = account_model.search(
            [
                ("company_ids", "in", [wizard.company_id.id]),
                ("is_result_account", "=", True),
                ("result_range_ids", "!=", False),
            ]
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
        for result_account in result_accounts.sorted(key=lambda a: self._code_sort_key(a.code)):
            total = 0.0
            range_labels = []
            for range_line in result_account.result_range_ids.sorted(
                key=lambda r: (r.sequence, r.id)
            ):
                range_accounts = self._get_range_accounts(
                    wizard.company_id.id, range_line.code_from, range_line.code_to
                )
                subtotal = sum(
                    display_balance_map.get(range_account.id, 0.0)
                    for range_account in range_accounts
                )
                sign = -1 if range_line.sign == "minus" else 1
                total += sign * subtotal
                range_labels.append(
                    f"{'-' if sign < 0 else '+'} {range_line.code_from}..{range_line.code_to}"
                )

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
        for partial in partial_lines:
            code = partial["code"]
            display_balance = partial["balance"] * self._sign_multiplier_for_group_code(code)
            line_vals = {
                "line_type": "group",
                "code": code,
                "name": partial["name"],
                "balance": partial["balance"],
                "display_balance": display_balance,
                "is_top_level": True,
                "level": 0,
                "account_type": False,
            }
            if code in existing_by_code:
                existing_by_code[code].update(line_vals)
            else:
                values["lines"].append(line_vals)
        values["lines"] = sorted(values["lines"], key=lambda line: self._code_sort_key(line["code"]))
        values["partial_result_lines"] = partial_lines
        return values
