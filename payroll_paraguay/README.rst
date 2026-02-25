================
Payroll Paraguay
================

This module installs payroll presets and payment flows commonly used in Paraguay:

* Factura de proveedor: confirms payslip and creates vendor bill automatically.
* IPS dependiente: 9% employee contribution, 16.5% employer contribution.
* Payroll payments menu: centralized pending/paid payslip payments.
* Auto-created salary templates for Paraguay (Factura / IPS).
* Templates for unpaid absences and aguinaldo.

Installed records
=================

* Salary rule categories: BASIC, DED, COMP, NET
* Contribution registers: IPS
* Salary structures:
  * Paraguay - Factura (IVA Credito 10%)
  * Paraguay - Dependiente IPS
  * Plantilla PY - Factura
  * Plantilla PY - Dependiente IPS
  * Plantilla PY - Aguinaldo
* Contract fields:
  * Payment scheme (IPS or Vendor bill)
  * Vendor and product for vendor-bill scheme
  * Vendor defaults from employee contact when using vendor-bill scheme
  * Product defaults from company payroll settings when missing in contract
* Payslip fields/actions:
  * Payment state and amount to pay
  * Paid amount and due amount (supports partial payments)
  * Vendor bill link (if applicable)
  * Register payroll payment action

Post-install configuration
==========================

Configure accounting accounts on salary rules and configure a service product
with purchase taxes/accounts for vendor-bill scheme.

Use menu Payroll > Configuration > Plantillas PY to duplicate base templates
and create your own variants (e.g. ADM / COM).

Leaves / absences
=================

This setup uses ``hr_holidays`` (Time Off). Mark absences and vacations there.
For salary deduction by absences, map the leave to a work entry type with code
``AUS`` and use the template rule ``TPL_AUS_UNP``.
