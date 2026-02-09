====================================
Dependencias de Etapas en Tareas
====================================

Este modulo introduce reglas de dependencia entre tareas y etapas dentro de un proyecto.

Caracteristicas
===============

* Define en cada tarea que otras tareas conviene cerrar antes de cambiar de
  etapa.
* Establece una etapa obligatoria para dar por finalizada cada tarea, evitando
  cierres fuera de proceso.
* Muestra advertencias al cambiar de etapa si existen tareas bloqueantes
  pendientes, sin impedir el cambio.

Uso
===

1. Abre una tarea y, en la pestana *Dependencias*, selecciona las tareas que
   deben finalizar antes de poder moverla de etapa.
2. Usa el campo "Etapa obligatoria de cierre" para indicar la unica etapa en la
   que la tarea puede marcarse como completada.
3. A partir de ahi, al intentar mover la tarea Odoo mostrara una advertencia si
   existen tareas bloqueantes abiertas, y solo permitira completar la tarea en
   la etapa definida.
