"""CR-01 Express Delivery tests. Written before the implementation."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from supplydesk.cli import main
from supplydesk.menu import run_menu
from supplydesk.service import OrderService

NOTEBOOKS_2 = [{"product_id": "notebook", "quantity": 2}]
HOODIES_2 = [{"product_id": "hoodie", "quantity": 2}]
HOODIES_3 = [{"product_id": "hoodie", "quantity": 3}]
BAGS_4 = [{"product_id": "bag", "quantity": 4}]          # exactly 10,000 cents

PRICING_KEYS = ("customer_type", "fulfillment", "items", "subtotal_cents",
                "discount_cents", "delivery_cents", "total_cents")


class ExpressTestCase(unittest.TestCase):

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


# ---------- Requirements 2, 3, 4, 6: pricing and validation ----------
class ExpressPricingTests(ExpressTestCase):

    def test_regular_two_notebooks_express_is_22_dollars(self):
        quote = self.service.quote("regular", NOTEBOOKS_2, "express")
        self.assertEqual(quote["fulfillment"], "express")
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 2200)

    def test_student_two_hoodies_express_is_84_dollars(self):
        quote = self.service.quote("student", HOODIES_2, "express")
        self.assertEqual(quote["subtotal_cents"], 8000)
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 8400)

    def test_three_hoodies_standard_120_but_express_132(self):
        standard = self.service.quote("regular", HOODIES_3, "delivery")
        express = self.service.quote("regular", HOODIES_3, "express")
        self.assertEqual(standard["total_cents"], 12000)   # existing free-delivery rule kept
        self.assertEqual(express["delivery_cents"], 1200)
        self.assertEqual(express["total_cents"], 13200)

    def test_express_fee_is_not_waived_at_exactly_10000(self):
        quote = self.service.quote("regular", BAGS_4, "express")
        self.assertEqual(quote["subtotal_cents"], 10000)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 11200)

    def test_student_discount_is_the_same_for_every_fulfillment(self):
        discounts = [self.service.quote("student", HOODIES_2, f)["discount_cents"]
                     for f in ("pickup", "delivery", "express")]
        self.assertEqual(discounts, [800, 800, 800])

    def test_other_fulfillment_values_are_still_rejected(self):
        for value in ("rush", "Express", "", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Fulfillment") as context:
                    self.service.quote("regular", NOTEBOOKS_2, value)
                self.assertIn("express", str(context.exception))


# ---------- Requirement 5: quotes, orders, history agree ----------
class ExpressOrderTests(ExpressTestCase):

    def test_quote_and_placed_express_order_agree(self):
        quote = self.service.quote("student", HOODIES_2, "express")
        order = self.service.place_order("student", HOODIES_2, "express")
        for key in PRICING_KEYS:
            with self.subTest(key=key):
                self.assertEqual(order[key], quote[key])

    def test_express_order_uses_normal_numbering_and_stock(self):
        order = self.service.place_order("regular", HOODIES_2, "express")
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(order["status"], "placed")
        self.assertEqual(self.stock_of("hoodie"), 3)

    def test_express_order_survives_lookup_reopen_and_cancel(self):
        placed = self.service.place_order("student", HOODIES_2, "express")
        reopened = OrderService(self.path)            # fresh service = reopened save file
        found = reopened.get_order(placed["order_id"])
        cancelled = reopened.cancel_order(placed["order_id"])
        for key in PRICING_KEYS:
            with self.subTest(key=key):
                self.assertEqual(found[key], placed[key])
                self.assertEqual(cancelled[key], placed[key])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(self.stock_of("hoodie"), 5)


# ---------- Requirements 1 and 7: commands and menu ----------
class ExpressInterfaceTests(ExpressTestCase):

    def run_cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = main(["--data", str(self.path), *args])
        return code, output.getvalue()

    def test_cli_express_quote_matches_client_example(self):
        code, out = self.run_cli("quote", "--customer", "student",
                                 "--fulfillment", "express", "--item", "hoodie:2")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total_cents"], 8400)

    def test_cli_still_rejects_unknown_fulfillment(self):
        with self.assertRaises(SystemExit) as context:
            self.run_cli("quote", "--fulfillment", "rush", "--item", "notebook:1")
        self.assertEqual(context.exception.code, 2)

    def test_cli_help_lists_express(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            main(["quote", "--help"])
        self.assertIn("express", output.getvalue())

    def test_menu_quote_with_express(self):
        answers = ["2", "student", "hoodie", "2", "", "express", "0"]
        output = io.StringIO()
        with mock.patch("builtins.input", side_effect=answers), \
                contextlib.redirect_stdout(output):
            run_menu(self.service)
        self.assertIn("Fulfillment: express", output.getvalue())
        self.assertIn("Delivery: $12.00", output.getvalue())
        self.assertIn("Total: $84.00", output.getvalue())

    def test_menu_fulfillment_prompt_mentions_express(self):
        answers = ["2", "regular", "notebook", "1", "", "", "0"]
        with mock.patch("builtins.input", side_effect=answers) as fake_input, \
                contextlib.redirect_stdout(io.StringIO()):
            run_menu(self.service)
        prompts = [call.args[0] for call in fake_input.call_args_list]
        self.assertTrue(any("express" in prompt for prompt in prompts))


if __name__ == "__main__":
    unittest.main()