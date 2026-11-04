"""Task 2 safety-net tests for Campus Supply Desk."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from supplydesk.cli import main
from supplydesk.menu import money, run_menu
from supplydesk.service import OrderService


class ServiceTestCase(unittest.TestCase):
    """Gives every test a fresh, empty save file in a temp folder."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def stock_of(self, product_id):
        for product in self.service.catalog():
            if product["product_id"] == product_id:
                return product["stock"]
        raise AssertionError("missing product " + product_id)


# ---------- Category 1: Normal behaviour ----------
class NormalBehaviourTests(ServiceTestCase):

    def test_student_delivery_order_matches_spec_example(self):
        order = self.service.place_order(
            "student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(order["subtotal_cents"], 8000)
        self.assertEqual(order["discount_cents"], 800)
        self.assertEqual(order["delivery_cents"], 600)
        self.assertEqual(order["total_cents"], 7800)
        self.assertEqual(self.stock_of("hoodie"), 3)

    def test_multi_item_quote_has_correct_lines_and_total(self):
        quote = self.service.quote("regular", [
            {"product_id": "notebook", "quantity": 2},
            {"product_id": "mug", "quantity": 1},
        ])
        self.assertEqual(len(quote["items"]), 2)
        self.assertEqual(quote["items"][0]["line_total_cents"], 1000)
        self.assertEqual(quote["items"][1]["line_total_cents"], 1500)
        self.assertEqual(quote["subtotal_cents"], 2500)
        self.assertEqual(quote["total_cents"], 2500)

    def test_regular_delivery_three_hoodies_gets_free_delivery(self):
        quote = self.service.quote(
            "regular", [{"product_id": "hoodie", "quantity": 3}], "delivery")
        self.assertEqual(quote["subtotal_cents"], 12000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 12000)

    def test_list_orders_returns_orders_in_placement_order(self):
        first = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        second = self.service.place_order("regular", [{"product_id": "bag", "quantity": 1}])
        ids = [order["order_id"] for order in self.service.list_orders()]
        self.assertEqual(ids, [first["order_id"], second["order_id"]])
        self.assertEqual(ids, ["ORD-0001", "ORD-0002"])


# ---------- Category 2: Boundary behaviour ----------
class BoundaryBehaviourTests(ServiceTestCase):

    def test_minimum_quantity_of_one_is_accepted(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 1}])
        self.assertEqual(quote["items"][0]["quantity"], 1)
        self.assertEqual(quote["total_cents"], 500)

    def test_quantity_100_is_rejected_by_the_quantity_rule(self):
        with self.assertRaisesRegex(ValueError, "Quantity must be an integer from 1 to 99"):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 100}])

    def test_quantity_99_passes_quantity_rule_but_fails_on_stock(self):
        # 99 is the largest allowed quantity, but only 20 notebooks exist,
        # so the error must come from the stock check, not the quantity check.
        with self.assertRaisesRegex(ValueError, "Not enough stock for notebook"):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 99}])

    def test_ordering_exactly_all_available_stock_succeeds(self):
        order = self.service.place_order("regular", [{"product_id": "bag", "quantity": 4}])
        self.assertEqual(order["status"], "placed")
        self.assertEqual(self.stock_of("bag"), 0)

    def test_ordering_one_more_than_available_stock_fails(self):
        with self.assertRaisesRegex(ValueError, "Not enough stock for bag"):
            self.service.place_order("regular", [{"product_id": "bag", "quantity": 5}])
        self.assertEqual(self.stock_of("bag"), 4)

    def test_student_subtotal_below_5000_gets_no_discount(self):
        quote = self.service.quote("student", [
            {"product_id": "hoodie", "quantity": 1},
            {"product_id": "notebook", "quantity": 1},
        ])
        self.assertEqual(quote["subtotal_cents"], 4500)
        self.assertEqual(quote["discount_cents"], 0)

    def test_student_subtotal_of_exactly_5000_gets_discount(self):
        # Spec: 10% discount when the subtotal is AT LEAST 5,000 cents.
        quote = self.service.quote("student", [{"product_id": "bag", "quantity": 2}])
        self.assertEqual(quote["subtotal_cents"], 5000)
        self.assertEqual(quote["discount_cents"], 500)
        self.assertEqual(quote["total_cents"], 4500)

    def test_delivery_is_free_at_exactly_10000(self):
        quote = self.service.quote("regular", [{"product_id": "bag", "quantity": 4}], "delivery")
        self.assertEqual(quote["subtotal_cents"], 10000)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 10000)

    def test_delivery_is_charged_just_below_10000(self):
        quote = self.service.quote("regular", [
            {"product_id": "bag", "quantity": 3},
            {"product_id": "mug", "quantity": 1},
        ], "delivery")
        self.assertEqual(quote["subtotal_cents"], 9000)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 9600)

    def test_new_save_file_has_empty_history(self):
        self.assertEqual(self.service.list_orders(), [])
        self.assertFalse(self.path.exists())

    def test_empty_item_list_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one item"):
            self.service.quote("regular", [])


