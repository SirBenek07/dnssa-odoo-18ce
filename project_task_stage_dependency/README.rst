====================================
Project Task Stage Dependency
====================================

Este módulo introduce reglas de dependencia bidireccionales entre las tareas y
las etapas de un proyecto.

Características
===============

* Define en cada tarea qué otras tareas deben cerrarse antes de permitir el
  cambio de etapa.
* Establece una etapa obligatoria para dar por finalizada cada tarea, evitando
  cierres fuera de proceso.
* Evita movimientos erróneos en el kanban y en cualquier acción que cambie la
  etapa de la tarea mediante mensajes de validación claros.

Uso
====

1. Abre una tarea y, en la nueva pestaña *Dependencias*, selecciona las tareas
   que deben finalizar antes de poder moverla de etapa.
2. Usa el campo "Required Completion Stage" para indicar la única etapa en la
   que la tarea puede marcarse como completada.
3. A partir de ahí, al intentar mover la tarea Odoo impedirá el cambio mientras
   existan tareas bloqueantes abiertas y sólo permitirá completar la tarea en la
   etapa definida.
