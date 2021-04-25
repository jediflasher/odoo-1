# -*- coding: utf-8 -*-
"Sync products and variants"

import logging
from decimal import Decimal
from itertools import chain
from typing import NamedTuple
from odoo import fields, models
from odoo.tools.float_utils import float_is_zero, float_repr
from .exc import (
    MultipleProductError,
    ProductInSalesNotFoundError,
    VariantSkuNotFoundError,
    VariantInSalesNotFoundError,
    UnknownInSalesVariantField,
)

log = logging.getLogger(__name__)

try:
    from insales.connection import ApiError
except ImportError as err:
    log.critical(err)


class VariantModifier(NamedTuple):
    "InSales Variant modifier"
    field_name: str
    value: any
    diff_name: str
    diff_old_value: any
    diff_new_value: any
    is_list: bool = False


class InsalesSyncProduct(models.Model):
    "Sync InSales product and variant with Odoo Product Template and Product Product"
    _name = "insales_sync.sync_product"

    @staticmethod
    def get_quantity_from_insales_variant(in_variant, field):
        "Get quantity from InSales variant"
        if field.is_additional:
            for in_field in in_variant.get("variant-field-values", []):
                if field.insales_field_id == in_field.get("variant-field-id"):
                    return int(in_field.get("value") or 0)
            return 0

        if field.insales_field not in in_variant.keys():
            raise UnknownInSalesVariantField(field.insales_field)
        return int(in_variant.get(field.insales_field) or 0)

    def _get_insales_variant_qty_modifiers(self, product, in_variant):
        "Get InSales quantity variant modifiers"
        if product.insales_sync_skip_qty:
            return []

        cfg = product.insales_sync_config_id
        mods = []

        for field in cfg.quantity_fields:
            try:
                in_qty = max(
                    self.get_quantity_from_insales_variant(in_variant, field), 0
                )
                odoo_qty = product.insales_sync_get_quantity(field.location)
            except UnknownInSalesVariantField as err:
                log.error(err.message)
                continue
            if in_qty == odoo_qty:
                continue

            mods.append(
                VariantModifier(
                    field_name=(
                        "variant-field-values-attributes"
                        if field.is_additional
                        else field.insales_field
                    ),
                    value=(
                        {"handle": field.insales_field, "value": odoo_qty}
                        if field.is_additional
                        else odoo_qty
                    ),
                    is_list=field.is_additional,
                    diff_name=field.insales_field,
                    diff_old_value=in_qty,
                    diff_new_value=odoo_qty,
                )
            )

        return mods

    def _get_insales_variant_weight_modifiers(self, product, in_weight):
        "Get InSales weight variant modifiers"
        cfg = product.insales_sync_config_id
        if not cfg.sync_weight or product.insales_sync_skip_weight:
            return []
        digits = self.env["decimal.precision"].precision_get("Stock Weight") or 16
        weight_str = float_repr(max(product.weight, 0), precision_digits=digits)

        if in_weight == Decimal(weight_str):
            return []

        weight_is_zero = float_is_zero(product.weight, precision_digits=digits)
        if cfg.sync_weight_skip_zero and weight_is_zero:
            log.warning(
                "Skip zero weight sync of InSales variant %s", product.default_code,
            )
            return []

        new_value = weight_str if not weight_is_zero else None
        return [
            VariantModifier(
                field_name="weight",
                value=new_value,
                diff_name="weight",
                diff_old_value=(str(in_weight) if in_weight else None),
                diff_new_value=new_value,
            )
        ]

    def _get_insales_variant_price_modifiers(self, product, in_price, in_old_price):
        "Get InSales price variant modifiers"
        cfg = product.insales_sync_config_id
        if not cfg.pricelist_id or product.insales_sync_skip_price:
            return []
        digits = self.env["decimal.precision"].precision_get("Product Price") or 16
        price = max(cfg.pricelist_id.get_product_price(product, 1, None), 0)
        price_str = float_repr(price, precision_digits=digits)

        mods = []
        if in_price != Decimal(price_str):
            mods.append(
                VariantModifier(
                    field_name="price",
                    value=price_str,
                    diff_name="price",
                    diff_old_value=(str(in_price) if in_price else None),
                    diff_new_value=price_str,
                )
            )
        if cfg.old_pricelist_id:
            old_price = cfg.old_pricelist_id.get_product_price(product, 1, None)
            old_price_str = float_repr(old_price, precision_digits=digits)
            if old_price <= price:
                old_price_str = None
            if (old_price_str and in_old_price != Decimal(old_price_str)) or (
                not old_price_str and in_old_price != old_price_str
            ):
                mods.append(
                    VariantModifier(
                        field_name="old-price",
                        value=old_price_str,
                        diff_name="old_price",
                        diff_old_value=(str(in_old_price) if in_old_price else None),
                        diff_new_value=old_price_str,
                    )
                )

        return mods

    def process_insales_variant(self, product_product, in_variant):
        "Process InSales variant"
        # pylint: disable=too-many-locals
        cfg = product_product.insales_sync_config_id

        # odoo -> insales
        mods = (
            self._get_insales_variant_weight_modifiers(
                product_product, in_variant.get("weight")
            )
            + self._get_insales_variant_price_modifiers(
                product_product, in_variant.get("price"), in_variant.get("old-price")
            )
            + self._get_insales_variant_qty_modifiers(product_product, in_variant)
        )

        if mods:
            diff_str = ", ".join(
                [
                    f"{x.diff_name}({x.diff_old_value} -> {x.diff_new_value})"
                    for x in mods
                ]
            )
            log.info(
                "Updating InSales variant %s: %s",
                product_product.default_code,
                diff_str,
            )

            if cfg.prod_environment:
                data = {}
                for mod in mods:
                    data[mod.field_name] = (
                        data.get(mod.field_name, []) + [mod.value]
                        if mod.is_list
                        else mod.value
                    )
                cfg.get_api_client().update_product_variant(
                    in_variant.get("product-id"), in_variant.get("id"), data
                )

        # insales -> odoo
        product_product.write(
            {
                "insales_sync_variant_id": in_variant.get("id"),
                "insales_sync_timestamp": fields.Datetime.now(),
            }
        )

    def sync_insales_variant(self, product_product):
        "Sync one InSales variant"
        product_id = product_product.insales_sync_product_id
        variant_id = product_product.insales_sync_variant_id
        cfg = product_product.insales_sync_config_id
        if not cfg or not cfg.active or not variant_id or not product_id:
            return
        client = cfg.get_api_client()
        try:
            in_variant = client.get_product_variant(product_id, variant_id)
            self.process_insales_variant(product_product, in_variant)
        except ApiError:
            raise VariantInSalesNotFoundError(variant_id)

    def process_insales_product(self, cfg, in_product):
        "Process InSales product"
        log.debug("Process product %s", in_product.get("permalink"))

        # process every variant
        for in_variant in in_product.get("variants", []):
            try:
                log.debug("Process variant %s", in_variant.get("sku"))

                # find product_product
                sku = in_variant.get("sku")
                if sku is None:
                    raise VariantSkuNotFoundError(
                        in_variant.get("product-id"), in_variant.get("id")
                    )
                product_product = self.env["product.product"].search(
                    [("default_code", "=", sku)]
                )
                if not product_product:
                    raise ProductInSalesNotFoundError(sku)
                if len(product_product) > 1:
                    raise MultipleProductError(sku)

                # update product_template
                product_product.product_tmpl_id.write(
                    {
                        "insales_sync_config_id": cfg.id,
                        "insales_sync_product_id": in_product.get("id"),
                        "insales_sync_permalink": in_product.get("permalink"),
                    }
                )

                # process insales variant
                self.process_insales_variant(product_product, in_variant)

            except (
                MultipleProductError,
                ProductInSalesNotFoundError,
                UnknownInSalesVariantField,
                VariantSkuNotFoundError,
            ) as err:
                log.error(err.message)
                continue

    def sync_insales_product(self, product_template):
        "Sync one InSales product"
        product_id = product_template.insales_sync_product_id
        cfg = product_template.insales_sync_config_id
        if not cfg or not cfg.active or not product_id:
            return
        client = cfg.get_api_client()
        try:
            in_product = client.get_product(product_id)
            self.process_insales_product(cfg, in_product)
        except ApiError:
            raise ProductInSalesNotFoundError(product_id)

    @staticmethod
    def get_iter_all_products(cfg):
        "Get iterator over all products"
        client = cfg.get_api_client()
        allowed_cat_ids = [
            cat.insales_id for cat in cfg.categories.search([["sync", "=", True]])
        ]

        # request by one category at a time because of unpredictable buggy filter
        get_iter_products_by_cat_id = lambda category_id: client.iterate_over_all(
            client.get_products, per_page=100, category_id=category_id
        )
        return chain.from_iterable(map(get_iter_products_by_cat_id, allowed_cat_ids))

    def sync_configuration(self, cfg):
        "Process connection"
        if not cfg.active:
            return

        # update categories list (new child categories?)
        cfg.update_categories()

        # iterate over all non-deleted products from allowed categories
        for in_product in self.get_iter_all_products(cfg):
            self.process_insales_product(cfg, in_product)

    # Entry point
    def cron_do(self):
        "Process every InSales configuration"
        for cfg in self.env["insales_sync.config"].search([["active", "=", True]]):
            self.sync_configuration(cfg)
