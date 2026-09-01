import unittest
from rule_engine import EXEMPT, FAIL, PASS, REVIEW, RuleEngine


def complete(**overrides):
    data = {
        "full_text": "Biscuits Net Qty 500 g MRP Rs. 50 (inclusive of all taxes) Unit Sale Price: Rs. 0.10/g",
        "language_codes": ["en"],
        "manufacturer": {"name": "Example Foods Ltd", "address": "1 MG Road, Bengaluru 560001"},
        "generic_name": "Biscuits",
        "net_quantity": "500 g",
        "manufacture_month_year": "08/2026",
        "mrp_declaration": "MRP Rs. 50 (inclusive of all taxes)",
        "unit_sale_price": "Rs. 0.10 / g",
        "mrp_sticker_covers_printed_mrp": False,
        "consumer_care": {
            "name": "Consumer Officer",
            "address": "1 MG Road, Bengaluru 560001",
            "phone": "1800-123-4567",
            "email": "care@examplefoods.com",
        },
        "evidence": [
            {"field": "net_quantity", "text": "500 g", "box_2d": [100, 100, 150, 400], "confidence": "HIGH"},
            {"field": "mrp_declaration", "text": "MRP Rs. 50", "box_2d": [200, 100, 250, 400], "confidence": "HIGH"},
        ],
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

    def test_large_package_non_agricultural_is_exempt(self):
        report = RuleEngine().evaluate(complete(generic_name="Industrial Lubricant", net_quantity="30 kg"))
        self.assertEqual(report["outcome"], EXEMPT)

    def test_large_package_cement_agricultural_not_exempt(self):
        report = RuleEngine().evaluate(complete(generic_name="Portland Cement", net_quantity="50 kg"))
        self.assertNotEqual(report["outcome"], EXEMPT)

    def test_sticker_overlay_is_violation(self):
        report = RuleEngine().evaluate(complete(mrp_sticker_covers_printed_mrp=True))
        self.assertEqual(report["outcome"], FAIL)
        f = [x for x in report["findings"] if x["rule_id"] == "VIO-04"][0]
        self.assertEqual(f["outcome"], FAIL)

    def test_schedule_ii_non_standard_pack_size_is_violation(self):
        # 135g is not standard for Tea under Schedule II
        report = RuleEngine().evaluate(complete(generic_name="Tea", net_quantity="135 g"))
        self.assertEqual(report["outcome"], FAIL)
        f = [x for x in report["findings"] if x["rule_id"] == "VIO-05"][0]
        self.assertEqual(f["outcome"], FAIL)

    def test_schedule_ii_standard_pack_size_passes(self):
        # 250g is standard for Tea
        report = RuleEngine().evaluate(complete(generic_name="Tea", net_quantity="250 g"))
        f = [x for x in report["findings"] if x["rule_id"] == "VIO-05"][0]
        self.assertEqual(f["outcome"], PASS)

    def test_misleading_qualifier_is_violation(self):
        report = RuleEngine().evaluate(complete(full_text="Net weight when packed approx 500g"))
        self.assertEqual(report["outcome"], FAIL)
        f = [x for x in report["findings"] if x["rule_id"] == "VIO-03"][0]
        self.assertEqual(f["outcome"], FAIL)

    def test_subthreshold_unit_is_violation(self):
        report = RuleEngine().evaluate(complete(net_quantity="0.5 kg"))
        self.assertEqual(report["outcome"], FAIL)
        f = [x for x in report["findings"] if x["rule_id"] == "VIO-02"][0]
        self.assertEqual(f["outcome"], FAIL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
