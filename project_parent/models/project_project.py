# Copyright 2019 Therp BV <https://therp.nl>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from collections import defaultdict

from odoo import api, fields, models


class Project(models.Model):
    _inherit = "project.project"
    _parent_store = True
    _parent_name = "parent_id"

    parent_id = fields.Many2one(
        comodel_name="project.project", string="Parent Project", index=True
    )
    child_ids = fields.One2many(
        comodel_name="project.project", inverse_name="parent_id", string="Sub-projects"
    )

    parent_path = fields.Char(index="btree")

    child_ids_count = fields.Integer(compute="_compute_child_ids_count", store=True)
    descendant_analytic_line_count = fields.Integer(
        string="Analytic Items",
        compute="_compute_descendant_analytic_line_count",
        compute_sudo=True,
        groups="analytic.group_analytic_accounting",
    )

    @api.depends("child_ids")
    def _compute_child_ids_count(self):
        for project in self:
            project.child_ids_count = len(project.child_ids)

    def action_open_child_project(self):
        self.ensure_one()
        ctx = self.env.context.copy()
        ctx.update(default_parent_id=self.id)
        domain = [("parent_id", "=", self.id)]
        return {
            "type": "ir.actions.act_window",
            "view_type": "form",
            "name": f"Children of {self.name}",
            "view_mode": "list,form,graph",
            "res_model": "project.project",
            "target": "current",
            "context": ctx,
            "domain": domain,
        }

    def _get_descendant_projects(self):
        """Return the hierarchy (self included) ignoring the active flag."""
        return self.env["project.project"].with_context(active_test=False).search(
            [("id", "child_of", self.ids)]
        )

    @staticmethod
    def _get_ancestor_ids_from_path(parent_path):
        if not parent_path:
            return []
        return [int(pid) for pid in parent_path.split("/") if pid]

    def _build_accounts_by_project(self):
        accounts_by_project = {project_id: set() for project_id in self.ids}
        descendant_projects = self._get_descendant_projects()
        for project in descendant_projects:
            if not project.account_id:
                continue
            for ancestor_id in self._get_ancestor_ids_from_path(project.parent_path):
                if ancestor_id in accounts_by_project:
                    accounts_by_project[ancestor_id].add(project.account_id.id)
        return accounts_by_project

    def _compute_descendant_analytic_line_count(self):
        if not self.env.user.has_group("analytic.group_analytic_accounting"):
            for project in self:
                project.descendant_analytic_line_count = 0
            return
        AnalyticLine = self.env["account.analytic.line"]
        if "account_id" not in AnalyticLine._fields or not self.ids:
            for project in self:
                project.descendant_analytic_line_count = 0
            return
        accounts_by_project = self._build_accounts_by_project()
        account_ids = {
            account_id for ids in accounts_by_project.values() for account_id in ids
        }
        count_by_account = defaultdict(int)
        if account_ids:
            data = AnalyticLine._read_group(
                [("account_id", "in", list(account_ids))],
                ["account_id"],
                ["__count"],
            )
            count_by_account = defaultdict(
                int, {account.id: count for account, count in data}
            )
        for project in self:
            project.descendant_analytic_line_count = sum(
                count_by_account[account_id]
                for account_id in accounts_by_project.get(project.id, set())
            )

    def action_view_descendant_analytic_items(self):
        self.ensure_one()
        AnalyticLine = self.env["account.analytic.line"]
        if "account_id" not in AnalyticLine._fields:
            return False
        descendant_accounts = self._get_descendant_projects().account_id
        domain_accounts = descendant_accounts.ids or [0]
        action = self.env.ref(
            "analytic.account_analytic_line_action_entries"
        ).read()[0]
        action["domain"] = [("account_id", "in", domain_accounts)]
        action["name"] = f"{self.name} - Analytic Items"
        return action
