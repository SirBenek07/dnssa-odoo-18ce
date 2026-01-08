===============================
Project Task Calendar Duration
===============================

Este módulo agrega la noción de fecha de inicio para cada tarea del proyecto y
ajusta la vista calendario para mostrar la tarea en todos los días que trans-
curre hasta que finaliza.

Características clave
=====================

* Utiliza los campos de fechas planificadas del módulo *project_timeline* para
  capturar la fecha de inicio.
* Calcula dinámicamente la fecha de finalización a mostrar en calendario. Las
  tareas abiertas se dibujan hasta el día actual y las completadas hasta su
  fecha real de cierre.
* Sustituye la fecha límite por el rango completo en la vista calendario,
  consiguiendo que cada tarea sea visible durante toda su duración.

Uso
====

1. En una tarea, establece la "Fecha planificada" (campo incorporado por
   ``project_timeline``).
2. Abre cualquier acción de tareas en vista calendario: comprobarás que cada
   tarea aparece desde la fecha indicada y se mantiene día a día hasta que la
   marques como completada.
