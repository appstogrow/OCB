from odoo import api, fields, models
from . import ir_model


class Base(models.AbstractModel):
    _inherit = 'base'

    # This field is used by global rules.
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        store=True,
        index=True,
        # required=True,
        default=lambda self: self.env.company,
    )
