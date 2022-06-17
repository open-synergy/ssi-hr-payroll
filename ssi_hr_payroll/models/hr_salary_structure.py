# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0-standalone.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrSalaryStructure(models.Model):
    _name = "hr.salary_structure"
    _inherit = [
        "mixin.master_data",
    ]
    _description = "Salary Structure"

    parent_id = fields.Many2one(
        string="Parent",
        comodel_name="hr.salary_structure",
        ondelete="restrict",
    )
    rule_ids = fields.Many2many(
        string="Salary Rules",
        comodel_name="hr.salary_rule",
        relation="rel_structure_2_salary_rule",
        column1="structure_id",
        column2="rule_id",
    )

    @api.constrains("parent_id")
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_("You cannot create a recursive salary structure."))

    def get_all_rules(self):
        """
        @return: returns a list of tuple (id, sequence) of rules that are maybe
                 to apply
        """
        all_rules = []
        for document in self:
            all_rules += document.rule_ids._recursive_search_of_rules()
        return all_rules
