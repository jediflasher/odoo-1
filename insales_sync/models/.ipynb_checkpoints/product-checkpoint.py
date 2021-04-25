# -*- coding: utf-8 -*-
"InSales Product models"

from odoo import api, fields, models


class ProductTemplate(models.Model):
    "Product Template Model"
    # pylint: disable=too-few-public-methods
    _inherit = "product.template"

    insales_sync_config_id = fields.Many2one(
        comodel_name="insales_sync.config",
        ondelete="set null",
        string="InSales Configuration",
        default=None,
    )
    insales_sync_product_id = fields.Integer(string="InSales Product Id")
    insales_sync_permalink = fields.Char(string="InSales Product Handle")

    @api.depends("product_variant_ids", "product_variant_ids.insales_sync_variant_id")
    def _compute_insales_sync_variant_id(self):
        unique_variants = self.filtered(
            lambda template: len(template.product_variant_ids) == 1
        )
        for template in unique_variants:
            template.insales_sync_variant_id = (
                template.product_variant_ids.insales_sync_variant_id
            )
        for template in self - unique_variants:
            template.insales_sync_variant_id = False

    @api.one
    def _set_insales_sync_variant_id(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.insales_sync_variant_id = (
                self.insales_sync_variant_id
            )

    insales_sync_variant_id = fields.Integer(
        "InSales Variant Id",
        compute=_compute_insales_sync_variant_id,
        inverse=_set_insales_sync_variant_id,
        store=True,
    )

    @api.depends("product_variant_ids", "product_variant_ids.insales_sync_skip_price")
    def _compute_insales_sync_skip_price(self):
        unique_variants = self.filtered(
            lambda template: len(template.product_variant_ids) == 1
        )
        for template in unique_variants:
            template.insales_sync_skip_price = (
                template.product_variant_ids.insales_sync_skip_price
            )
        for template in self - unique_variants:
            template.insales_sync_skip_price = False

    @api.one
    def _set_insales_sync_skip_price(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.insales_sync_skip_price = (
                self.insales_sync_skip_price
            )

    insales_sync_skip_price = fields.Boolean(
        string="Skip Price Synchronization",
        compute=_compute_insales_sync_skip_price,
        inverse=_set_insales_sync_skip_price,
        store=True,
    )

    @api.depends("product_variant_ids", "product_variant_ids.insales_sync_skip_qty")
    def _compute_insales_sync_skip_qty(self):
        unique_variants = self.filtered(
            lambda template: len(template.product_variant_ids) == 1
        )
        for template in unique_variants:
            template.insales_sync_skip_qty = (
                template.product_variant_ids.insales_sync_skip_qty
            )
        for template in self - unique_variants:
            template.insales_sync_skip_qty = False

    @api.one
    def _set_insales_sync_skip_qty(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.insales_sync_skip_qty = self.insales_sync_skip_qty

    insales_sync_skip_qty = fields.Boolean(
        string="Skip Quantity Synchronization",
        compute=_compute_insales_sync_skip_qty,
        inverse=_set_insales_sync_skip_qty,
        store=True,
    )

    @api.depends("product_variant_ids", "product_variant_ids.insales_sync_skip_weight")
    def _compute_insales_sync_skip_weight(self):
        unique_variants = self.filtered(
            lambda template: len(template.product_variant_ids) == 1
        )
        for template in unique_variants:
            template.insales_sync_skip_weight = (
                template.product_variant_ids.insales_sync_skip_weight
            )
        for template in self - unique_variants:
            template.insales_sync_skip_weight = False

    @api.one
    def _set_insales_sync_skip_weight(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.insales_sync_skip_weight = (
                self.insales_sync_skip_weight
            )

    insales_sync_skip_weight = fields.Boolean(
        string="Skip Weight Synchronization",
        compute=_compute_insales_sync_skip_weight,
        inverse=_set_insales_sync_skip_weight,
        store=True,
    )

    @api.depends("product_variant_ids", "product_variant_ids.insales_sync_timestamp")
    def _compute_insales_sync_timesmamp(self):
        unique_variants = self.filtered(
            lambda template: len(template.product_variant_ids) == 1
        )
        for template in unique_variants:
            template.insales_sync_timestamp = (
                template.product_variant_ids.insales_sync_timestamp
            )
        for template in self - unique_variants:
            template.insales_sync_timestamp = False

    insales_sync_timestamp = fields.Datetime(
        string="InSales Last Synchronization",
        compute=_compute_insales_sync_timesmamp,
        store=True,
    )

    def _compute_insales_sync_visible(self):
        "InSales tab visible"
        for record in self:
            record.insales_sync_visible = bool(record.sudo().insales_sync_config_id)

    insales_sync_visible = fields.Boolean(compute=_compute_insales_sync_visible)

    def _compute_insales_sync_public_url(self):
        "Compute public url of product"
        for record in self:
            config_id = record.sudo().insales_sync_config_id
            if not config_id or not record.insales_sync_permalink:
                record.insales_sync_public_url = False
            else:
                record.insales_sync_public_url = "https://{}.myinsales.ru/product/{}".format(
                    config_id.host, record.insales_sync_permalink
                )

    insales_sync_public_url = fields.Char(
        string="InSales Public Product URL", compute=_compute_insales_sync_public_url
    )

    def _compute_insales_sync_admin_url(self):
        "Compute admin url of product"
        for record in self:
            config_id = record.sudo().insales_sync_config_id
            if not config_id or not record.insales_sync_product_id:
                record.insales_sync_admin_url = False
            else:
                record.insales_sync_admin_url = "https://{}.myinsales.ru/admin2/products/{}".format(
                    config_id.host, record.insales_sync_product_id
                )

    insales_sync_admin_url = fields.Char(
        string="InSales Admin Product URL", compute=_compute_insales_sync_admin_url
    )

    def insales_sync_now_action(self):
        "Sync product now"
        for record in self:
            record.env["insales_sync.sync_product"].sync_insales_product(record)


class ProductProduct(models.Model):
    "Product Model"
    # pylint: disable=too-few-public-methods
    _inherit = "product.product"

    insales_sync_variant_id = fields.Integer(string="InSales Variant Id")
    insales_sync_timestamp = fields.Datetime(
        string="InSales Last Synchronization", index=True
    )
    insales_sync_skip_price = fields.Boolean(
        string="Skip Price Synchronization", default=False
    )
    insales_sync_skip_qty = fields.Boolean(
        string="Skip Quantity Synchronization", default=False
    )
    insales_sync_skip_weight = fields.Boolean(
        string="Skip Weight Synchronization", default=False
    )

    def insales_sync_get_quantity(self, location):
        "Find product quantity in location"
        self.ensure_one()
        quant = self.env["stock.quant"].search(
            [("product_id", "=", self.id), ("location_id", "=", location.id)]
        )
        reserved = sum(line.reserved_quantity for line in quant)
        on_hand = sum(line.quantity for line in quant)
        return int(on_hand - reserved)

    def insales_sync_now_action(self):
        "Sync variant now"
        for record in self:
            record.env["insales_sync.sync_product"].sync_insales_variant(record)
