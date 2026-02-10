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
    analytic_account_ids = fields.Many2many(
        comodel_name="account.analytic.account",
        string="Cuentas analiticas",
        domain="[('company_id', 'in', [False, company_id])]",
        help=(
            "Filtro opcional por cuentas analiticas. "
            "Incluye cuentas hijas (jerarquia) al buscar proyectos."
        ),
    )
    include_order_links_fallback = fields.Boolean(
        string="Usar compra/venta como respaldo",
        default=True,
        help="Si una linea analitica no tiene proyecto directo, se intentara asociar por vinculos de compra/venta.",
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
        elif active_model == "account.analytic.account" and active_ids:
            vals["analytic_account_ids"] = [(6, 0, active_ids)]
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
        projects = self.env["project.project"].search(
            [("company_id", "in", [False, self.company_id.id])],
            order="name",
        )
        if self.project_ids:
            projects = self.project_ids

        if not self.analytic_account_ids:
            return projects

        project_analytic_field = next(
            (
                field_name
                for field_name in ("account_id", "analytic_account_id")
                if field_name in projects._fields
            ),
            False,
        )
        if not project_analytic_field:
            return self.env["project.project"]

        allowed_analytic_ids = set(
            self.env["account.analytic.account"]
            .search([("id", "child_of", self.analytic_account_ids.ids)])
            .ids
        )
        projects = projects.filtered(
            lambda project: project[project_analytic_field]
            and project[project_analytic_field].id in allowed_analytic_ids
        )
        return projects.sorted("name")

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

    def _analytic_line_project_ids(self, line, selected_project_ids, analytic_to_project):
        project_ids = set()

        # Primary source: project directly stored in analytic line.
        if "project_id" in line._fields and line.project_id:
            project_ids.add(line.project_id.id)

        # Secondary source: map analytic account to project.
        if not project_ids and "account_id" in line._fields and line.account_id:
            mapped_project_id = analytic_to_project.get(line.account_id.id)
            if mapped_project_id:
                project_ids.add(mapped_project_id)

        # Optional fallback via linked accounting line purchase/sale references.
        move_line = getattr(line, "move_line_id", False)
        if (
            not project_ids
            and self.include_order_links_fallback
            and move_line
            and move_line.exists()
        ):
            if "sale_line_ids" in move_line._fields:
                project_ids.update(move_line.sale_line_ids.mapped("project_id").ids)
            if (
                "purchase_line_id" in move_line._fields
                and move_line.purchase_line_id
                and move_line.purchase_line_id.project_id
            ):
                project_ids.add(move_line.purchase_line_id.project_id.id)

        return sorted(project_ids.intersection(selected_project_ids))

    def _build_analytic_to_project_map(self, projects, project_analytic_field):
        """Map analytic accounts to selected projects.

        Supports analytic hierarchies (account_analytic_parent) by resolving
        descendants to the closest selected project analytic ancestor.
        """
        analytic_to_project = {}
        if not project_analytic_field:
            return analytic_to_project

        root_to_project = {}
        for project in projects:
            analytic_account = project[project_analytic_field]
            if analytic_account:
                root_to_project[analytic_account.id] = project.id

        if not root_to_project:
            return analytic_to_project

        analytic_model = self.env["account.analytic.account"].with_context(active_test=False)
        descendants = analytic_model.search([("id", "child_of", list(root_to_project))])
        parent_by_id = {account.id: account.parent_id.id for account in descendants}

        for account in descendants:
            current_id = account.id
            depth = 0
            best_root_id = False
            best_depth = -1
            while current_id:
                if current_id in root_to_project and depth > best_depth:
                    best_root_id = current_id
                    best_depth = depth
                current_id = parent_by_id.get(current_id)
                depth += 1
            if best_root_id:
                analytic_to_project[account.id] = root_to_project[best_root_id]

        return analytic_to_project

    def _is_analytic_ancestor_of(self, ancestor_account, descendant_account):
        if not ancestor_account or not descendant_account:
            return False
        if ancestor_account == descendant_account:
            return False
        if "parent_path" in descendant_account._fields and descendant_account.parent_path:
            parent_ids = [
                int(item)
                for item in descendant_account.parent_path.split("/")
                if item and item.isdigit()
            ]
            return ancestor_account.id in parent_ids
        current = descendant_account.parent_id
        while current:
            if current.id == ancestor_account.id:
                return True
            current = current.parent_id
        return False

    def _analytic_depth(self, account):
        if not account:
            return 0
        if "parent_path" in account._fields and account.parent_path:
            return len([item for item in account.parent_path.split("/") if item])
        depth = 0
        current = account
        while current:
            depth += 1
            current = current.parent_id
        return depth

    def _pick_selected_parent_for_label(self, line_analytic, project_analytic):
        """Return the best selected analytic account for grouped label.

        If the user filtered by analytic accounts and one selected account is an
        ancestor (or the same account) of both the project analytic and line analytic,
        use it as label root (e.g. "Cuenta Madre / Proyecto").
        """
        selected = self.analytic_account_ids
        if not selected or not project_analytic:
            return False

        candidates = selected.filtered(
            lambda account: (
                account == project_analytic
                or self._is_analytic_ancestor_of(account, project_analytic)
            )
            and (
                not line_analytic
                or account == line_analytic
                or self._is_analytic_ancestor_of(account, line_analytic)
            )
        )
        if not candidates:
            return False
        return max(candidates, key=lambda account: self._analytic_depth(account))

    def _build_detail_descriptor(self, line, project, main_task, project_analytic_field):
        line_analytic = (
            line.account_id
            if "account_id" in line._fields and line.account_id
            else self.env["account.analytic.account"]
        )
        project_analytic = (
            project[project_analytic_field]
            if project_analytic_field and project_analytic_field in project._fields
            else self.env["account.analytic.account"]
        )

        selected_parent = self._pick_selected_parent_for_label(
            line_analytic=line_analytic,
            project_analytic=project_analytic,
        )
        if selected_parent:
            return {
                "key": (project.id, "selected_analytic", selected_parent.id),
                "label": f"{selected_parent.display_name} / {project.display_name}",
                "task": False,
            }

        if self._is_analytic_ancestor_of(line_analytic, project_analytic):
            return {
                "key": (project.id, "analytic_parent", line_analytic.id),
                "label": f"{line_analytic.display_name} / {project.display_name}",
                "task": False,
            }

        return {
            "key": (project.id, "task", main_task.id if main_task else 0),
            "label": (
                f"{project.display_name} / {main_task.display_name}"
                if main_task
                else f"{project.display_name} / Sin tarea principal"
            ),
            "task": main_task,
        }

    def _get_direct_main_task_for_line(self, line):
        task = False
        # Stock consumptions created by project_task_stock store the task link
        # in account.analytic.line.stock_task_id.
        if "stock_task_id" in line._fields and line.stock_task_id:
            task = line.stock_task_id
        if "task_id" in line._fields and line.task_id:
            task = line.task_id
        move_line = getattr(line, "move_line_id", False)
        if not task and move_line and move_line.exists():
            expense = (
                move_line.expense_id
                if "expense_id" in move_line._fields
                else self.env["hr.expense"]
            )
            if expense and "parent_task_id" in expense._fields and expense.parent_task_id:
                task = expense.parent_task_id
            if (
                not task
                and "purchase_line_id" in move_line._fields
                and move_line.purchase_line_id
                and move_line.purchase_line_id.task_id
            ):
                task = move_line.purchase_line_id.task_id
            if (
                not task
                and "sale_line_ids" in move_line._fields
                and move_line.sale_line_ids
            ):
                task = move_line.sale_line_ids.filtered("task_id")[:1].task_id
        if not task:
            return False
        return task.parent_id or task

    def _get_main_task_for_line(
        self,
        line,
        project_id,
        sibling_task_cache,
        selected_project_ids,
        analytic_to_project,
        signed_amount,
    ):
        direct_task = self._get_direct_main_task_for_line(line)
        if direct_task:
            return direct_task

        move_line = getattr(line, "move_line_id", False)
        if not move_line or not move_line.exists() or not move_line.move_id:
            return False

        is_positive = signed_amount >= 0
        cache_key = (move_line.move_id.id, project_id, is_positive)
        if cache_key in sibling_task_cache:
            return sibling_task_cache[cache_key]

        analytic_line_model = self.env["account.analytic.line"]
        sibling_domain = [
            ("move_line_id.move_id", "=", move_line.move_id.id),
            ("id", "!=", line.id),
            ("amount", ">=", 0) if is_positive else ("amount", "<", 0),
        ]

        sibling_lines = analytic_line_model.search(sibling_domain, order="id")
        best_task = False
        best_amount = 0.0
        for sibling in sibling_lines:
            sibling_project_ids = self._analytic_line_project_ids(
                sibling, selected_project_ids, analytic_to_project
            )
            if project_id not in sibling_project_ids:
                continue
            sibling_task = self._get_direct_main_task_for_line(sibling)
            if not sibling_task:
                continue
            amount = abs(sibling.amount or 0.0)
            if amount >= best_amount:
                best_task = sibling_task
                best_amount = amount

        sibling_task_cache[cache_key] = best_task
        return best_task

    def _prepare_report_data(self):
        self.ensure_one()
        projects = self._get_selected_projects()
        periods = self._get_periods()
        if not periods:
            return {"periods": [], "lines": [], "totals": {}}

        analytic_line_model = self.env["account.analytic.line"]
        project_model = self.env["project.project"]

        selected_project_ids = set(projects.ids)
        project_analytic_field = next(
            (
                field_name
                for field_name in ("account_id", "analytic_account_id")
                if field_name in project_model._fields
            ),
            False,
        )
        analytic_to_project = self._build_analytic_to_project_map(
            projects, project_analytic_field
        )

        period_keys = [period["key"] for period in periods]

        grouped = {
            project.id: {
                "project": project,
                "income": defaultdict(float),
                "expense": defaultdict(float),
            }
            for project in projects
        }
        income_detail_by_task = {}
        expense_detail_by_task = {}

        analytic_domain = [
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("company_id", "=", self.company_id.id),
        ]

        sibling_task_cache = {}
        for line in analytic_line_model.search(analytic_domain):
            period_key = fields.Date.to_date(line.date).strftime("%Y-%m")
            if period_key not in period_keys:
                continue

            project_ids = self._analytic_line_project_ids(
                line, selected_project_ids, analytic_to_project
            )
            if not project_ids:
                continue

            signed_amount = line.amount or 0.0
            split_amount = signed_amount / len(project_ids)
            for project_id in project_ids:
                project = grouped[project_id]["project"]
                main_task = self._get_main_task_for_line(
                    line,
                    project_id,
                    sibling_task_cache,
                    selected_project_ids,
                    analytic_to_project,
                    split_amount,
                )
                detail_descriptor = self._build_detail_descriptor(
                    line=line,
                    project=project,
                    main_task=main_task,
                    project_analytic_field=project_analytic_field,
                )
                detail_key = detail_descriptor["key"]
                label = detail_descriptor["label"]
                detail_task = detail_descriptor["task"]
                if split_amount >= 0:
                    grouped[project_id]["income"][period_key] += split_amount
                    if detail_key not in income_detail_by_task:
                        income_detail_by_task[detail_key] = {
                            "project": project,
                            "task": detail_task,
                            "label": label,
                            "income": defaultdict(float),
                        }
                    income_detail_by_task[detail_key]["income"][period_key] += split_amount
                else:
                    expense_amount = abs(split_amount)
                    grouped[project_id]["expense"][period_key] += expense_amount
                    if detail_key not in expense_detail_by_task:
                        expense_detail_by_task[detail_key] = {
                            "project": project,
                            "task": detail_task,
                            "label": label,
                            "expense": defaultdict(float),
                        }
                    expense_detail_by_task[detail_key]["expense"][period_key] += expense_amount

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

        income_task_lines = []
        for detail in sorted(
            income_detail_by_task.values(),
            key=lambda item: (
                item["project"].display_name or "",
                item["task"].display_name if item["task"] else "",
            ),
        ):
            vals = {
                "label": detail["label"],
                "project": detail["project"],
                "task": detail["task"],
                "income": {},
                "total": 0.0,
            }
            for period in periods:
                amount = detail["income"].get(period["key"], 0.0)
                vals["income"][period["key"]] = amount
                vals["total"] += amount
            income_task_lines.append(vals)

        expense_task_lines = []
        for detail in sorted(
            expense_detail_by_task.values(),
            key=lambda item: (
                item["project"].display_name or "",
                item["task"].display_name if item["task"] else "",
            ),
        ):
            vals = {
                "label": detail["label"],
                "project": detail["project"],
                "task": detail["task"],
                "expense": {},
                "total": 0.0,
            }
            for period in periods:
                amount = detail["expense"].get(period["key"], 0.0)
                vals["expense"][period["key"]] = amount
                vals["total"] += amount
            expense_task_lines.append(vals)

        profit_task_lines = []
        for detail_key in set(income_detail_by_task) | set(expense_detail_by_task):
            income_detail = income_detail_by_task.get(detail_key)
            expense_detail = expense_detail_by_task.get(detail_key)
            detail = income_detail or expense_detail
            vals = {
                "label": detail["label"],
                "project": detail["project"],
                "task": detail["task"],
                "income": {},
                "expense": {},
                "profit": {},
                "total_profit": 0.0,
            }
            for period in periods:
                key = period["key"]
                income = (
                    income_detail["income"].get(key, 0.0) if income_detail else 0.0
                )
                expense = (
                    expense_detail["expense"].get(key, 0.0) if expense_detail else 0.0
                )
                profit = income - expense
                vals["income"][key] = income
                vals["expense"][key] = expense
                vals["profit"][key] = profit
                vals["total_profit"] += profit
            profit_task_lines.append(vals)

        profit_task_lines.sort(
            key=lambda item: (
                item["project"].display_name or "",
                -(item["total_profit"] or 0.0),
                item["task"].display_name if item["task"] else "",
            )
        )

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
            "income_task_lines": income_task_lines,
            "expense_task_lines": expense_task_lines,
            "profit_task_lines": profit_task_lines,
            "totals": totals,
            "currency": self.company_id.currency_id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "company": self.company_id,
        }
