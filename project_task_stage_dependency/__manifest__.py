{
    "name": "Dependencias de Etapas en Tareas de Proyecto",
    "summary": "Controla cambios de etapa con prerequisitos entre tareas y etapa obligatoria de cierre",
    "version": "18.0.1.0.0",
    "category": "Project",
    "author": "Versiones",
    "website": "https://github.com/Versiones",
    "license": "AGPL-3",
    "depends": ["project"],
    "data": [
        "security/ir.model.access.csv",
        "views/project_task_views.xml",
        "views/project_task_dependency_close_warn_wizard_views.xml",
    ],
    "installable": True,
}
