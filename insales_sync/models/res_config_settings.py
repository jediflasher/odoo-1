# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_insales_sync = fields.Boolean(
        string="InSales Sync", default=True, readonly=True,
    )
