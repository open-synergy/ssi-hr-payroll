# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0-standalone.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BrowsableObject(object):
    def __init__(self, employee_id, vals_dict, env):
        self.employee_id = employee_id
        self.dict = vals_dict
        self.env = env

    def __getattr__(self, attr):
        return attr in self.dict and self.dict.__getitem__(attr) or 0.0


class Payslips(BrowsableObject):
    """a class that will be used into the python code, mainly for
    usability purposes"""

    def sum(self, code, from_date, to_date=None):
        if to_date is None:
            to_date = fields.Date.today()
        self.env.cr.execute(
            """SELECT sum(case when hp.credit_note = False then
            (pl.total) else (-pl.total) end)
                    FROM hr_payslip as hp, hr_payslip_line as pl
                    WHERE hp.employee_id = %s AND hp.state = 'done'
                    AND hp.date_from >= %s AND hp.date_to <= %s AND
                     hp.id = pl.slip_id AND pl.code = %s""",
            (self.employee_id, from_date, to_date, code),
        )
        res = self.env.cr.fetchone()
        return res and res[0] or 0.0


class InputLine(BrowsableObject):
    """a class that will be used into the python code, mainly for
    usability purposes"""

    def sum(self, code, from_date, to_date=None):
        if to_date is None:
            to_date = fields.Date.today()
        self.env.cr.execute(
            """
            SELECT sum(amount) as sum
            FROM hr_payslip as hp, hr_payslip_input as pi
            WHERE hp.employee_id = %s AND hp.state = 'done'
            AND hp.date_from >= %s AND hp.date_to <= %s
            AND hp.id = pi.payslip_id AND pi.code = %s""",
            (self.employee_id, from_date, to_date, code),
        )
        return self.env.cr.fetchone()[0] or 0.0


