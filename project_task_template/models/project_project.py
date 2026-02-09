from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval


class ProjectProject(models.Model):
    _inherit = "project.project"

    template_area_ids = fields.One2many(
        comodel_name="project.task.template.area",
        inverse_name="project_id",
        string="Areas",
    )

    def _compute_task_count_for_templates(self, count_field="task_count", additional_domain=None):
        domain = [
            ("project_id", "in", self.ids),
            ("display_in_project", "=", True),
            ("is_task_template", "=", False),
        ]
        if additional_domain:
            domain = expression.AND([domain, additional_domain])
        tasks_count_by_project = dict(
            self.env["project.task"]
            .with_context(active_test=any(project.active for project in self))
            ._read_group(domain, ["project_id"], ["__count"])
        )
        for project in self:
            project[count_field] = tasks_count_by_project.get(project, 0)

    def _compute_task_count(self):
        self._compute_task_count_for_templates(count_field="task_count")

    def _compute_open_task_count(self):
        self._compute_task_count_for_templates(
            count_field="open_task_count",
            additional_domain=[("state", "in", self.env["project.task"].OPEN_STATES)],
        )

    def _compute_closed_task_count(self):
        self._compute_task_count_for_templates(
            count_field="closed_task_count",
            additional_domain=[("state", "not in", self.env["project.task"].OPEN_STATES)],
        )

    def action_open_task_template_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generar tareas desde plantilla"),
            "res_model": "project.task.template.generate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_project_id": self.id,
            },
        }

    def action_view_tasks(self):
        self.ensure_one()
        action = super().action_view_tasks()
        base_domain = action.get("domain", [])
        if isinstance(base_domain, str):
            eval_context = {
                "active_id": self.id,
                "active_ids": self.ids,
                "uid": self.env.uid,
                "context": dict(self.env.context),
            }
            base_domain = safe_eval(base_domain, eval_context) if base_domain else []
        elif not isinstance(base_domain, (list, tuple)):
            base_domain = []
        action["domain"] = expression.AND(
            [
                list(base_domain),
                [("is_task_template", "=", False)],
            ]
        )
        return action

    def action_manage_templates(self):
        self.ensure_one()
        if not self.env.user.has_group("project.group_project_manager"):
            raise ValidationError(
                _("Solo usuarios con rol Proyecto / Administrador pueden gestionar plantillas.")
            )
        list_view = self.env.ref("project.view_task_tree2")
        return {
            "type": "ir.actions.act_window",
            "name": _("Gestionar Plantilla de Tareas"),
            "res_model": "project.task",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (False, "form")],
            "domain": [
                ("project_id", "=", self.id),
                ("is_task_template", "=", True),
                ("parent_id", "=", False),
            ],
            "context": {
                "default_project_id": self.id,
                "default_is_task_template": True,
                "from_template_management": True,
                "search_default_project_id": self.id,
            },
            "target": "current",
        }

    def generate_tasks_from_template(
        self,
        template_root_task,
        root_planned_date_start,
        root_planned_date_end,
        assignee_by_template_area,
        assignee_by_template_area_name=None,
        generated_task_name=None,
    ):
        self.ensure_one()
        if not root_planned_date_start or not root_planned_date_end:
            raise ValidationError(
                _("Para generar tareas se necesita asignar fecha de Inicio/Fin.")
            )

        if not template_root_task or not template_root_task.is_task_template:
            raise ValidationError(_("Debe seleccionar una plantilla valida."))
        if template_root_task.project_id != self:
            raise ValidationError(_("La plantilla seleccionada no pertenece a este proyecto."))

        template_tasks = self.env["project.task"].search(
            [
                ("id", "child_of", template_root_task.id),
                ("project_id", "=", self.id),
                ("is_task_template", "=", True),
            ],
            order="id",
        )
        template_tasks = self._order_template_tasks_parent_first(template_tasks)
        stage_by_name = {
            stage.name: stage for stage in self.type_ids
        }
        root_date_by_template_task = {}
        template_to_target_task = {}
        template_to_target_area = self._map_or_create_template_areas(template_tasks)

        for template_task in template_tasks:
            has_template_parent = template_task.parent_id.id in template_to_target_task
            parent_task = template_to_target_task.get(template_task.parent_id.id)
            is_selected_root = template_task.id == template_root_task.id
            mapped_completion_stage = self._map_stage(
                template_task.completion_stage_id, stage_by_name
            )
            template_area_ids = self._get_task_template_area_ids(template_task)
            mapped_template_area_ids = [
                template_to_target_area[area_id]
                for area_id in template_area_ids
                if area_id in template_to_target_area
            ]
            values = {
                "name": (
                    generated_task_name
                    if is_selected_root and generated_task_name
                    else template_task.name
                ),
                "project_id": self.id,
                "parent_id": parent_task.id if parent_task else False,
                "description": template_task.description,
                "priority": template_task.priority,
                "sequence": template_task.sequence,
                "company_id": self.company_id.id,
                "template_offset_days": template_task.template_offset_days,
                "template_offset_direction": template_task.template_offset_direction,
                "is_task_template": False,
                "completion_stage_enforcement": template_task.completion_stage_enforcement,
            }
            if mapped_template_area_ids:
                values["template_area_ids"] = [(6, 0, mapped_template_area_ids)]
                values["template_area_id"] = mapped_template_area_ids[0]
            if mapped_completion_stage:
                values["completion_stage_id"] = mapped_completion_stage.id
            mapped_stage = self._map_stage(template_task.stage_id, stage_by_name)
            if mapped_stage:
                values["stage_id"] = mapped_stage.id
            if template_task.tag_ids:
                values["tag_ids"] = [(6, 0, template_task.tag_ids.ids)]
            if has_template_parent:
                root_template_task = self._find_root_template_task(
                    template_task, set(template_to_target_task.keys())
                )
                root_dates = root_date_by_template_task.get(root_template_task.id)
                if not root_dates or not root_dates.get("start") or not root_dates.get(
                    "end"
                ):
                    raise ValidationError(
                        _("Para generar tareas se necesita asignar fecha de Inicio/Fin.")
                    )
                values.update(
                    self._compute_relative_planned_dates(
                        template_task=template_task,
                        root_date_start=root_dates["start"],
                        root_date_end=root_dates["end"],
                    )
                )
            else:
                values["planned_date_start"] = root_planned_date_start
                values["planned_date_end"] = root_planned_date_end

            assigned_user_ids = []
            for area in self._get_task_template_areas(template_task):
                assignee = assignee_by_template_area.get(area.id)
                if not assignee and assignee_by_template_area_name:
                    assignee = assignee_by_template_area_name.get(area.name)
                assigned_user = self._resolve_assignee_user(assignee) if assignee else False
                if assigned_user:
                    assigned_user_ids.append(assigned_user.id)
            if assigned_user_ids:
                values["user_ids"] = [(6, 0, list(dict.fromkeys(assigned_user_ids)))]

            new_task = self.env["project.task"].create(values)
            template_to_target_task[template_task.id] = new_task
            if has_template_parent:
                root_task = self._find_root_template_task(
                    template_task, set(template_to_target_task.keys())
                )
                root_dates = root_date_by_template_task[root_task.id]
            else:
                root_dates = {
                    "start": root_planned_date_start,
                    "end": root_planned_date_end,
                }
            root_date_by_template_task[template_task.id] = root_dates

        for template_task in template_tasks:
            if not template_task.dependency_task_ids:
                continue
            target_task = template_to_target_task[template_task.id]
            dependency_ids = [
                template_to_target_task[dependency_task.id].id
                for dependency_task in template_task.dependency_task_ids
                if dependency_task.id in template_to_target_task
            ]
            if dependency_ids:
                target_task.write({"dependency_task_ids": [(6, 0, dependency_ids)]})

    def _map_or_create_template_areas(self, template_tasks):
        target_areas_by_name = {area.name: area for area in self.template_area_ids}
        template_to_target_area = {}
        template_areas = self.env["project.task.template.area"]
        for template_task in template_tasks:
            template_areas |= self._get_task_template_areas(template_task)

        for template_area in template_areas:
            target_area = target_areas_by_name.get(template_area.name)
            if not target_area:
                target_area = self.env["project.task.template.area"].create(
                    {
                        "name": template_area.name,
                        "project_id": self.id,
                    }
                )
                target_areas_by_name[target_area.name] = target_area
            template_to_target_area[template_area.id] = target_area.id
        return template_to_target_area

    def _get_task_template_areas(self, task):
        areas = task.template_area_ids
        if not areas and task.template_area_id:
            areas = task.template_area_id
        return areas

    def _get_task_template_area_ids(self, task):
        return self._get_task_template_areas(task).ids

    def _find_root_template_task(self, template_task, allowed_template_ids=None):
        root_task = template_task
        while root_task.parent_id and (
            not allowed_template_ids or root_task.parent_id.id in allowed_template_ids
        ):
            root_task = root_task.parent_id
        return root_task

    def _order_template_tasks_parent_first(self, template_tasks):
        pending = {task.id: task for task in template_tasks}
        ordered_ids = []
        while pending:
            progressed_ids = []
            ordered_set = set(ordered_ids)
            for task_id, task in pending.items():
                parent = task.parent_id
                if not parent or parent.id not in pending or parent.id in ordered_set:
                    ordered_ids.append(task_id)
                    progressed_ids.append(task_id)
            if not progressed_ids:
                ordered_ids.extend(sorted(pending.keys()))
                break
            for task_id in progressed_ids:
                pending.pop(task_id, None)
        return self.env["project.task"].browse(ordered_ids)

    def _compute_relative_planned_dates(
        self, template_task, root_date_start, root_date_end
    ):
        if not template_task.template_offset_direction:
            return {
                "planned_date_start": template_task.planned_date_start,
                "planned_date_end": template_task.planned_date_end,
            }
        if template_task.template_offset_direction == "before":
            if not root_date_start:
                raise ValidationError(
                    _("Para generar tareas se necesita asignar fecha de Inicio/Fin.")
                )
            base_date = root_date_start
            days = -template_task.template_offset_days
        else:
            if not root_date_end:
                raise ValidationError(
                    _("Para generar tareas se necesita asignar fecha de Inicio/Fin.")
                )
            base_date = root_date_end
            days = template_task.template_offset_days

        planned_date = base_date + timedelta(days=days)
        return {
            "planned_date_start": planned_date,
            "planned_date_end": planned_date,
        }

    def _map_stage(self, template_stage, stage_by_name):
        if not template_stage:
            return False
        if template_stage in self.type_ids:
            return template_stage
        return stage_by_name.get(template_stage.name, False)

    def _resolve_assignee_user(self, assignee):
        if not assignee:
            return False
        if getattr(assignee, "_name", False) == "res.users":
            return assignee
        if getattr(assignee, "_name", False) == "hr.employee":
            user = assignee.user_id
            if user:
                return user
            resource_user = assignee.resource_id.user_id if assignee.resource_id else False
            if resource_user:
                return resource_user
            if assignee.work_contact_id:
                return self.env["res.users"].search(
                    [("partner_id", "=", assignee.work_contact_id.id)],
                    limit=1,
                )
        return False
