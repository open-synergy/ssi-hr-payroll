# Copyright 2022 OpenSynergy Indonesia
# Copyright 2022 PT. Simetri Sinergi Indonesia
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl-3.0-standalone.html).

from odoo import fields, models


class HrPayslipInput(models.Model):
    _name = "hr.payslip_input"

    _description = "Payslip Input"

    payslip_id = fields.Many2one(
        string="Payslip",
        comodel_name="hr.payslip",
        required=True,
        ondelete="cascade",
    )
    input_type_id = fields.Many2one(
        string="Input Type",
        comodel_name="hr.payslip_input_type",
        required=True,
        ondelete="restrict",
    )
    amount = fields.Float(
        string="Amount",
        required=True,
    )
