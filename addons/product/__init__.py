# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import report
from . import populate

from odoo.addons.base.models.base_test import update_xmlids
from odoo.api import Environment, SUPERUSER_ID

def post_init_hook(cr, registry):
    env = Environment(cr, SUPERUSER_ID, {})
    test_price_list = env.ref("product.test_price_list")
    xmlids = [
        ("product", "list0", test_price_list.id)
    ]
    update_xmlids(env.cr, xmlids)
