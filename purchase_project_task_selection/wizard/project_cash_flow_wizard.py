from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date


class ProjectCashFlowWizard(models.TransientModel):
    _name = "project.cash.flow.wizard"
    _description = "Project Cash Flow Wizard"

    date_from = fields.Date(
        string="Fecha desde",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string="Fecha hasta",
        required=True,
        default=fields.Date.context_today,
    )
    project_ids = fields.Many2many(
        comodel_name="project.project",
        string="Proyectos",
        help="Si no selecciona proyectos, se incluiran todos los proyectos de la compania.",
    )
    include_order_links_fallback = fields.Boolean(
        string="Usar compra/venta como respaldo",
        default=True,
        help="Si una linea no tiene asociacion analitica a proyecto, se intentara asociar por vinculos de compra/venta.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Compania",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if active_model == "project.project" and active_ids:
            vals["project_ids"] = [(6, 0, active_ids)]
        return vals

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha desde no puede ser mayor que la fecha hasta."))

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref(
            "purchase_project_task_selection.action_report_project_cash_flow"
        ).report_action(self)

    def _get_selected_projects(self):
        self.ensure_one()
        if self.project_ids:
            return self.project_ids
        return self.env["project.project"].search(
            [("company_id", "in", [False, self.company_id.id])],
            order="name",
        )

    def _get_periods(self):
        self.ensure_one()
        periods = []
        date_from = fields.Date.to_date(self.date_from)
        date_to = fields.Date.to_date(self.date_to)
        cursor = date_from.replace(day=1)
        end_month = date_to.replace(day=1)
        while cursor <= end_month:
            next_month = cursor + relativedelta(months=1)
            periods.append(
                {
                    "key": cursor.strftime("%Y-%m"),
                    "label": format_date(self.env, cursor, date_format="MMM yyyy"),
                    "date_from": max(cursor, date_from),
                    "date_to": min(next_month - timedelta(days=1), date_to),
                }
            )
            cursor = next_month
        return periods

    def _line_project_shares(
        self,
        line,
        selected_project_ids,
        analytic_to_project,
        has_sale_link,
        has_purchase_link,
    ):
        project_shares = defaultdict(float)

        # Primary source: analytic distribution in accounting entries.
        if "analytic_distribution" in line._fields and line.analytic_distribution:
            for key, percent in line.analytic_distribution.items():
                analytic_ids = [int(analytic_id) for analytic_id in key.split(",")]
                if not analytic_ids:
                    continue
                share = (float(percent or 0.0) / 100.0) / len(analytic_ids)
                for analytic_id in analytic_ids:
                    project_id = analytic_to_project.get(analytic_id)
                    if project_id and project_id in selected_project_ids:
                        project_shares[project_id] += share

        # Secondary source: explicit analytic account field if present.
        if (
            not project_shares
            and "analytic_account_id" in line._fields
            and line.analytic_account_id
        ):
            project_id = analytic_to_project.get(line.analytic_account_id.id)
            if project_id and project_id in selected_project_ids:
                project_shares[project_id] = 1.0

        # Fallback source: links from sale/purchase lines.
        if not project_shares and self.include_order_links_fallback:
            project_ids = set()
            if has_sale_link:
                project_ids.update(line.sale_line_ids.mapped("project_id").ids)
            if has_purchase_link and line.purchase_line_id.project_id:
                project_ids.add(line.purchase_line_id.project_id.id)
            project_ids = sorted(project_ids.intersection(selected_project_ids))
            if project_ids:
                share = 1.0 / len(project_ids)
                for project_id in project_ids:
                    project_shares[project_id] = share

        return dict(project_shares)

    def _prepare_report_data(self):
        self.ensure_one()
        projects = self._get_selected_projects()
        periods = self._get_periods()
        if not periods:
            return {"periods": [], "lines": [], "totals": {}}

        move_line_model = self.env["account.move.line"]
        has_sale_link = "sale_line_ids" in move_line_model._fields
        has_purchase_link = "purchase_line_id" in move_line_model._fields

        selected_project_ids = set(projects.ids)
        analytic_to_project = {
            project.analytic_account_id.id: project.id
            for project in projects
            if project.analytic_account_id
        }

        period_keys = [period["key"] for period in periods]
        income_move_types = {"out_invoice", "out_receipt", "out_refund"}
        expense_move_types = {"in_invoice", "in_receipt", "in_refund"}

        grouped = {
            project.id: {
                "project": project,
                "income": defaultdict(float),
                "expense": defaultdict(float),
            }
            for project in projects
        }

        domain = [
            ("parent_state", "=", "posted"),
            ("move_id.move_type", "in", sorted(income_move_types | expense_move_types)),
            ("display_type", "=", False),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
        ]

        for line in move_line_model.search(domain):
            period_key = fields.Date.to_date(line.date).strftime("%Y-%m")
            if period_key not in period_keys:
                continue
            project_shares = self._line_project_shares(
                line,
                selected_project_ids,
                analytic_to_project,
                has_sale_link,
                has_purchase_link,
            )
            if not project_shares:
                continue

            move_type = line.move_id.move_type
            if move_type in income_move_types:
                signed_amount = -line.balance
                bucket = "income"
            else:
                signed_amount = line.balance
                bucket = "expense"

            for project_id, share in project_shares.items():
                grouped[project_id][bucket][period_key] += signed_amount * share

        lines = []
        total_income = defaultdict(float)
        total_expense = defaultdict(float)

        for project in projects:
            data = grouped[project.id]
            line_vals = {
                "project": project,
                "income": {},
                "expense": {},
                "net": {},
                "accumulated": {},
            }
            running = 0.0
            for period in periods:
                key = period["key"]
                income = data["income"].get(key, 0.0)
                expense = data["expense"].get(key, 0.0)
                net = income - expense
                running += net
                line_vals["income"][key] = income
                line_vals["expense"][key] = expense
                line_vals["net"][key] = net
                line_vals["accumulated"][key] = running
                total_income[key] += income
                total_expense[key] += expense
            lines.append(line_vals)

        totals = {"income": {}, "expense": {}, "net": {}, "accumulated": {}}
        running_total = 0.0
        for period in periods:
            key = period["key"]
            income = total_income.get(key, 0.0)
            expense = total_expense.get(key, 0.0)
            net = income - expense
            running_total += net
            totals["income"][key] = income
            totals["expense"][key] = expense
            totals["net"][key] = net
            totals["accumulated"][key] = running_total

        return {
            "periods": periods,
            "lines": lines,
            "totals": totals,
            "currency": self.company_id.currency_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "company": self.company_id,
        }
