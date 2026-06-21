from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ai_advent_agent.scenarios import scenario_assistant_personalization_demo
from ai_advent_agent.user_profile import (
    JsonUserProfileStore,
    UserProfile,
    UserProfileEventStore,
    UserProfiles,
    build_profile_prompt_message,
    normalize_profile_name,
)


class UserProfileTest(unittest.TestCase):
    def test_profile_name_normalization_and_validation(self) -> None:
        self.assertEqual(normalize_profile_name(" Concise_Engineer "), "concise_engineer")
        for value in ["", "bad name", "../secret", "русский"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_profile_name(value)

    def test_json_store_saves_schema_active_profile_and_trimmed_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "user_profiles.json"
            profiles = UserProfiles()
            profile = profiles.create("teacher")
            profile.set_field("language", " русский ")
            profile.set_preference("examples", " много коротких примеров ")
            JsonUserProfileStore(path).save(profiles)

            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded = JsonUserProfileStore(path).load()

            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(loaded.active_profile, "teacher")
            self.assertEqual(loaded.profiles["teacher"].language, "русский")
            self.assertEqual(
                loaded.profiles["teacher"].preferences,
                {"examples": "много коротких примеров"},
            )

    def test_invalid_json_types_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "user_profiles.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "active_profile": "",
                        "profiles": {"demo": {"name": "demo", "language": 42}},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                JsonUserProfileStore(path).load()

    def test_active_and_reset_policies(self) -> None:
        profiles = UserProfiles()
        concise = profiles.create("concise_engineer")
        concise.set_field("style", "кратко")
        profiles.create("teacher").set_field("style", "обучающе")
        profiles.use("concise_engineer")

        profiles.reset_active()

        self.assertEqual(profiles.active_profile, "concise_engineer")
        self.assertIn("concise_engineer", profiles.profiles)
        self.assertFalse(profiles.profiles["concise_engineer"].active)
        self.assertTrue(profiles.profiles["teacher"].active)

        profiles.reset_all()

        self.assertEqual(profiles.active_profile, "")
        self.assertEqual(profiles.profiles, {})

    def test_profile_events_are_append_only_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = UserProfileEventStore(Path(tmp) / "profile_events.jsonl")

            store.append(action="create_profile", profile="teacher")
            store.append(
                action="set_profile_preference",
                profile="teacher",
                key="examples",
                value="short",
            )

            events = store.load_all()
            self.assertEqual(
                [event["action"] for event in events],
                ["create_profile", "set_profile_preference"],
            )
            self.assertEqual(events[1]["key"], "examples")

    def test_build_profile_prompt_message_for_active_non_empty_profile(self) -> None:
        profiles = UserProfiles()
        profile = profiles.create("teacher")
        profile.set_field("language", "русский")
        profile.set_constraint("privacy", "не запрашивать секреты")

        message, fields_count, tokens = build_profile_prompt_message(profiles)

        self.assertIsNotNone(message)
        assert message is not None
        self.assertIn("User profile preferences", message["content"])
        self.assertIn("teacher", message["content"])
        self.assertEqual(fields_count, 2)
        self.assertGreater(tokens, 0)

    def test_empty_active_profile_does_not_build_prompt_message(self) -> None:
        profiles = UserProfiles()
        profiles.create("empty")

        message, fields_count, tokens = build_profile_prompt_message(profiles)

        self.assertIsNone(message)
        self.assertEqual(fields_count, 0)
        self.assertEqual(tokens, 0)

    def test_user_profile_from_dict_trims_values(self) -> None:
        profile = UserProfile.from_dict(
            {
                "name": "demo",
                "style": " concise ",
                "preferences": {" tone ": " direct "},
                "constraints": {" privacy ": " no secrets "},
            }
        )

        self.assertEqual(profile.style, "concise")
        self.assertEqual(profile.preferences, {"tone": "direct"})
        self.assertEqual(profile.constraints, {"privacy": "no secrets"})

    def test_assistant_personalization_demo_works_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            output_dir = tmp_dir / "agent-context"
            results_file = tmp_dir / "results" / "day-12-assistant-personalization.md"

            scenario_assistant_personalization_demo(
                output_dir=output_dir,
                results_file=results_file,
                context_window=10_000,
                max_tokens=500,
            )

            self.assertTrue((output_dir / "user_profiles.json").exists())
            self.assertTrue((output_dir / "profile_events.jsonl").exists())
            self.assertTrue((output_dir / "token_reports.jsonl").exists())
            self.assertTrue((output_dir / "prompt_no_profile.json").exists())
            self.assertTrue((output_dir / "prompt_concise_engineer.json").exists())
            self.assertTrue((output_dir / "prompt_teacher.json").exists())
            result_text = results_file.read_text(encoding="utf-8")
            self.assertIn("no_profile", result_text)
            self.assertIn("concise_engineer", result_text)
            self.assertIn("teacher", result_text)


if __name__ == "__main__":
    unittest.main()
