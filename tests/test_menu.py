"""Characterization tests for menu.run_menu(), added before Refactoring 3.
They record current behaviour so the menu split can be verified."""

import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from supplydesk.menu import run_menu
from supplydesk.service import OrderService


class MenuTestCase(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def run_with(self, answers):
        """Run the menu with scripted input; return (exit code, printed text)."""
        output = io.StringIO()
        with mock.patch("builtins.input", side_effect=answers), \
                contextlib.redirect_stdout(output):
            code = run_menu(self.service)
        return code, output.getvalue()


class MenuBehaviourTests(MenuTestCase):

    def test_option_1_shows_catalog(self):
        code, out = self.run_with(["1", "0"])
        self.assertEqual(code, 0)
        self.assertIn("Product ID", out)
        self.assertIn("notebook", out)

    def test_option_3_confirmed_places_order(self):
        code, out = self.run_with(["3", "regular", "notebook", "2", "", "", "y", "0"])
        self.assertEqual(code, 0)
        self.assertIn("ORD-0001 - placed", out)
        self.assertEqual(len(self.service.list_orders()), 1)

    def test_option_3_declined_places_nothing(self):
        code, out = self.run_with(["3", "regular", "notebook", "2", "", "", "n", "0"])
        self.assertIn("Order not placed.", out)
        self.assertFalse(self.path.exists())

    def test_option_4_with_no_orders(self):
        code, out = self.run_with(["4", "0"])
        self.assertIn("No orders yet.", out)

    def test_option_5_finds_existing_order(self):
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        code, out = self.run_with(["5", "ORD-0001", "0"])
        self.assertIn("ORD-0001 - placed", out)

    def test_option_6_confirmed_cancels_order(self):
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        code, out = self.run_with(["6", "ORD-0001", "y", "0"])
        self.assertIn("ORD-0001 - cancelled", out)

    def test_option_6_declined_keeps_order(self):
        self.service.place_order("regular", [{"product_id": "notebook", "quantity": 1}])
        code, out = self.run_with(["6", "ORD-0001", "n", "0"])
        self.assertIn("Cancellation abandoned.", out)
        self.assertEqual(self.service.get_order("ORD-0001")["status"], "placed")

    def test_unknown_choice_shows_hint_and_keeps_running(self):
        code, out = self.run_with(["9", "0"])
        self.assertIn("Choose a number from 0 to 6.", out)
        self.assertEqual(code, 0)

    def test_service_error_returns_to_menu(self):
        code, out = self.run_with(["5", "ORD-9999", "0"])
        self.assertIn("Error: Unknown order: ORD-9999", out)
        self.assertIn("Returning to the menu.", out)
        self.assertEqual(code, 0)

    def test_end_of_input_exits_cleanly(self):
        code, out = self.run_with([EOFError()])
        self.assertEqual(code, 0)
        self.assertIn("Goodbye.", out)


if __name__ == "__main__":
    unittest.main()