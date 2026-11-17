Fixtures for the view tests, in `web/src/test/fixtures/`: `stalled.json`, `writing.json`, `empty.json`, `new-check.json`.
Each is one `Dashboard` JSON body. `tests/test_web.py::test_front_end_fixtures_are_valid_dashboards`
parses each one with `Dashboard.model_validate_json`.
