{
    "name": "Project Task Template",
    "summary": "Generate project tasks from templates with area assignees",
    "version": "18.0.1.0.0",
    "category": "Project",
    "author": "Versiones",
    "website": "https://github.com/Versiones",
    "license": "AGPL-3",
    "depends": [
        "project_task_stage_dependency",
        "hr",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_views.xml",
        "views/project_task_views.xml",
        "wizard/project_task_template_generate_wizard_views.xml",
    ],
    "installable": True,
}
