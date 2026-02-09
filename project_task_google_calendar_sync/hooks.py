# -*- coding: utf-8 -*-


def post_init_hook(env):
    env["project.task"].search([])._sync_task_calendar_events()
