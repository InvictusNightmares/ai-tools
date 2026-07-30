#!/usr/bin/env python3

import pathlib
import re
import unittest


SQL_PATH = pathlib.Path(__file__).with_name("register-sub2api-account.sql")


class RegistrationSQLTest(unittest.TestCase):
    def setUp(self):
        self.sql = SQL_PATH.read_text(encoding="utf-8")

    def test_registration_preserves_existing_credentials_and_model_aliases(self):
        self.assertNotRegex(
            self.sql,
            re.compile(r"credentials\s*=\s*jsonb_build_object", re.I),
        )
        self.assertIn(
            "COALESCE(credentials, '{}'::jsonb)",
            self.sql,
        )
        self.assertIn(
            "COALESCE(credentials->'model_mapping', '{}'::jsonb)",
            self.sql,
        )
        self.assertIn("'claude-opus-5'", self.sql)
        self.assertIn("'claude-opus-5[1m]'", self.sql)

    def test_registration_requires_the_target_group(self):
        self.assertIn("required active group", self.sql)
        self.assertIn("required account", self.sql)
        self.assertIn("model_mapping must be a JSON object", self.sql)
        self.assertIn("RAISE EXCEPTION", self.sql)


if __name__ == "__main__":
    unittest.main()
