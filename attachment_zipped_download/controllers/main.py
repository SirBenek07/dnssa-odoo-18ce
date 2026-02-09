# Copyright 2019 César Fernández Domínguez <cesfernandez@outlook.com>
# Copyright 2022 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import _, http
from odoo.http import request


class AttachmentZippedDownloadController(http.Controller):
    @http.route("/web/attachment/download_zip", type="http", auth="user")
    def download_zip(
        self,
        ids=None,
        debug=0,
        zip_name=None,
        selected_task_ids=None,
        group_by_selected_task=False,
    ):
        ids = [] if not ids else ids
        if len(ids) == 0:
            return
        list_ids = map(int, ids.split(","))
        context = dict(request.env.context)
        if selected_task_ids:
            context["zip_selected_task_ids"] = list(
                map(int, str(selected_task_ids).split(","))
            )
        context["zip_group_by_selected_task"] = str(group_by_selected_task).lower() in (
            "1",
            "true",
            "yes",
        )
        out_file = (
            request.env["ir.attachment"]
            .with_context(context)
            .browse(list_ids)
            ._create_temp_zip()
        )
        download_name = zip_name or _("attachments.zip")
        if not str(download_name).lower().endswith(".zip"):
            download_name = f"{download_name}.zip"
        stream = http.Stream(
            type="data",
            data=out_file.getvalue(),
            mimetype="application/zip",
            as_attachment=True,
            download_name=download_name,
        )
        return stream.get_response()
