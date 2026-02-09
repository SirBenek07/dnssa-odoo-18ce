# Project Task Tools (Odoo 18)

Asigna **herramientas** y **vehiculos** a tareas de proyecto con control de **reserva/uso/devolucion**.

## Instalacion
1. Colocar el modulo dentro de tu `addons` y actualizar la lista de apps.
2. Instalar dependencias: `project`, `stock`, `fleet`.
3. Instalar este modulo.

## Uso
- En la tarea, pestana **Recursos**:
  - Elegir tipo de recurso: **Herramienta** o **Vehiculo**.
  - Definir rango de fechas para reserva/uso.
  - Para herramientas, **Entregar** y **Devolver** crean pickings internos.
  - Para vehiculos, **Entregar** y **Devolver** actualizan el estado de la reserva.

- En Proyecto -> **Reporte rapido de recursos**:
  - Vista lista con columnas de recurso, fechas, tarea/evento y estado.
  - Resaltado en rojo cuando la reserva esta dentro del rango actual.
  - Filtro predeterminado para ocultar reservas vencidas (`date_to < hoy`).
  - Vista alternativa de calendario para planificar uso y reservas.

> Este modulo sigue conviviendo con OCA `project_task_stock` (consumibles).
