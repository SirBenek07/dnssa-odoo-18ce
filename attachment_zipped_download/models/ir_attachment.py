# Copyright 2019 César Fernández Domínguez <cesfernandez@outlook.com>
# Copyright 2022 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
import zipfile
from io import BytesIO
from urllib.parse import urlencode

from odoo import models
from odoo.exceptions import UserError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def action_attachments_download(self, zip_name=False, **options):
        items = self.filtered(lambda x: x.type == "binary")
        if not items:
            raise UserError(
                self.env._("None attachment selected. Only binary attachments allowed.")
            )
        query = {"ids": ",".join(map(str, items.ids))}
        if zip_name:
            query["zip_name"] = str(zip_name)
        for key, value in options.items():
            if value in (False, None, ""):
                continue
            if isinstance(value, (list, tuple, set)):
                query[key] = ",".join(map(str, value))
            else:
                query[key] = str(value)
        url = f"/web/attachment/download_zip?{urlencode(query)}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "self",
        }

    def _create_temp_zip(self):
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for attachment in self:
                attachment.check("read")
                zip_file.writestr(
                    attachment._compute_zip_file_name(),
                    attachment.raw,
                )
            zip_buffer.seek(0)
            zip_file.close()
        return zip_buffer

    def _compute_zip_file_name(self):
        """Give a chance of easily changing the name of the file inside the ZIP."""
        self.ensure_one()
        selected_task_ids = self.env.context.get("zip_selected_task_ids") or []
        if (
            selected_task_ids
            and self.res_model == "project.task"
            and self.res_id
            and self.env.context.get("zip_group_by_selected_task")
        ):
            selected_set = set(selected_task_ids)
            task = self.env["project.task"].browse(self.res_id).exists()
            if task:
                chain = []
                current = task
                root = False
                while current:
                    chain.append(current)
                    if current.id in selected_set:
                        root = current
                        break
                    current = current.parent_id
                if root:
                    root_pos = next(
                        (idx for idx, item in enumerate(chain) if item.id == root.id),
                        0,
                    )
                    task_path = list(reversed(chain[:root_pos]))
                    parts = [root.name] + [item.name for item in task_path] + [self.name]
                    safe_parts = [
                        (part or "").replace("/", "-").replace("\\", "-").strip() or "unnamed"
                        for part in parts
                    ]
                    return "/".join(safe_parts)
        return self.name
