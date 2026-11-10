import os
import sys
import unittest
import urllib.error
from email.message import Message
from io import BytesIO
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from automation_common import automation_metadata, parse_federal_bill
from build import add_reciprocal_relations
from discover_openstates import request_json
from discover_weekly import classify, discover_federal, recent_govinfo_matches
from sync_weekday import lifecycle_from_actions, values


class AutomationTests(unittest.TestCase):
    def test_related_measures_are_mirrored(self):
        records = [
            {
                "record_id": "house-bill",
                "measure_id": "H.R. 1",
                "related_measures": [
                    {"record_id": "senate-bill", "measure_id": "S. 1", "relationship": "companion"}
                ],
            },
            {"record_id": "senate-bill", "measure_id": "S. 1"},
        ]
        result = add_reciprocal_relations(records)
        self.assertEqual(
            result[1]["related_measures"],
            [{"record_id": "house-bill", "measure_id": "H.R. 1", "relationship": "companion"}],
        )

    def test_parse_congress_bill_identity(self):
        record = {"congress_url": "https://www.congress.gov/bill/119th-congress/house-bill/1736"}
        self.assertEqual(parse_federal_bill(record), (119, "hr", 1736))

    def test_parse_congress_joint_resolution_identity(self):
        for chamber, bill_type, number in (("house", "hjres", 187), ("senate", "sjres", 198)):
            with self.subTest(chamber=chamber):
                url = f"https://www.congress.gov/bill/119th-congress/{chamber}-joint-resolution/{number}"
                self.assertEqual(parse_federal_bill({"official_url": url}), (119, bill_type, number))

    def test_lifecycle_is_conservative(self):
        self.assertEqual(lifecycle_from_actions([{"text": "Signed by President."}], "passed_chamber"), "enacted")
        self.assertEqual(lifecycle_from_actions([], "referred"), "referred")
        self.assertEqual(lifecycle_from_actions([{"text": "Committee reported the bill."}], "floor"), "floor")

    def test_historical_actions_preserve_terminal_lifecycle(self):
        for terminal in ("inactive", "failed", "withdrawn"):
            with self.subTest(terminal=terminal):
                self.assertEqual(lifecycle_from_actions([{"text": "Passed Senate."}], terminal), terminal)

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

    @patch("discover_weekly.request_json")
    @patch("discover_weekly.congress_json")
    def test_federal_discovery_paginates_and_combines_title_and_full_text(self, congress, govinfo):
        congress.side_effect = [
            {
                "bills": [{"congress": 119, "type": "HR", "number": "1", "title": "Air Safety Act"}],
                "pagination": {"count": 2, "next": "https://api.congress.gov/v3/bill?offset=1"},
            },
            {
                "bills": [{"congress": 119, "type": "S", "number": "2", "title": "AI Safety Act"}],
                "pagination": {"count": 2},
            },
        ]
        govinfo.side_effect = [
            {"results": [
                {"packageId": "BILLS-119hr1ih", "title": "Air Safety Act"},
                {"packageId": "BILLS-119hr1rh", "title": "Air Safety Act"},
            ], "offsetMark": "next-page", "count": 4},
            {"results": [
                {"packageId": "BILLS-119hr3ih", "title": "National Defense Authorization Act"},
                {"packageId": "BILLS-119s2is", "title": "AI Safety Act"},
            ], "count": 4},
        ]

        candidates, _ = discover_federal("test-congress", "test-govinfo", 8)
        by_bill = {item["measure_id"]: item for item in candidates}
        self.assertEqual(congress.call_args_list[1].kwargs["offset"], 1)
        self.assertEqual(govinfo.call_args_list[1].kwargs["payload"]["offsetMark"], "next-page")
        self.assertEqual(by_bill["H.R. 1"]["discovery_sources"], ["govinfo-full-text"])
        self.assertEqual(len(by_bill["H.R. 1"]["govinfo_text_matches"]), 2)
        self.assertEqual(by_bill["H.R. 3"]["official_url"], "https://www.congress.gov/bill/119th-congress/house-bill/3")
        self.assertEqual(by_bill["S. 2"]["discovery_sources"], ["congress-title", "govinfo-full-text"])

    @patch("discover_weekly.request_json")
    def test_govinfo_discovery_rejects_truncated_pagination(self, govinfo):
        govinfo.return_value = {"results": [], "count": 10}
        with self.assertRaisesRegex(RuntimeError, "before returning"):
            recent_govinfo_matches("test-key", "2026-11-01T00:00:00Z", "2026-11-09T00:00:00Z")

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