# ---------- Category 3: Invalid or exceptional behaviour ----------
class InvalidBehaviourTests(ServiceTestCase):

    def test_invalid_customer_type_is_rejected(self):
        for customer in ("vip", "Student", ""):
            with self.subTest(customer=customer):
                with self.assertRaisesRegex(ValueError, "Customer type"):
                    self.service.quote(customer, [{"product_id": "mug", "quantity": 1}])

    def test_invalid_fulfillment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Fulfillment"):
            self.service.quote("regular", [{"product_id": "mug", "quantity": 1}], "shipping")

    def test_item_that_is_not_a_dictionary_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "product_id and quantity"):
            self.service.quote("regular", ["mug"])

    def test_unknown_product_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown product"):
            self.service.quote("regular", [{"product_id": "ghost", "quantity": 1}])

    def test_invalid_quantities_are_rejected(self):
        # Spec: booleans, fractions and numeric strings are not valid quantities.
        for quantity in (0, -1, True, "2", 2.0, None):
            with self.subTest(quantity=quantity):
                with self.assertRaisesRegex(ValueError, "Quantity must be an integer"):
                    self.service.quote("regular", [{"product_id": "mug", "quantity": quantity}])

    def test_unknown_order_id_is_rejected_for_lookup_and_cancel(self):
        with self.assertRaisesRegex(ValueError, "Unknown order"):
            self.service.get_order("ORD-9999")
        with self.assertRaisesRegex(ValueError, "Unknown order"):
            self.service.cancel_order("ORD-9999")
        self.assertFalse(self.path.exists())

    def test_rejected_request_does_not_change_saved_data(self):
        self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        before = self.path.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [
                {"product_id": "mug", "quantity": 1},
                {"product_id": "ghost", "quantity": 1},
            ])
        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        next_order = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertEqual(next_order["order_id"], "ORD-0002")

    def test_malformed_save_file_raises_instead_of_resetting(self):
        self.path.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.service.catalog()
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{not valid json")

    def test_cli_returns_exit_code_2_for_unknown_product(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = main(["--data", str(self.path), "place", "--item", "ghost:1"])
        self.assertEqual(code, 2)
        self.assertIn("Unknown product", error.getvalue())
        self.assertFalse(self.path.exists())

    def test_duplicate_lines_cannot_exceed_available_stock(self):
        # Spec: combined quantity across lines must not exceed stock (20 notebooks).
        with self.assertRaisesRegex(ValueError, "Not enough stock"):
            self.service.place_order("regular", [
                {"product_id": "notebook", "quantity": 15},
                {"product_id": "notebook", "quantity": 15},
            ])
        self.assertEqual(self.stock_of("notebook"), 20)

    def test_cancelling_twice_does_not_restore_stock_twice(self):
        order = self.service.place_order("regular", [{"product_id": "mug", "quantity": 2}])
        self.service.cancel_order(order["order_id"])
        again = self.service.cancel_order(order["order_id"])
        self.assertEqual(again["status"], "cancelled")
        self.assertEqual(self.stock_of("mug"), 8)


# ---------- Category 4: Behaviour important to preserve ----------
class PreservedBehaviourTests(ServiceTestCase):

    PRICING_KEYS = ("customer_type", "fulfillment", "items", "subtotal_cents",
                    "discount_cents", "delivery_cents", "total_cents")

    def test_quote_and_placed_order_have_identical_pricing(self):
        # Protects D1: quote() and place_order() will share one helper after refactoring.
        requests = [
            ("regular", [{"product_id": "notebook", "quantity": 2}], "pickup"),
            ("student", [{"product_id": "hoodie", "quantity": 2}], "delivery"),
            ("regular", [{"product_id": "hoodie", "quantity": 3}], "delivery"),
            ("student", [{"product_id": "mug", "quantity": 1},
                         {"product_id": "pen-pack", "quantity": 3}], "delivery"),
        ]
        for index, (customer, items, fulfillment) in enumerate(requests):
            with self.subTest(request=index):
                service = OrderService(Path(self.directory.name) / f"case{index}.json")
                quote = service.quote(customer, items, fulfillment)
                order = service.place_order(customer, items, fulfillment)
                for key in self.PRICING_KEYS:
                    self.assertEqual(order[key], quote[key], key)

    def test_quote_does_not_save_reserve_stock_or_use_an_order_id(self):
        self.service.quote("regular", [{"product_id": "bag", "quantity": 4}])
        self.assertFalse(self.path.exists())
        self.assertEqual(self.stock_of("bag"), 4)
        order = self.service.place_order("regular", [{"product_id": "bag", "quantity": 1}])
        self.assertEqual(order["order_id"], "ORD-0001")

    def test_order_ids_are_not_reused_after_cancellation(self):
        first = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.service.cancel_order(first["order_id"])
        second = self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertEqual(second["order_id"], "ORD-0002")

    def test_cancelled_order_stays_in_history_with_original_totals(self):
        order = self.service.place_order("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.service.cancel_order(order["order_id"])
        history = self.service.list_orders()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "cancelled")
        self.assertEqual(history[0]["items"], order["items"])
        self.assertEqual(history[0]["total_cents"], 7800)
        self.assertEqual(self.stock_of("hoodie"), 5)

    def test_orders_and_stock_survive_reopening(self):
        self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 3}])
        reopened = OrderService(self.path)
        self.assertEqual([o["order_id"] for o in reopened.list_orders()], ["ORD-0001"])
        pen_stock = [p["stock"] for p in reopened.catalog() if p["product_id"] == "pen-pack"]
        self.assertEqual(pen_stock, [7])

    def test_money_formats_cents_as_dollars(self):
        self.assertEqual(money(1000), "$10.00")
        self.assertEqual(money(7800), "$78.00")
        self.assertEqual(money(5), "$0.05")
        self.assertEqual(money(0), "$0.00")

    def test_cli_quote_prints_json_and_returns_0(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--data", str(self.path), "quote", "--item", "notebook:2"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["customer_type"], "regular")
        self.assertEqual(result["fulfillment"], "pickup")
        self.assertEqual(result["total_cents"], 1000)
        self.assertFalse(self.path.exists())

    def test_menu_quote_shows_total_and_creates_no_order(self):
        # Protects D3: run_menu() will be split into smaller methods.
        # Inputs: option 2, regular, notebook x 2, finish items, pickup, then exit.
        answers = ["2", "regular", "notebook", "2", "", "", "0"]
        output = io.StringIO()
        with mock.patch("builtins.input", side_effect=answers), contextlib.redirect_stdout(output):
            code = run_menu(self.service)
        self.assertEqual(code, 0)
        self.assertIn("Total: $10.00", output.getvalue())
        self.assertIn("Quote only", output.getvalue())
        self.assertFalse(self.path.exists())

if __name__ == "__main__":
    unittest.main()