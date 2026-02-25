import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    py_is_template = fields.Boolean(
        string="Plantilla PY",
        default=False,
        help="Marca estructuras base de plantilla para Paraguay.",
    )
    py_clone_prefix = fields.Char(
        string="Prefijo clonacion",
        help="Prefijo para generar codigos al clonar reglas plantilla (ej: IPS_ADM, FACT_COM).",
    )

    def _py_sanitize_code_token(self, value):
        token = re.sub(r"[^A-Z0-9_]+", "_", (value or "").upper()).strip("_")
        return token or "RULE"

    def _py_clean_clone_prefix(self, value):
        token = self._py_sanitize_code_token(value)
        parts = [p for p in token.split("_") if p]
        blocked = {"TPL", "COPIA", "COPY"}
        parts = [p for p in parts if p not in blocked]
        cleaned = "_".join(parts)
        return cleaned or "RULE"

    def _py_next_rule_code(self, candidate):
        code = candidate
        idx = 1
        Rule = self.env["hr.salary.rule"]
        while Rule.search_count([("code", "=", code)]):
            idx += 1
            code = f"{candidate}_{idx}"
        return code

    def action_py_clone_template_rules_replace(self):
        self.ensure_one()

        tpl_rules = self.rule_ids.filtered(lambda r: (r.code or "").startswith("TPL_"))
        if not tpl_rules:
            raise UserError(_("No hay reglas plantilla (TPL_*) para clonar en esta estructura."))

        prefix = self._py_clean_clone_prefix(self.py_clone_prefix or self.code or self.name)
        cloned_rules = self.env["hr.salary.rule"]
        replacement_map = {}

        # Clone top-level template rules used by this structure.
        for rule in tpl_rules.sorted(key=lambda r: (r.sequence, r.id)):
            base_code = self._py_sanitize_code_token((rule.code or "").removeprefix("TPL_"))
            new_code = self._py_next_rule_code(f"{prefix}_{base_code}")
            new_name = (rule.name or "").replace("TPL ", "", 1)
            new_rule = rule.copy(
                {
                    "code": new_code,
                    "name": new_name or rule.name,
                }
            )
            cloned_rules |= new_rule
            replacement_map[rule.id] = new_rule.id

        new_rule_ids = [
            replacement_map.get(rule.id, rule.id)
            for rule in self.rule_ids.sorted(key=lambda r: (r.sequence, r.id))
        ]
        self.write(
            {
                "rule_ids": [(6, 0, new_rule_ids)],
                "py_is_template": False,
                "py_clone_prefix": prefix,
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reglas clonadas"),
                "message": _(
                    "Se clonaron %(count)s reglas plantilla y se reemplazaron en la estructura."
                )
                % {"count": len(cloned_rules)},
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
