import unittest

from rule_engine import EXEMPT, FAIL, PASS, REVIEW, RuleEngine


def complete(**overrides):
    data = {
        "full_text": "Biscuits Net Qty 500 g MRP Rs. 50 (inclusive of all taxes)",
        "language_codes": ["en"],
        "manufacturer": {"name": "Example Foods", "address": "1 MG Road, Bengaluru 560001"},
        "generic_name": "Biscuits", "net_quantity": "500 g", "manufacture_month_year": "08/2026",
        "mrp_declaration": "MRP Rs. 50 (inclusive of all taxes)",
        "consumer_care": {"name": "Example Care", "address": "1 MG Road Bengaluru 560001", "phone": "1800-123-4567", "email": "care@example.com"},
    }
    data.update(overrides)
    return data


class RulesTest(unittest.TestCase):
    def test_complete_package_has_no_violation(self):
        report = RuleEngine().evaluate(complete())
        self.assertEqual(report["outcome"], PASS)

    def test_missing_text_becomes_review_not_false_violation(self):
        report = RuleEngine().evaluate(complete(mrp_declaration=None))
        self.assertEqual(report["outcome"], REVIEW)

    def test_invalid_count_unit_is_violation(self):
        report = RuleEngine().evaluate(complete(net_quantity="1 dozen"))
        self.assertEqual(report["outcome"], FAIL)

    def test_clear_b2b_package_is_exempt(self):
        report = RuleEngine().evaluate(complete(not_for_retail_sale=True, industrial_or_institutional_only=True))
        self.assertEqual(report["outcome"], EXEMPT)

    def test_large_package_is_not_automatically_exempt(self):
        report = RuleEngine().evaluate(complete(net_quantity="30 kg"))
        self.assertNotEqual(report["outcome"], EXEMPT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
