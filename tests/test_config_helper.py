"""Tests for bob_dev.helpers.config_helper."""

from __future__ import annotations

import os

import pytest

from bob_dev.helpers.config_helper import update_env_file


class TestUpdateEnvFile:
    def test_creates_file_with_new_key(self, tmp_path):
        env_path = tmp_path / ".env"
        update_env_file("MY_KEY", "my_value", env_path)
        assert env_path.exists()
        assert "MY_KEY=my_value" in env_path.read_text()

    def test_updates_existing_key_in_place(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("MY_KEY=old_value\n")
        update_env_file("MY_KEY", "new_value", env_path)
        content = env_path.read_text()
        assert "MY_KEY=new_value" in content
        assert "old_value" not in content

    def test_does_not_duplicate_key(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("MY_KEY=old\n")
        update_env_file("MY_KEY", "updated", env_path)
        assert env_path.read_text().count("MY_KEY=") == 1

    def test_appends_new_key_to_existing_file(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("EXISTING=123\n")
        update_env_file("NEW_KEY", "new_value", env_path)
        content = env_path.read_text()
        assert "EXISTING=123" in content
        assert "NEW_KEY=new_value" in content

    def test_sets_os_environ(self, tmp_path):
        env_path = tmp_path / ".env"
        key = "TEST_BOB_CFG_KEY_UNIQUE"
        update_env_file(key, "test_123", env_path)
        assert os.environ.get(key) == "test_123"
        del os.environ[key]

    def test_overwrites_os_environ_with_new_value(self, tmp_path):
        env_path = tmp_path / ".env"
        key = "TEST_BOB_OVERWRITE_KEY"
        os.environ[key] = "original"
        update_env_file(key, "overwritten", env_path)
        assert os.environ.get(key) == "overwritten"
        del os.environ[key]

    def test_multiple_keys_in_file(self, tmp_path):
        env_path = tmp_path / ".env"
        update_env_file("KEY_A", "val_a", env_path)
        update_env_file("KEY_B", "val_b", env_path)
        content = env_path.read_text()
        assert "KEY_A=val_a" in content
        assert "KEY_B=val_b" in content

    def test_only_updates_matching_prefix(self, tmp_path):
        """KEY and KEY_EXTRA should not collide during prefix matching."""
        env_path = tmp_path / ".env"
        env_path.write_text("KEY=original\nKEY_EXTRA=stays\n")
        update_env_file("KEY", "changed", env_path)
        content = env_path.read_text()
        assert "KEY=changed" in content
        assert "KEY_EXTRA=stays" in content
