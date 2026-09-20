import os
import sys
import unittest
import urllib.error
from email.message import Message
from io import BytesIO
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from automation_common import automation_metadata, parse_federal_bill
from discover_openstates import request_json
from discover_weekly import classify
from sync_weekday import lifecycle_from_actions, values


class AutomationTests(unittest.TestCase):
    def test_parse_congress_bill_identity(self):
        record = {"congress_url": "https://www.congress.gov/bill/119th-congress/house-bill/1736"}
        self.assertEqual(parse_federal_bill(record), (119, "hr", 1736))

    def test_lifecycle_is_conservative(self):
        self.assertEqual(lifecycle_from_actions([{"text": "Signed by President."}], "passed_chamber"), "enacted")
        self.assertEqual(lifecycle_from_actions([], "referred"), "referred")

    def test_objective_values_preserve_source_status(self):
        record = {"title": "Old", "sponsor": "Old Sponsor", "committees": [], "lifecycle_status": "referred"}
        bill = {"title": "New", "introducedDate": "2026-01-02", "sponsors": [{"firstName": "Ada", "lastName": "Lovelace"}]}
        result = values(record, bill, [{"text": "Referred to committee", "actionDate": "2026-01-03"}], 301, [{"name": "Committee A"}])
        self.assertEqual(result["sponsor"], "Ada Lovelace")
        self.assertEqual(result["cosponsor_count"], 301)
        self.assertNotIn("status", result)

    @patch.dict(os.environ, {}, clear=True)
    def test_no_ai_key_fails_safe_with_review_flags(self):
        result = classify([{"jurisdiction_level": "state", "title": "Candidate"}])[0]
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(result["classification"], "unreviewed")
        self.assertIn("official-source-verification-required", result["agent_flags"])

    def test_automation_metadata_clamps_confidence(self):
        result = automation_metadata(2, ["review"], "test")
        self.assertEqual(result["agent_confidence"], 1.0)
        self.assertTrue(result["requires_human_review"])

    @patch("discover_openstates.time.sleep")
    @patch("discover_openstates.urllib.request.urlopen")
    def test_openstates_retries_rate_limit(self, urlopen, sleep):
        headers = Message()
        headers["Retry-After"] = "3"
        urlopen.side_effect = [
            urllib.error.HTTPError("https://example.test", 429, "Too Many Requests", headers, None),
            BytesIO(b'{"results": []}'),
        ]

        self.assertEqual(request_json("https://example.test", "key"), {"results": []})
        sleep.assert_called_once_with(3.0)

    @patch("discover_openstates.time.sleep")
    @patch("discover_openstates.urllib.request.urlopen")
    def test_openstates_does_not_retry_client_errors(self, urlopen, sleep):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://example.test", 401, "Unauthorized", Message(), None
        )

        with self.assertRaises(urllib.error.HTTPError):
            request_json("https://example.test", "bad-key")
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
