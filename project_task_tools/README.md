# Project Task Tools (Odoo 18)

Asigna **herramientas/equipos no consumibles** a tareas de proyecto con **préstamo/retorno** mediante **movimientos internos**.

## Instalación
1. Colocar el módulo dentro de tu `addons` y actualizar la lista de apps.
2. Instalar dependencias: `project`, `stock` (vienen en Odoo CE).
3. Instalar este módulo.

## Uso
- En la tarea, pestaña **Herramientas**:
  - Agregar líneas (producto, cantidad, opcional serie/lote).
  - Definir **Desde** (ubicación de herramientas) y **Hacia** (ubicación del proyecto/tarea).
  - **Entregar**: crea un picking interno y valida.
  - **Devolver**: crea el retorno (interno) y valida.

> Diseñado para convivir con OCA `project_task_stock` (consumibles).