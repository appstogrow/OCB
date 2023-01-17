from odoo import api, fields, models
from odoo.exceptions import AccessError
from . import ir_model

"""
If company_id doesn't exist, look for it in a related record.
Key: model name
Value: field name to reference another record.
"""
FIELD_NAME_TO_GET_COMPANY = {
    'ir.default': 'user_id',
    'ir.model.data': 'res_id',
    'ir.property': 'res_id',
    "mail.activity": "res_id",
    'website.menu': 'website_id',
}

def _get_model_name_and_res_id(self, field, data):
    if not _get_value(field.name, data):
        comodel_name = res_id = None
    elif field.type == 'many2one':
        comodel_name = field.comodel_name
        res_id = _get_value(field.name, data)
    elif field.type == 'many2one_reference':
        try:
            comodel_name = _get_value(field.model_field, data)
        except:
            # mail.activity action_close_dialog():
            # mail.activity.res_id is connected with res_model_id instead of res_model
            model_field = self._fields[field.model_field]
            position = len(model_field.related) - 2
            comodel_id = _get_value(model_field.related[position], data)
            comodel_name = self.env["ir.model"].browse(comodel_id).model
        res_id = _get_value(field.name, data)
    elif field.type == 'reference':
        comodel_name, res_id = _get_value(field.name, data).split(',')
        res_id = int(res_id)
    elif field.type == 'char':
      if (field.model_name == 'ir.property' and field.name in ('res_id', 'value_reference')):
        comodel_name, res_id = _get_value(field.name, data).split(',')
        res_id = int(res_id)
      else:
        comodel_name = res_id = None
    elif field.type in ('one2many', 'many2many'):
        comodel_name = field.comodel_name
        commands = _get_value(field.name, data)
        # for command in commands:
        #     This is complex. Need recursive function to check nested values for command 0-1
        #     Command 6 has ids, while the others have id.
        #     TODO later
        return []
    else:
        comodel_name = res_id = None
    return [(comodel_name, res_id)]

def _get_value(field_name, record_or_dict):
    if type(record_or_dict) is dict:
        return record_or_dict[field_name]
    else:
        return getattr(record_or_dict, field_name)


class Base(models.AbstractModel):
    """
    This code cannot be inside multicompany_base; then it is not active on installing/updating modules.

    If multicompany_base is installed:
        Don't accept {'company_id': False}
        (e.g. stock.location from XML)

        Don't accept FK relations to records which the user cannot browse.
    """

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

    def create(self, vals_list):
        for vals_dict in vals_list:
            vals_dict = self._set_company_if_false_and_multicompany_base_is_installed(vals_dict)
            self._security_check_that_user_can_browse_all_relations(vals_dict)
        return super(Base, self).create(vals_list)

    def write(self, vals_dict):
        vals_dict = self._set_company_if_false_and_multicompany_base_is_installed(vals_dict)
        self._security_check_that_user_can_browse_all_relations(vals_dict)
        return super(Base, self).write(vals_dict)

    def _set_company_if_false_and_multicompany_base_is_installed(self, vals_dict):
        if 'company_id' in vals_dict and not vals_dict['company_id']:
            if self.env['ir.module.module'].sudo().search([('name', '=', 'multicompany_base')]).state == 'installed':
                vals_dict['company_id'] = self._related_company(vals_dict).id
        return vals_dict

    def _related_company(self, record_or_values):
        field_name = FIELD_NAME_TO_GET_COMPANY.get(self._name)
        if not field_name:
            return self.env.company

        field = self._fields[field_name]
        [(comodel_name, res_id)] = _get_model_name_and_res_id(self, field, record_or_values)
        if res_id:
            related_record = self.env[comodel_name].browse(res_id)
            return related_record.company_id
        else:
            return self.env.company

    def _security_check_that_user_can_browse_all_relations(self, vals_dict):
        model_exceptions = [
            'ir.mail_server', # Send mail from a mail server which the user cannot access.
        ]
        if not self.env.su:
            for (key, value) in vals_dict.items():
                field = self._fields[key]
                if field.type in ('many2one', 'many2one_reference', 'reference', 'char', 'one2many', 'many2many'):
                    model_name_res_id = _get_model_name_and_res_id(self, field, vals_dict)
                    for model_name, res_id in model_name_res_id:
                        if model_name and res_id and model_name not in model_exceptions:
                            # access_control().field will give AccessError if the user cannot read the record.
                            # This is super important for security!
                            # Without this line, a company manager can get access to e.g. SYSTEM company
                            # with user.write({'company_id': 1, 'company_ids': [[4, 1, 0]})
                            self.env[model_name].browse(res_id).access_control(raise_if_access_error=True)

    def access_control(self, raise_if_access_error):
        """
        Use cases:
        - self.env.ref('xmlid'): .access_control() is added to the api.
        - create() & write() for security reasons.
        """
        # access_ok will always be True in superuser mode.
        access_ok = self.check_access_rights('read', raise_exception=raise_if_access_error)

        if not self.env.user:
            rule_ok = True
        else:
            try:
                self.check_access_rule('read')
                rule_ok = True
            except AccessError:
                rule_ok = False

        if access_ok and rule_ok:
            return self
        else:
            if raise_if_access_error:
                raise AccessError("access_control() failed for this record: {},{}".format(self, id))

    def record_company(self):
        self = self.sudo_bypass_global_rules()
        try:
            company = self.mapped('company_id')
        except:
            return
        if len(company) == 1:
            if company in self.env.user.company_ids:
                return company

    def with_record_company(self):
        company = self.record_company()
        return self.with_company(company) if company else self

    def sudo_bypass_global_rules(self):
        try:
            return self.sudo(bypass_global_rules=True)
        except:
            return self.sudo()
