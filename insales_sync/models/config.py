# -*- coding: utf-8 -*-
"InSales sync configuration models"

import logging
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from .exc import GetIdOfAdditionalFieldError

log = logging.getLogger(__name__)

try:
    from insales import InSalesApi
    from insales.connection import ApiError
except ImportError as err:
    log.critical(err)


class InSalesSyncConfig(models.Model):
    "InSales configuration"

    _name = "insales_sync.config"
    _order = "host, api_key"

    name = fields.Char(required=True, string="Name", default="New Configuration")
    host = fields.Char(required=True, string="Host prefix")
    api_key = fields.Char(required=True, string="API Key")
    api_password = fields.Char(required=True, string="API Password")
    active = fields.Boolean(
        required=True,
        default=False,
        index=True,
        string="Active",
        help="Configuration may be temporary disabled",
    )
    prod_environment = fields.Boolean(
        required=True,
        default=False,
        string="Environment",
        help="Only insignificant information is synchronized in test environment.\n"
        "Important data is only written to the log.",
    )
    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        ondelete="set null",
        string="Active Pricelist",
        default=None,
    )
    old_pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        ondelete="set null",
        string="Old Price Pricelist",
        default=None,
    )
    categories = fields.One2many(
        string="InSales Categories",
        comodel_name="insales_sync.config.category",
        inverse_name="config_id",
    )
    quantity_fields = fields.One2many(
        string="Quantity Fields",
        comodel_name="insales_sync.config.quantity",
        inverse_name="config_id",
    )
    sync_weight = fields.Boolean(string="Synchronize Product Weight", default=False)
    sync_weight_skip_zero = fields.Boolean(
        string="Skip Sync of Zero Weight", default=True
    )

    @api.multi
    def toggle_prod_environment(self):
        "Toggle production/testing environment"
        for record in self:
            record.prod_environment = not record.prod_environment

    @api.multi
    def get_api_client(self):
        "Get InSalesApi client instance"
        self.ensure_one()
        return InSalesApi.from_credentials(
            self.host, self.api_key, self.api_password, response_timeout=60,
        )

    @api.multi
    def update_categories(self):
        "Update list of categories"
        for record in self:
            client = record.get_api_client()
            # root category is useless and must be skipped
            # in_categories = [x for x in client.get_categories() if x.get("parent-id")]
            in_categories = client.get_categories()

            # remove stale records
            record.categories.search(
                [["insales_id", "not in", [x.get("id") for x in in_categories]]]
            ).unlink()

            # create or update
            cats = {
                cat.insales_id: {"id": cat.id, "insales_id": cat.insales_id}
                for cat in record.categories
            }
            for in_cat in in_categories:
                content = {
                    "title": in_cat.get("title"),
                    "insales_id": in_cat.get("id"),
                    "insales_parent_id": in_cat.get("parent-id"),
                }
                cat = cats.get(in_cat.get("id"))
                if cat:
                    cat.update(content)
                else:
                    cats[content.get("insales_id")] = content

            def walk_up(tree, curr, path=None):
                parent = tree.get(curr.get("insales_parent_id"))
                if not parent:
                    return path or []
                path = [parent.get("insales_id")] + (path or [])
                return walk_up(tree, parent, path)

            for cat in cats.values():
                parent_path = walk_up(cats, cat)
                cat.update({"parent_path": "/".join([str(x) for x in parent_path])})
                path_named = [cats.get(x, {}).get("title", "") for x in parent_path] + [
                    cat.get("title", "")
                ]
                cat.update({"path_named": " / ".join(path_named)})

            for cat in cats.values():
                # suppress warnings
                del cat["insales_parent_id"]

            data = [(1 if x.get("id") else 0, x.get("id", 0), x) for x in cats.values()]
            record.write({"categories": data})

    @api.multi
    def update_categories_action(self):
        "Update cetegories action"
        self.update_categories()

    @api.multi
    def sync_now_action(self):
        "Update cetegories action"
        for record in self:
            record.env["insales_sync.sync_product"].sync_configuration(record)


class InSalesSyncConfigCategory(models.Model):
    "InSales category"
    # pylint: disable=too-few-public-methods

    _name = "insales_sync.config.category"
    _order = "path_named"

    config_id = fields.Many2one(
        comodel_name="insales_sync.config",
        ondelete="cascade",
        string="Configuration",
        index=True,
        required=True,
    )
    title = fields.Char(string="Title")
    insales_id = fields.Integer(required=True, string="InSales Id")
    parent_path = fields.Char(string="Materialized Parent Path", default="")
    path_named = fields.Char(string="Materialized Path Titles", default="")
    sync = fields.Boolean(string="Synchronize", default=False, index=True)

    @api.multi
    def get_self_path(self):
        "Get self materialized path"
        self.ensure_one()
        return "/".join(
            [x for x in self.parent_path.split("/") if x] + [str(self.insales_id)]
        )

    @api.multi
    def get_children(self):
        "Get children"
        self.ensure_one()
        return self.search([["parent_path", "=like", self.get_self_path() + "%"]])

    @api.multi
    def propagate_sync_to_children(self):
        "Propagate Sync boolean to children"
        for record in self:
            if record.sync:
                record.get_children().write({"sync": True})

    @api.multi
    def write(self, values):
        "Save model with propagation to children"
        super(InSalesSyncConfigCategory, self).write(values)
        self.propagate_sync_to_children()


class InSalesSyncConfigQuantity(models.Model):
    "What product category sync to what field of InSales variant"
    # pylint: disable=too-few-public-methods

    _name = "insales_sync.config.quantity"

    config_id = fields.Many2one(
        comodel_name="insales_sync.config",
        ondelete="cascade",
        string="Configuration",
        index=True,
        required=True,
    )
    location = fields.Many2one(
        "stock.location", string="Location", required=True, domain=[]
    )
    is_additional = fields.Boolean(string="Field is additional")
    insales_field = fields.Char(string="InSales Field", required=True)

    @api.depends("insales_field", "is_additional")
    def _compute_insales_field_id(self):
        "Get InSales field id"
        for record in self:
            if not record.is_additional:
                record.insales_field_id = None
                continue
            client = record.config_id.get_api_client()
            try:
                in_field = client.get_variant_field(record.insales_field)
                in_id = in_field.get("id")
                record.insales_field_id = in_id
            except ApiError:
                raise ValidationError(
                    _(GetIdOfAdditionalFieldError(record.insales_field).message)
                )

    insales_field_id = fields.Integer(
        string="InSales Field ID", compute=_compute_insales_field_id, store=True,
    )
