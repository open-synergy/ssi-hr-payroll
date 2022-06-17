# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0-standalone.html).

from odoo import _, api, fields, models


class HrPayslipLine(models.Model):
    _name = "hr.payslip_line"

    _description = "Payslip Input"

    payslip_id = fields.Many2one(
        string="Payslip",
        comodel_name="hr.payslip",
        required=True,
        ondelete="cascade",
    )
    rule_id = fields.Many2one(
        string="Salary Rule",
        comodel_name="hr.salary_rule",
        required=True,
        ondelete="restrict",
    )
    category_id = fields.Many2one(
        string="Salary Rule Category", related="rule_id.category_id"
    )
    move_line_debit_id = fields.Many2one(
        string="Move Line Debit",
        comodel_name="account.move.line",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    move_line_credit_id = fields.Many2one(
        string="Move Line Credit",
        comodel_name="account.move.line",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )
    rate = fields.Float(
        string="Rate (%)",
        default=100.0,
    )
    amount = fields.Float(
        string="Amount",
    )
    quantity = fields.Float(
        string="Quantity",
    )

    @api.depends(
        "quantity",
        "amount",
        "rate",
    )
    def _compute_total(self):
        for document in self:
            quantity = float(document.quantity)
            amount = document.amount
            rate = document.rate
            document.total = (quantity * amount) * (rate / 100)

    total = fields.Float(
        string="Total",
        compute="_compute_total",
    )

    def _get_partner_id(self):
        self.ensure_one()
        partner_id = False
        contribution = self.rule_id.contribution_id
        if contribution:
            partner_id = contribution.partner_id.id
        else:
            partner_id = self.payslip_id.employee_id.address_home_id.id
        return partner_id

    def _prepare_aml_debit_data(self, move):
        self.ensure_one()
        payslip = self.payslip_id
        debit_account_id = self.rule_id.debit_account_id.id
        amount = self.amount
        name = _("%s for %s") % (self.rule_id.name, payslip.name)

        data = {
            "move_id": move.id,
            "name": name,
            "partner_id": self._get_partner_id(),
            "account_id": debit_account_id,
            "journal_id": payslip.journal_id.id,
            "debit": amount > 0.0 and amount or 0.0,
            "credit": amount < 0.0 and -amount or 0.0,
        }
        return data

    def _prepare_aml_credit_data(self, move):
        self.ensure_one()
        payslip = self.payslip_id
        credit_account_id = self.rule_id.credit_account_id.id
        amount = self.amount
        name = _("%s for %s") % (self.rule_id.name, payslip.name)

        data = {
            "move_id": move.id,
            "name": name,
            "partner_id": self._get_partner_id(),
            "account_id": credit_account_id,
            "journal_id": payslip.journal_id.id,
            "debit": amount < 0.0 and -amount or 0.0,
            "credit": amount > 0.0 and amount or 0.0,
        }
        return data

    def create_move_line(self, move):
        obj_account_move_line = self.env["account.move.line"].with_context(
            check_move_validity=False
        )
        debit_sum = 0.0
        credit_sum = 0.0

        for document in self.sudo():
            if document.rule_id.debit_account_id:
                debit_data = document._prepare_aml_debit_data(move)
                debit_sum += debit_data["debit"] - debit_data["credit"]
                move_line = obj_account_move_line.create(debit_data)
                document.move_line_debit_id = move_line.id
            if document.rule_id.credit_account_id:
                credit_data = document._prepare_aml_credit_data(move)
                credit_sum += credit_data["credit"] - credit_data["debit"]
                move_line = obj_account_move_line.create(credit_data)
                document.move_line_credit_id = move_line.id

        return debit_sum, credit_sum
