# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0-standalone.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class HrSalaryRule(models.Model):
    _name = "hr.salary_rule"
    _inherit = [
        "mixin.master_data",
    ]
    _description = "Salary Rule"

    parent_id = fields.Many2one(
        string="Parent",
        comodel_name="hr.salary_rule",
        ondelete="restrict",
    )
    child_ids = fields.One2many(
        string="Child Salary Rule",
        comodel_name="hr.salary_rule",
        inverse_name="parent_id",
        copy=True,
    )
    category_id = fields.Many2one(
        string="Category",
        comodel_name="hr.salary_rule_category",
        required=True,
        ondelete="restrict",
    )
    debit_account_id = fields.Many2one(
        string="Debit Account",
        comodel_name="account.account",
        ondelete="restrict",
    )
    credit_account_id = fields.Many2one(
        string="Credit Account",
        comodel_name="account.account",
        ondelete="restrict",
    )
    contribution_id = fields.Many2one(
        string="Salary Contribution",
        comodel_name="hr.salary_contribution",
        ondelete="restrict",
    )
    condition_python = fields.Text(
        string="Python Condition",
        default="""
# Available variables:
#----------------------
# payslip: object containing the payslips
# employee: hr.employee object
# contract: hr.contract object
# rules: object containing the rules code (previously computed)
# categories: object containing the computed salary rule categories
#    (sum of amount of all rules belonging to that category).
# worked_days: object containing the computed worked days
# inputs: object containing the computed inputs

# Note: returned value have to be set in the variable 'result'

result = True""",
        help="Applied this rule for calculation if condition is true. You can "
        "specify condition like basic > 1000.",
    )
    amount_python = fields.Text(
        string="Amount Python",
        default="""
# Available variables:
#----------------------
# payslip: object containing the payslips
# employee: hr.employee object
# contract: hr.contract object
# rules: object containing the rules code (previously computed)
# categories: object containing the computed salary rule categories
#    (sum of amount of all rules belonging to that category).
# worked_days: object containing the computed worked days.
# inputs: object containing the computed inputs.

# Note: returned value have to be set in the variable 'result'

result = True""",
    )
    appear_on_payslip = fields.Boolean(
        string="Appear on Payslip",
    )
    input_type_ids = fields.Many2many(
        string="Input Types",
        comodel_name="hr.payslip_input_type",
        relation="rel_rule_2_input_type",
        column1="rule_id",
        column2="input_type_id",
    )
    sequence = fields.Integer(
        string="Sequence",
        required=True,
        index=True,
        default=5,
        help="Use to arrange calculation sequence",
    )

    @api.constrains("parent_id")
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_("You cannot create a recursive salary rule."))

    def _recursive_search_of_rules(self):
        """
        @return: returns a list of tuple (id, sequence) which are all the
                 children of the passed rule_ids
        """
        children_rules = []
        for rule in self.filtered(lambda rule: rule.child_ids):
            children_rules += rule.child_ids._recursive_search_of_rules()
        return [(rule.id, rule.sequence) for rule in self] + children_rules

    def _evaluate_rule(self, computation_method, localdict):
        self.ensure_one()
        if not computation_method:
            return False
        try:
            method_name = "_evaluate_rule_" + computation_method
            result = getattr(self, method_name)(localdict)
        except Exception as error:
            msg_err = _("Error evaluating a conditions.\n %s") % error
            raise UserError(msg_err)
        return result

    def _evaluate_rule_condition(self, localdict):
        self.ensure_one()
        res = False
        try:
            safe_eval(self.condition_python, localdict, mode="exec", nocopy=True)
            return "result" in localdict and localdict["result"] or False
        except Exception as error:
            msg_err = """
Wrong python condition defined for salary rule %s (%s).
Here is the error received:

%s
""" % (
                self.name,
                self.code,
                repr(error),
            )
            raise UserError(_("Error evaluating conditions.\n %s") % msg_err)
        return res

    def _evaluate_rule_amount(self, localdict):
        self.ensure_one()
        res = False
        try:
            safe_eval(self.amount_python, localdict, mode="exec", nocopy=True)
            return (
                float(localdict["result"]),
                "result_qty" in localdict and localdict["result_qty"] or 1.0,
                "result_rate" in localdict and localdict["result_rate"] or 100.0,
            )
        except Exception as error:
            msg_err = """
Wrong python condition defined for salary rule %s (%s).
Here is the error received:

%s
""" % (
                self.name,
                self.code,
                repr(error),
            )
            raise UserError(_("Error evaluating conditions.\n %s") % msg_err)
        return res
