# -*- coding: utf-8 -*-
"Common exceptions"


class GetIdOfAdditionalFieldError(Exception):
    "Get id of additional field exception"

    def __init__(self, field_id: int):
        msg = "Can't get additional field id: {}".format(field_id)
        super().__init__(msg)
        self.message = msg


class MultipleProductError(Exception):
    "Multiple products with same reference exception"

    def __init__(self, sku: str):
        msg = "Multiple products with internal reference {} found in Odoo".format(sku)
        super().__init__(msg)
        self.message = msg


class ProductInSalesNotFoundError(Exception):
    "Product not found exception"

    def __init__(self, product_id: str):
        msg = "Product with InSales ID {} not found".format(product_id)
        super().__init__(msg)
        self.message = msg


class VariantInSalesNotFoundError(Exception):
    "Variant not found exception"

    def __init__(self, variant_id: int):
        msg = "Variant with InSales Variant ID {} not found".format(variant_id)
        super().__init__(msg)
        self.message = msg


class VariantSkuNotFoundError(Exception):
    "Variant SKU not found exception"

    def __init__(self, product_id: int, variant_id: int):
        msg = "Variant with InSales Product ID {} and Variant ID {} have no SKU".format(
            product_id, variant_id
        )
        super().__init__(msg)
        self.message = msg


class UnknownInSalesVariantField(Exception):
    "Unknown InSales variant field"

    def __init__(self, field: str):
        msg = "Unknown InSales field: {}".format(field)
        super().__init__(msg)
        self.message = msg
