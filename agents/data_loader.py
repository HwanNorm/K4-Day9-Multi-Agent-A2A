"""Loads Olist CSVs once and exposes lookup helpers keyed by order_id / customer_unique_id."""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class OlistData:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.orders = pd.read_csv(data_dir / "olist_orders_dataset.csv")
        self.items = pd.read_csv(data_dir / "olist_order_items_dataset.csv")
        self.payments = pd.read_csv(data_dir / "olist_order_payments_dataset.csv")
        self.customers = pd.read_csv(data_dir / "olist_customers_dataset.csv")
        self.sellers = pd.read_csv(data_dir / "olist_sellers_dataset.csv")
        self.products = pd.read_csv(data_dir / "olist_products_dataset.csv")
        self.category_translation = pd.read_csv(data_dir / "product_category_name_translation.csv")

        for col in [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]:
            self.orders[col] = pd.to_datetime(self.orders[col], errors="coerce")
        self.items["shipping_limit_date"] = pd.to_datetime(
            self.items["shipping_limit_date"], errors="coerce"
        )

        self.products = self.products.merge(
            self.category_translation, on="product_category_name", how="left"
        )

    def get_order(self, order_id: str):
        rows = self.orders[self.orders["order_id"] == order_id]
        return rows.iloc[0] if not rows.empty else None

    def get_items(self, order_id: str) -> pd.DataFrame:
        return self.items[self.items["order_id"] == order_id].sort_values("order_item_id")

    def get_payments(self, order_id: str) -> pd.DataFrame:
        return self.payments[self.payments["order_id"] == order_id].sort_values(
            "payment_sequential"
        )

    def get_customer(self, customer_id: str):
        rows = self.customers[self.customers["customer_id"] == customer_id]
        return rows.iloc[0] if not rows.empty else None

    def get_related_orders(self, customer_unique_id: str, exclude_order_id: str) -> pd.DataFrame:
        cust_ids = self.customers[
            self.customers["customer_unique_id"] == customer_unique_id
        ]["customer_id"]
        related = self.orders[
            self.orders["customer_id"].isin(cust_ids) & (self.orders["order_id"] != exclude_order_id)
        ]
        return related

    def get_seller(self, seller_id: str):
        rows = self.sellers[self.sellers["seller_id"] == seller_id]
        return rows.iloc[0] if not rows.empty else None

    def get_product(self, product_id: str):
        rows = self.products[self.products["product_id"] == product_id]
        return rows.iloc[0] if not rows.empty else None
