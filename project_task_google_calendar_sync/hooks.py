# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["project.task"].search([])._sync_task_calendar_events()
