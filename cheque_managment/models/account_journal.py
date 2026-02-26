from odoo import Command, api, fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    emit_check = fields.Boolean(
        string="Emite cheques",
        help="Habilita el metodo de pago saliente 'Cheque' y el control de cheques emitidos.",
    )
    cheque_count = fields.Integer(
        string="Cheques",
        compute="_compute_cheque_count",
    )

    def _get_dns_cheque_payment_method(self):
        return self.env.ref(
            "cheque_managment.account_payment_method_dns_cheque_out",
            raise_if_not_found=False,
        )

    @api.depends("type", "currency_id", "emit_check")
    def _compute_outbound_payment_method_line_ids(self):
        cheque_method = self._get_dns_cheque_payment_method()
        for journal in self:
            existing_lines_by_method = {}
            manual_line = self.env["account.payment.method.line"]
            for line in journal.outbound_payment_method_line_ids:
                # Preserve user configuration (name/account/sequence) when toggling the cheque option.
                existing_lines_by_method.setdefault(line.payment_method_id.id, line)
                if line.code == "manual" and not manual_line:
                    manual_line = line
            commands = [Command.clear()]
            if journal.type in ("bank", "cash", "credit"):
                default_methods = journal._default_outbound_payment_methods()
                if (
                    cheque_method
                    and journal.type == "bank"
                    and journal.emit_check
                    and cheque_method not in default_methods
                ):
                    default_methods |= cheque_method
                for payment_method in default_methods:
                    existing_line = existing_lines_by_method.get(payment_method.id)
                    fallback_payment_account_id = False
                    if (
                        payment_method.code == "dns_cheque"
                        and manual_line
                        and manual_line.payment_account_id
                    ):
                        fallback_payment_account_id = manual_line.payment_account_id.id
                    commands.append(
                        Command.create(
                            {
                                "name": (existing_line.name if existing_line else False)
                                or payment_method.name,
                                "payment_method_id": payment_method.id,
                                "sequence": (existing_line.sequence if existing_line else 10),
                                "payment_account_id": existing_line.payment_account_id.id
                                if existing_line and existing_line.payment_account_id
                                else fallback_payment_account_id,
                            }
                        )
                    )
            journal.outbound_payment_method_line_ids = commands

    @api.depends("emit_check")
    def _compute_cheque_count(self):
        counts = {}
        if self.ids:
            data = self.env["account.cheque"].read_group(
                [("journal_id", "in", self.ids)],
                ["journal_id"],
                ["journal_id"],
            )
            counts = {item["journal_id"][0]: item["journal_id_count"] for item in data}
        for journal in self:
            journal.cheque_count = counts.get(journal.id, 0)

    def action_open_cheques(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cheque_managment.action_account_cheque"
        )
        action["domain"] = [("journal_id", "=", self.id)]
        action_context = dict(self.env.context)
        action_context.update(
            {
                "default_journal_id": self.id,
                "search_default_active_cheques": 1,
            }
        )
        action["context"] = action_context
        return action
