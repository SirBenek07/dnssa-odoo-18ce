{
  "name": "Project Task Tools",
  "version": "18.0.1.0.0",
  "summary": "Asignación de herramientas (no consumibles) a tareas con préstamo/retorno mediante movimientos internos.",
  "author": "Federico Fernández",
  "website": "https://example.com",
  "license": "AGPL-3",
  "depends": ["project", "stock", "fleet"],
  "data": [
    "security/ir.model.access.csv",
    "views/project_task_type_views.xml",
    "views/product_template_views.xml",
    "views/project_task_views.xml",
    "views/project_task_resource_report_views.xml",
  ],
  "application": False,
  "installable": True
}
