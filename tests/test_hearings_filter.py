import unittest

from app.scrapers.hearings.hearings_filter import HearingsFilter


def _record(**overrides):
    record = {
        "source_id": "1",
        "title": "Titel",
        "source_url": "https://example.test/1",
        "place_text": "",
    }
    record.update(overrides)
    return record


class HearingsFilterTests(unittest.TestCase):
    def test_flags_regional_plan_and_substation_hearings(self):
        records = HearingsFilter().apply(
            [
                _record(
                    title=(
                        "Öffentlichkeitsbeteiligung zur "
                        "Änderung der Regionalplanung"
                    ),
                ),
                _record(
                    source_id="2",
                    title=(
                        "Offenlage zur Erweiterung des "
                        "Umspannwerks"
                    ),
                ),
                _record(
                    source_id="3",
                    title="Kommunaler Haushalt Buchenbach",
                ),
            ]
        )

        self.assertEqual(
            [record["relevant"] for record in records],
            [True, True, False],
        )

    def test_equipment_name_without_expansion_is_not_relevant(self):
        records = HearingsFilter().apply(
            [
                _record(
                    title="Anhörung zum Umspannwerk",
                )
            ]
        )

        self.assertFalse(records[0]["relevant"])


if __name__ == "__main__":
    unittest.main()
