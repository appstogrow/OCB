def update_xmlids(cr, xmlids):
    """
    Link xmlids to other res_id (test records)
    :param xmlids: list of tuples with module, name, res_id
    """
    for module, name, res_id in xmlids:
        # Cannot use ORM to change records with "noupdate" on external id.
        cr.execute(
            """UPDATE ir_model_data SET res_id = {res_id}
            WHERE module = '{module}' AND name = '{name}'"""
            .format(
                module=module, name=name, res_id=res_id
            )
        )
