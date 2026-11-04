"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore


class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    # ---------- private helpers ----------

    def _find_product(self, catalog, product_id):
        """Return the catalog product with this id, or None."""
        for product in catalog:
            if product["product_id"] == product_id:
                return product
        return None

    def _find_order(self, state, order_id):
        """Return the order with this id, or raise ValueError."""
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)

    def _price_request(self, state, customer_type, items, fulfillment):
        """Validate a request and return its priced summary.
        Shared by quote() and place_order() so they can never disagree."""
        if customer_type not in ("regular", "student"):
            raise ValueError("Customer type must be regular or student.")
        if fulfillment not in ("pickup", "delivery"):
            raise ValueError("Fulfillment must be pickup or delivery.")
        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")
        lines = []
        subtotal = 0
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")
            product = self._find_product(state["catalog"], item.get("product_id"))
            if product is None:
                raise ValueError("Unknown product.")
            quantity = item.get("quantity")
            if type(quantity) is not int or quantity < 1 or quantity > 99:
                raise ValueError("Quantity must be an integer from 1 to 99.")
            if quantity > product["stock"]:
                raise ValueError("Not enough stock for " + product["product_id"] + ".")
            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total
            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })
        discount = 0
        if customer_type == "student" and subtotal > 5000:
            discount = (subtotal * 10 + 50) // 100
        delivery = 0
        if fulfillment == "delivery" and subtotal - discount < 10000:
            delivery = 600
        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }

    # ---------- public operations ----------

    def catalog(self):
        return self.store.load()["catalog"]

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return self._price_request(state, customer_type, items, fulfillment)

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        priced = self._price_request(state, customer_type, items, fulfillment)
        order = {
            "order_id": "ORD-" + str(state["next_order_number"]).zfill(4),
            "status": "placed",
            **priced,
        }
        for line in order["items"]:
            self._find_product(state["catalog"], line["product_id"])["stock"] -= line["quantity"]
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        return self._find_order(self.store.load(), order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = self._find_order(state, order_id)
        for line in order["items"]:
            self._find_product(state["catalog"], line["product_id"])["stock"] += line["quantity"]
        order["status"] = "cancelled"
        self.store.save(state)
        return order