from odoo import SUPERUSER_ID, api


def _get_or_create_category(env, code, name):
    categ = env["hr.salary.rule.category"].search([("code", "=", code)], limit=1)
    if not categ:
        categ = env["hr.salary.rule.category"].create({"name": name, "code": code})
    return categ


def _get_or_create_register(env, name):
    register = env["hr.contribution.register"].search([("name", "=", name)], limit=1)
    if not register:
        register = env["hr.contribution.register"].create({"name": name})
    return register


def _get_or_create_rule(env, vals):
    rule = env["hr.salary.rule"].search([("code", "=", vals["code"])], limit=1)
    if not rule:
        rule = env["hr.salary.rule"].create(vals)
    return rule


def _get_or_create_structure(env, code, name, rule_ids):
    struct = env["hr.payroll.structure"].search([("code", "=", code)], limit=1)
    vals = {
        "name": name,
        "code": code,
        "py_is_template": True,
        "rule_ids": [(6, 0, rule_ids)],
    }
    if not struct:
        struct = env["hr.payroll.structure"].create(vals)
    else:
        struct.write(vals)
    return struct


def _run_post_init(env):
    categ_basic = _get_or_create_category(env, "BASIC", "Basico")
    categ_ded = _get_or_create_category(env, "DED", "Descuentos")
    categ_ips_emp = _get_or_create_category(env, "IPSEMP", "Aporte Empleado IPS")
    categ_comp = _get_or_create_category(env, "COMP", "Contribucion Patronal")
    categ_net = _get_or_create_category(env, "NET", "Neto")
    categ_agui = _get_or_create_category(env, "AGUI", "Aguinaldo")

    ips_register = _get_or_create_register(env, "IPS")

    fact_basic = _get_or_create_rule(
        env,
        {
            "name": "TPL Factura - Monto Base",
            "code": "TPL_FACT_BASIC",
            "sequence": 100,
            "category_id": categ_basic.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": "result = contract.wage",
        },
    )
    fact_net = _get_or_create_rule(
        env,
        {
            "name": "TPL Factura - Neto a Pagar",
            "code": "TPL_FACT_NET",
            "sequence": 900,
            "category_id": categ_net.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": "result = categories.BASIC - categories.DED",
        },
    )

    ips_basic = _get_or_create_rule(
        env,
        {
            "name": "TPL IPS - Basico (91%)",
            "code": "TPL_IPS_BASIC",
            "sequence": 100,
            "category_id": categ_basic.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": "result = contract.wage * 0.91",
        },
    )
    ips_employee = _get_or_create_rule(
        env,
        {
            "name": "TPL IPS - Aporte Empleado (9%)",
            "code": "TPL_IPS_EMP_9",
            "sequence": 200,
            "category_id": categ_ips_emp.id,
            "register_id": ips_register.id,
            "condition_select": "none",
            "amount_select": "percentage",
            "amount_percentage_base": "contract.wage",
            "amount_percentage": 9.0,
        },
    )
    absence_unpaid = _get_or_create_rule(
        env,
        {
            "name": "TPL Ausencia Injustificada (codigo AUS)",
            "code": "TPL_AUS_UNP",
            "sequence": 250,
            "category_id": categ_ded.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": (
                "dias_aus = abs(worked_days.AUS.number_of_days)\n"
                "result = (contract.wage / 30.0) * dias_aus"
            ),
        },
    )
    ips_employer = _get_or_create_rule(
        env,
        {
            "name": "TPL IPS - Aporte Patronal (16.5%)",
            "code": "TPL_IPS_PAT_165",
            "sequence": 300,
            "category_id": categ_comp.id,
            "register_id": ips_register.id,
            "condition_select": "none",
            "amount_select": "percentage",
            "amount_percentage_base": "contract.wage",
            "amount_percentage": 16.5,
        },
    )
    ips_net = _get_or_create_rule(
        env,
        {
            "name": "TPL IPS - Neto a Pagar",
            "code": "TPL_IPS_NET",
            "sequence": 900,
            "category_id": categ_net.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": "result = categories.BASIC - categories.DED",
        },
    )
    aguinaldo_prov = _get_or_create_rule(
        env,
        {
            "name": "TPL Aguinaldo - Provision Mensual",
            "code": "TPL_AGUINALDO_PROV",
            "sequence": 850,
            "category_id": categ_agui.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": "result = contract.wage / 12.0",
        },
    )
    aguinaldo = _get_or_create_rule(
        env,
        {
            "name": "TPL Aguinaldo - Pago (contra provision)",
            "code": "TPL_AGUINALDO_PAY",
            "sequence": 100,
            "category_id": categ_agui.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": "result = contract.wage / 12.0",
        },
    )
    aguinaldo_net = _get_or_create_rule(
        env,
        {
            "name": "TPL Aguinaldo - Neto",
            "code": "TPL_AGUINALDO_NET",
            "sequence": 900,
            "category_id": categ_net.id,
            "condition_select": "none",
            "amount_select": "code",
            "amount_python_compute": "result = categories.AGUI - categories.DED",
        },
    )

    _get_or_create_structure(
        env,
        "PY_TPL_FACT",
        "Plantilla PY - Factura",
        [fact_basic.id, absence_unpaid.id, aguinaldo_prov.id, fact_net.id],
    )
    _get_or_create_structure(
        env,
        "PY_TPL_IPS",
        "Plantilla PY - Dependiente IPS",
        [ips_basic.id, ips_employee.id, absence_unpaid.id, ips_employer.id, aguinaldo_prov.id, ips_net.id],
    )
    _get_or_create_structure(
        env,
        "PY_TPL_AGUINALDO",
        "Plantilla PY - Pago Aguinaldo (contra provision)",
        [aguinaldo.id, aguinaldo_net.id],
    )


def post_init_hook(*args):
    """Support both hook signatures used by different Odoo loading flows.

    - post_init_hook(env)
    - post_init_hook(cr, registry)
    """
    if len(args) == 1:
        env = args[0]
    elif len(args) == 2:
        cr, _registry = args
        env = api.Environment(cr, SUPERUSER_ID, {})
    else:
        raise TypeError("post_init_hook() expected env or (cr, registry)")
    _run_post_init(env)