class HrPayslip(models.Model):
    _name = "hr.payslip"
    _inherit = [
        "mixin.transaction_confirm",
        "mixin.transaction_done",
        "mixin.transaction_cancel",
        "mixin.employee_document",
        "mixin.date_duration",
    ]
    # Multiple Approval Attribute
    _approval_from_state = "draft"
    _approval_to_state = "done"
    _approval_state = "confirm"
    _after_approved_method = "action_done"

    # Attributes related to add element on view automatically
    _automatically_insert_view_element = True
    _automatically_insert_done_button = False
    _automatically_insert_done_policy_fields = False

    # Attributes related to add element on form view automatically
    _automatically_insert_multiple_approval_page = True
    _statusbar_visible_label = "draft,confirm,done"
    _policy_field_order = [
        "confirm_ok",
        "approve_ok",
        "reject_ok",
        "restart_approval_ok",
        "cancel_ok",
        "restart_ok",
        "manual_number_ok",
    ]
    _header_button_order = [
        "action_confirm",
        "action_approve_approval",
        "action_reject_approval",
        "%(ssi_transaction_cancel_mixin.base_select_cancel_reason_action)d",
        "action_restart",
    ]

    # Attributes related to add element on search view automatically
    _state_filter_order = [
        "dom_draft",
        "dom_confirm",
        "dom_reject",
        "dom_done",
        "dom_cancel",
    ]

    # Mixin duration attribute
    _date_start_readonly = True
    _date_end_readonly = True
    _date_start_states_list = ["draft"]
    _date_start_states_readonly = ["draft"]
    _date_end_states_list = ["draft"]
    _date_end_states_readonly = ["draft"]

    # Sequence attribute
    _create_sequence_state = "done"

    type_id = fields.Many2one(
        string="Type",
        comodel_name="hr.payslip_type",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    structure_id = fields.Many2one(
        string="Salary Structure",
        comodel_name="hr.salary_structure",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    line_ids = fields.One2many(
        string="Payslip Lines",
        comodel_name="hr.payslip_line",
        inverse_name="payslip_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    input_line_ids = fields.One2many(
        string="Input Types",
        comodel_name="hr.payslip_input",
        inverse_name="payslip_id",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    date = fields.Date(
        string="Date",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    journal_id = fields.Many2one(
        string="Journal",
        comodel_name="account.journal",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    move_id = fields.Many2one(
        string="Move",
        comodel_name="account.move",
        readonly=True,
        copy=False,
        ondelete="restrict",
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
    state = fields.Selection(
        string="State",
        selection=[
            ("draft", "Draft"),
            ("confirm", "Waiting for Approval"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
            ("reject", "Rejected"),
        ],
        default="draft",
        copy=False,
    )

    @api.model
    def _get_policy_field(self):
        res = super(HrPayslip, self)._get_policy_field()
        policy_field = [
            "confirm_ok",
            "approve_ok",
            "done_ok",
            "cancel_ok",
            "reject_ok",
            "restart_ok",
            "restart_approval_ok",
            "manual_number_ok",
        ]
        res += policy_field
        return res

    def _prepare_payslip_line_data(self):
        self.ensure_one()
        lines = [(0, 0, line) for line in self._get_payslip_lines(self.id)]
        return {"line_ids": lines}

    def _prepare_account_move_data(self):
        self.ensure_one()
        name = _("Payslip of %s") % (self.employee_id.name)
        data = {
            "narration": name,
            "ref": self.name,
            "journal_id": self.journal_id.id,
            "date": self.date or self.date_to,
        }
        return data

    def _prepare_adjustment_aml_data(
        self, currency, credit_sum, debit_sum, move_id, type_data
    ):
        self.ensure_one()
        journal_acc_id = self.journal_id.default_account_id.id
        if not journal_acc_id:
            msgError = _(
                "The Expense Journal %s has not properly "
                "configured the Credit or Debit Account!"
            )
            raise UserError(msgError % (self.journal_id.name))

        data = {
            "move_id": move_id.id,
            "name": _("Adjustment Entry"),
            "partner_id": False,
            "account_id": journal_acc_id,
            "journal_id": self.journal_id.id,
            "date": self.date,
        }
        if type_data == "debit":
            data["debit"] = currency.round(credit_sum - debit_sum)
            data["credit"] = 0.0
        else:
            data["credit"] = currency.round(debit_sum - credit_sum)
            data["debit"] = 0.0
        return data

    def _sum_salary_rule_category(self, localdict, category, amount):
        self.ensure_one()
        if category.parent_id:
            localdict = self._sum_salary_rule_category(
                localdict, category.parent_id, amount
            )

        if category.code in localdict["categories"].dict:
            localdict["categories"].dict[category.code] += amount
        else:
            localdict["categories"].dict[category.code] = amount

        return localdict

    @api.model
    def _get_payslip_lines(self, payslip_id):
        self.ensure_one()
        result_dict = {}
        rules_dict = {}
        inputs_dict = {}
        blacklist = []

        obj_hr_payslip = self.env["hr.payslip"]
        obj_hr_salary_struc = self.env["hr.salary_structure"]
        obj_hr_salary_rule = self.env["hr.salary_rule"]

        employee = self.employee_id
        structure_id = self.structure_id.id

        for input_line in self.input_line_ids:
            inputs_dict[input_line.input_type_id.code] = input_line

        payslip = obj_hr_payslip.browse(payslip_id)

        categories = BrowsableObject(payslip.employee_id.id, {}, self.env)
        inputs = InputLine(payslip.employee_id.id, inputs_dict, self.env)
        payslips = Payslips(payslip.employee_id.id, self, self.env)
        rules = BrowsableObject(payslip.employee_id.id, rules_dict, self.env)

        baselocaldict = {
            "categories": categories,
            "rules": rules,
            "payslip": payslips,
            "inputs": inputs,
        }

        rule_ids = obj_hr_salary_struc.browse(structure_id).get_all_rules()

        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x: x[1])]
        sorted_rules = obj_hr_salary_rule.browse(sorted_rule_ids)

        localdict = dict(baselocaldict, employee=employee)
        for rule in sorted_rules:
            key = rule.code
            localdict["result"] = None
            localdict["result_qty"] = 1.0
            localdict["result_rate"] = 100
            if rule._evaluate_rule("condition", localdict) and rule.id not in blacklist:
                amount, qty, rate = rule._evaluate_rule("amount", localdict)
                previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                tot_rule = amount * qty * rate / 100.0
                localdict[rule.code] = tot_rule
                rules_dict[rule.code] = rule
                localdict = self._sum_salary_rule_category(
                    localdict, rule.category_id, tot_rule - previous_amount
                )
                result_dict[key] = {
                    "payslip_id": payslip_id,
                    "rule_id": rule.id,
                    "amount": amount,
                    "quantity": qty,
                    "rate": rate,
                }
            else:
                blacklist += [id for id, seq in rule._recursive_search_of_rules()]

        return list(result_dict.values())

    def action_compute_payslip(self):
        for document in self.sudo():
            document.line_ids.unlink()
            document.write(self._prepare_payslip_line_data())

    def action_done(self):
        _super = super(HrPayslip, self)
        res = _super.action_done()

        obj_account_move = self.env["account.move"]
        obj_account_move_line = self.env["account.move.line"]

        for document in self.sudo():
            currency = (
                document.company_id.currency_id
                or document.journal_id.company_id.currency_id
            )
            move = obj_account_move.create(document._prepare_account_move_data())
            document.move_id = move.id
            debit_sum, credit_sum = document.line_ids.create_move_line(move)

            if currency.compare_amounts(credit_sum, debit_sum) == -1:
                move_line = obj_account_move_line.create(
                    document._prepare_adjustment_aml_data(
                        currency, credit_sum, debit_sum, move, "credit"
                    )
                )
                document.move_line_credit_id = move_line.id
            elif currency.compare_amounts(debit_sum, credit_sum) == -1:
                move_line = obj_account_move_line.create(
                    document._prepare_adjustment_aml_data(
                        currency, credit_sum, debit_sum, move, "debit"
                    )
                )
                document.move_line_debit_id = move_line.id
        return res

    def action_cancel(self, cancel_reason=False):
        _super = super(HrPayslip, self)
        res = _super.action_cancel(cancel_reason)
        for document in self.sudo():
            moves = document.move_id
            if moves.state == "posted":
                msg_err = _(
                    "You cannot cancel a payslip which journal is already posted!"
                )
                raise UserError(msg_err)
            document.write(
                {
                    "move_line_debit_id": False,
                    "move_line_credit_id": False,
                    "move_id": False,
                }
            )
            for lines in document.line_ids:
                lines.write(
                    {
                        "move_line_debit_id": False,
                        "move_line_credit_id": False,
                    }
                )
            moves.with_context(force_delete=True).unlink()
        return res
