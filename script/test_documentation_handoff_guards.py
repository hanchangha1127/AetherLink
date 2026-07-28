from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from script import check_docs_hygiene
from script.check_copy_hygiene import macos_pairing_callback_wiring_failures


GENERIC_CALL = "model.requestPairingForUserInterface()"
REMOTE_CALL = "model.requestRemotePairingForUserInterface()"

VALID_PAIRING_VIEW = f"""
struct PairingView {{
    RemoteRelayRoutePanel(model: model) {{
        {REMOTE_CALL}
    }}

    private func generatePairingQR() {{
        {GENERIC_CALL}
    }}
}}
"""

VALID_CONTENT_VIEW = f"""
StatusView(
    onGenerateRelayQRCode: {{
        {GENERIC_CALL}
    }},
    onGenerateRemoteRelayQRCode: {{
        {REMOTE_CALL}
    }}
)

case .pairingQR:
    Button {{
        {GENERIC_CALL}
    }} label: {{
        Text("Pair")
    }}
"""

VALID_STATUS_VIEW = """
if shouldShowRouteDiagnosticsPanel(model: model) {
    RemoteRelayRoutePanel(
        model: model,
        onGenerateRemotePairingQRCode: onGenerateRemoteRelayQRCode
    )
}

private func performRuntimeOverviewAction(
    _ action: StatusRuntimeOverviewAction,
    scrollProxy: ScrollViewProxy
) {
    switch action {
    case .pairing:
            onGenerateRelayQRCode?()
    case .refreshProviders:
        break
    case .loadModels:
        break
    case .connectionRecovery:
        break
    }
}
"""

VALID_APP = f"""
case .pairingQR:
    Button {{
        {GENERIC_CALL}
    }} label: {{
        Text("Pair")
    }}
"""


class DocumentationHandoffGuardTests(unittest.TestCase):
    def failures(
        self,
        *,
        pairing: str = VALID_PAIRING_VIEW,
        content: str = VALID_CONTENT_VIEW,
        status: str = VALID_STATUS_VIEW,
        app: str = VALID_APP,
    ) -> list[str]:
        return macos_pairing_callback_wiring_failures(
            pairing,
            content,
            status,
            app,
        )

    def test_current_callback_wiring_passes(self) -> None:
        self.assertEqual(self.failures(), [])

    def test_pairing_main_and_recovery_swap_is_rejected_even_when_both_calls_remain(self) -> None:
        pairing = VALID_PAIRING_VIEW.replace(GENERIC_CALL, "GENERIC_PLACEHOLDER")
        pairing = pairing.replace(REMOTE_CALL, GENERIC_CALL)
        pairing = pairing.replace("GENERIC_PLACEHOLDER", REMOTE_CALL)

        failures = self.failures(pairing=pairing)

        self.assertTrue(any("generatePairingQR" in failure for failure in failures))
        self.assertTrue(any("Connection Recovery" in failure for failure in failures))

    def test_comments_and_strings_cannot_satisfy_pairing_wiring(self) -> None:
        pairing = f"""
RemoteRelayRoutePanel(model: model) {{
    {GENERIC_CALL}
    // {REMOTE_CALL}
    let remoteDecoy = "{REMOTE_CALL}"
}}

private func generatePairingQR() {{
    {REMOTE_CALL}
    /* {GENERIC_CALL} */
    let genericDecoy = #"{GENERIC_CALL}"#
}}
"""

        self.assertEqual(len(self.failures(pairing=pairing)), 2)

    def test_content_status_callback_swap_is_rejected(self) -> None:
        content = VALID_CONTENT_VIEW.replace(GENERIC_CALL, "GENERIC_PLACEHOLDER", 1)
        content = content.replace(REMOTE_CALL, GENERIC_CALL, 1)
        content = content.replace("GENERIC_PLACEHOLDER", REMOTE_CALL, 1)

        failures = self.failures(content=content)

        self.assertTrue(any("quick-action closure" in failure for failure in failures))
        self.assertTrue(any("recovery closure" in failure for failure in failures))

    def test_status_callback_swap_is_rejected(self) -> None:
        status = VALID_STATUS_VIEW.replace(
            "onGenerateRemotePairingQRCode: onGenerateRemoteRelayQRCode",
            "onGenerateRemotePairingQRCode: onGenerateRelayQRCode",
        ).replace(
            "onGenerateRelayQRCode?()",
            "onGenerateRemoteRelayQRCode?()",
        )

        failures = self.failures(status=status)

        self.assertTrue(any("Connection Recovery" in failure for failure in failures))
        self.assertTrue(any("overview pairing action" in failure for failure in failures))

    def test_toolbar_and_menu_remote_calls_are_rejected(self) -> None:
        case_anchor = "case .pairingQR:"
        content_prefix, content_case = VALID_CONTENT_VIEW.split(case_anchor, 1)
        content = content_prefix + case_anchor + content_case.replace(
            GENERIC_CALL,
            REMOTE_CALL,
            1,
        )
        app = VALID_APP.replace(GENERIC_CALL, REMOTE_CALL)

        failures = self.failures(content=content, app=app)

        self.assertTrue(any("toolbar" in failure for failure in failures))
        self.assertTrue(any("menu" in failure for failure in failures))

    def manifest_failures(self, document: dict[str, object]) -> list[str]:
        return self.manifest_failures_from_raw(json.dumps(document, indent=2))

    def manifest_failures_from_raw(self, raw_text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "manifest.json"
            manifest_path.write_text(raw_text, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "PHYSICAL_QR_OBSERVATION_MANIFEST",
                manifest_path,
            ):
                return check_docs_hygiene.physical_qr_observation_manifest_failures()

    def current_manifest(self) -> dict[str, object]:
        return json.loads(
            check_docs_hygiene.PHYSICAL_QR_OBSERVATION_MANIFEST.read_text(
                encoding="utf-8"
            )
        )

    def test_current_physical_qr_manifest_passes_closed_schema(self) -> None:
        self.assertEqual(
            check_docs_hygiene.physical_qr_observation_manifest_failures(),
            [],
        )

    def test_unknown_secret_manifest_key_is_rejected(self) -> None:
        document = self.current_manifest()
        document["pairingCode"] = "must-not-be-retained"

        failures = self.manifest_failures(document)

        self.assertTrue(any("closed schema mismatch" in failure for failure in failures))
        self.assertTrue(any("prohibited sensitive key pairingCode" in failure for failure in failures))

    def test_manifest_digest_drift_is_rejected_against_current_docs(self) -> None:
        document = self.current_manifest()
        qr_observation = document["qrObservation"]
        self.assertIsInstance(qr_observation, dict)
        qr_observation["payloadSha256"] = "0" * 64

        failures = self.manifest_failures(document)

        self.assertTrue(any("payloadSha256" in failure for failure in failures))
        self.assertTrue(any("must match" in failure for failure in failures))

    def test_duplicate_manifest_key_is_rejected(self) -> None:
        raw_text = check_docs_hygiene.PHYSICAL_QR_OBSERVATION_MANIFEST.read_text(
            encoding="utf-8"
        )
        needle = '"sensitiveMaterialIncluded": false'
        raw_text = raw_text.replace(needle, f"{needle},\n    {needle}", 1)

        failures = self.manifest_failures_from_raw(raw_text)

        self.assertTrue(any("duplicate JSON key" in failure for failure in failures))

    def test_full_pairing_uri_variant_in_manifest_value_is_rejected(self) -> None:
        document = self.current_manifest()
        source = document["source"]
        self.assertIsInstance(source, dict)
        source["laterSourceDelta"] = (
            "AETHERLINK : // pair ? pairing_code=must-not-be-retained"
        )

        failures = self.manifest_failures(document)

        self.assertTrue(any("credential-like string value" in failure for failure in failures))

    def local_release_failures_from_text(
        self,
        document_text: str,
        *,
        ledger_bytes: bytes | None = None,
        g0_text: str | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            document_path = Path(temporary_directory) / "release.md"
            document_path.write_text(document_text, encoding="utf-8")
            missing_archive = Path(temporary_directory) / "missing-archive"
            ledger_path = Path(temporary_directory) / "version-ledger.tsv"
            ledger_path.write_bytes(
                ledger_bytes
                if ledger_bytes is not None
                else check_docs_hygiene.LOCAL_RELEASE_LEDGER.read_bytes()
            )
            g0_path = Path(temporary_directory) / "decision-v1.json"
            g0_path.write_text(
                g0_text
                if g0_text is not None
                else check_docs_hygiene.LOCAL_RELEASE_G0_DECISION.read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            with (
                patch.object(
                    check_docs_hygiene,
                    "LOCAL_RELEASE_DOC",
                    document_path,
                ),
                patch.object(
                    check_docs_hygiene,
                    "LOCAL_RELEASE_ARCHIVE_DIR",
                    missing_archive,
                ),
                patch.object(
                    check_docs_hygiene,
                    "LOCAL_RELEASE_LEDGER",
                    ledger_path,
                ),
                patch.object(
                    check_docs_hygiene,
                    "LOCAL_RELEASE_G0_DECISION",
                    g0_path,
                ),
            ):
                return check_docs_hygiene.local_release_document_failures()

    def local_release_transition_failures_from_text(
        self,
        document_text: str,
        *,
        ledger_bytes: bytes | None = None,
        g0_text: str | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            ledger_path = Path(temporary_directory) / "version-ledger.tsv"
            ledger_path.write_bytes(
                ledger_bytes
                if ledger_bytes is not None
                else check_docs_hygiene.LOCAL_RELEASE_LEDGER.read_bytes()
            )
            g0_path = Path(temporary_directory) / "decision-v1.json"
            g0_path.write_text(
                g0_text
                if g0_text is not None
                else check_docs_hygiene.LOCAL_RELEASE_G0_DECISION.read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            with (
                patch.object(
                    check_docs_hygiene,
                    "LOCAL_RELEASE_LEDGER",
                    ledger_path,
                ),
                patch.object(
                    check_docs_hygiene,
                    "LOCAL_RELEASE_G0_DECISION",
                    g0_path,
                ),
            ):
                return (
                    check_docs_hygiene.local_release_transition_fixture_failures(
                        document_text
                    )
                )

    def local_release_provider_failures_from_text(
        self,
        document_text: str,
        *,
        g0_text: str | None = None,
    ) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            g0_path = Path(temporary_directory) / "decision-v1.json"
            g0_path.write_text(
                g0_text
                if g0_text is not None
                else check_docs_hygiene.LOCAL_RELEASE_G0_DECISION.read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_G0_DECISION",
                g0_path,
            ):
                return (
                    check_docs_hygiene.local_release_provider_fixture_failures(
                        document_text
                    )
                )

    def test_current_local_release_document_passes_identity_contract(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )

        self.assertEqual(
            self.local_release_failures_from_text(document_text),
            [],
        )

    def test_current_local_release_document_cross_checks_archive_when_present(
        self,
    ) -> None:
        if not check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR.is_dir():
            self.skipTest("local release archive is not present")

        self.assertEqual(
            check_docs_hygiene.local_release_document_failures(),
            [],
        )

    def test_every_local_release_identity_mutation_is_rejected(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        identity_snippets = (
            f"`{check_docs_hygiene.LOCAL_RELEASE_ID}`",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MEMBER_COUNT} payload members",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT}-file source inventory",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SIZE:,} bytes",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE:,} bytes",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SHA256}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_SHA256}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MACOS_UUID}`",
            *(
                f"{size:,} bytes"
                for size, _ in check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MEMBERS.values()
            ),
            *(
                f"`{sha256}`"
                for _, sha256 in check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MEMBERS.values()
            ),
        )

        for identity_snippet in identity_snippets:
            with self.subTest(identity=identity_snippet):
                mutated = document_text.replace(
                    identity_snippet,
                    "INVALID_RELEASE_IDENTITY",
                )
                self.assertNotEqual(mutated, document_text)
                self.assertTrue(
                    any(
                        "missing exact" in failure
                        for failure in self.local_release_failures_from_text(
                            mutated
                        )
                    ),
                    f"mutated release identity {identity_snippet!r} was accepted",
                )

    def test_local_release_transition_fixture_mutations_are_rejected(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        mutations = {
            "boolean_type_confusion": (
                '"inPlaceUpgradeSupported": false',
                '"inPlaceUpgradeSupported": 0',
            ),
            "predecessor_invented": (
                '"productionPredecessor": null',
                '"productionPredecessor": "aetherlink-0.9.0+9"',
            ),
            "n_minus_one_overclaim": (
                '"status": "unproven-no-prior-production-release"',
                '"status": "qualified"',
            ),
            "upgrade_path_overclaim": (
                '"upgradePathTested": false',
                '"upgradePathTested": true',
            ),
            "migration_overclaim": (
                '"stateMigrationSupported": false',
                '"stateMigrationSupported": true',
            ),
            "wrong_transition": (
                '"requiredAction": "clean-install-and-fresh-pair"',
                '"requiredAction": "in-place-upgrade"',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1',
                '"schemaVersion": 1,\n  "schemaVersion": 1',
            ),
            "missing_start_marker": (
                check_docs_hygiene.LOCAL_RELEASE_TRANSITION_FIXTURE_START,
                "<!-- removed-transition-fixture-start -->",
            ),
            "missing_end_marker": (
                check_docs_hygiene.LOCAL_RELEASE_TRANSITION_FIXTURE_END,
                "<!-- removed-transition-fixture-end -->",
            ),
        }

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated = document_text.replace(before, after)
                self.assertNotEqual(mutated, document_text)
                failures = self.local_release_transition_failures_from_text(
                    mutated
                )
                expected_failure = (
                    "expected exactly one"
                    if label in ("missing_start_marker", "missing_end_marker")
                    else (
                        "invalid release-transition fixture JSON"
                        if label == "duplicate_root_key"
                        else "must match the canonical first-lineage schema"
                    )
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    f"transition fixture mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

    def test_local_release_transition_fixture_rejects_ledger_drift(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        drifted_ledger = (
            b"build_number\tmarketing_version\n"
            b"1\t1.0.0\n"
            b"2\t1.0.0\n"
        )

        failures = self.local_release_transition_failures_from_text(
            document_text,
            ledger_bytes=drifted_ledger,
        )

        self.assertTrue(
            any(
                "current entry differs from the local release transition fixture"
                in failure
                for failure in failures
            )
        )

    def test_local_release_transition_fixture_rejects_malformed_middle_ledger_row(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        malformed_ledger = (
            b"build_number\tmarketing_version\n"
            b"MALFORMED\n"
            b"1\t1.0.0\n"
        )

        failures = self.local_release_transition_failures_from_text(
            document_text,
            ledger_bytes=malformed_ledger,
        )

        self.assertTrue(
            any(
                "cannot cross-check local release transition fixture" in failure
                for failure in failures
            )
        )

    def test_local_release_transition_fixture_rejects_g0_migration_drift(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        g0 = json.loads(
            check_docs_hygiene.LOCAL_RELEASE_G0_DECISION.read_text(
                encoding="utf-8"
            )
        )
        g0["releasePolicy"]["android"]["currentDebugDataMigration"] = (
            "in_place_upgrade"
        )

        failures = self.local_release_transition_failures_from_text(
            document_text,
            g0_text=json.dumps(g0, indent=2, sort_keys=True),
        )

        self.assertTrue(
            any(
                "non-security release version, identity, migration, or "
                "compatibility fields differ" in failure
                for failure in failures
            )
        )

    def test_local_release_transition_fixture_rejects_g0_policy_version_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        g0 = json.loads(
            check_docs_hygiene.LOCAL_RELEASE_G0_DECISION.read_text(
                encoding="utf-8"
            )
        )
        g0["releasePolicy"]["versioning"]["marketingVersion"] = "9.9.9"

        failures = self.local_release_transition_failures_from_text(
            document_text,
            g0_text=json.dumps(g0, indent=2, sort_keys=True),
        )

        self.assertTrue(
            any(
                "non-security release version, identity, migration, or "
                "compatibility fields differ" in failure
                for failure in failures
            )
        )

    def test_local_release_provider_fixture_mutations_are_rejected(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        mutations = {
            "boolean_type_confusion": (
                '"qualified": false,\n      "releaseDate": "2026-07-27"',
                '"qualified": 0,\n      "releaseDate": "2026-07-27"',
            ),
            "current_candidate_overclaim": (
                '"qualified": false,\n      "releaseDate": "2026-07-27"',
                '"qualified": true,\n      "releaseDate": "2026-07-27"',
            ),
            "previous_candidate_overclaim": (
                '"qualified": false,\n      "releaseDate": "2026-07-25"',
                '"qualified": true,\n      "releaseDate": "2026-07-25"',
            ),
            "minimum_version_invented": (
                '"minimumSupportedVersion": null',
                '"minimumSupportedVersion": "0.4.19"',
            ),
            "local_version_drift": (
                '"version": "0.4.17-beta+3"',
                '"version": "0.4.20"',
            ),
            "official_version_drift": (
                '"version": "0.32.5"',
                '"version": "0.32.6"',
            ),
            "official_release_date_drift": (
                '"releaseDate": "2026-07-22"',
                '"releaseDate": "2026-07-23"',
            ),
            "official_archive_hash_drift": (
                '"darwinArchiveSha256": '
                '"5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"',
                '"darwinArchiveSha256": '
                '"0000000000000000000000000000000000000000000000000000000000000000"',
            ),
            "isolated_restart_drift": (
                '"restartPassed": true',
                '"restartPassed": false',
            ),
            "recorded_date_drift": (
                '"recordedDate": "2026-07-28"',
                '"recordedDate": "2026-07-29"',
            ),
            "isolated_run_count_drift": (
                '"executed": 4',
                '"executed": 3',
            ),
            "test_count_type_confusion": (
                '"executed": 71',
                '"executed": 71.0',
            ),
            "evidence_overclaim": (
                '"exact-version-isolated-ollama-adapter-health-empty-catalog-'
                'restart-plus-focused-default-tests-no-live-chat-or-model-'
                'lifecycle"',
                '"full-live-provider-qualification"',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "tests"',
                '"schemaVersion": 1,\n  "schemaVersion": 1,\n  "tests"',
            ),
        }

        start_index = document_text.index(
            check_docs_hygiene.LOCAL_RELEASE_PROVIDER_FIXTURE_START
        )
        end_index = document_text.index(
            check_docs_hygiene.LOCAL_RELEASE_PROVIDER_FIXTURE_END
        ) + len(check_docs_hygiene.LOCAL_RELEASE_PROVIDER_FIXTURE_END)
        fixture_block = document_text[start_index:end_index]

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated_block = fixture_block.replace(before, after, 1)
                self.assertNotEqual(mutated_block, fixture_block)
                mutated = (
                    document_text[:start_index]
                    + mutated_block
                    + document_text[end_index:]
                )
                failures = self.local_release_provider_failures_from_text(
                    mutated
                )
                expected_failure = (
                    "invalid provider-compatibility fixture JSON"
                    if label == "duplicate_root_key"
                    else "must match the canonical recorded-date schema"
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    f"provider fixture mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

        marker_mutations = {
            "missing_start_marker": (
                check_docs_hygiene.LOCAL_RELEASE_PROVIDER_FIXTURE_START,
                "<!-- removed-provider-fixture-start -->",
            ),
            "missing_end_marker": (
                check_docs_hygiene.LOCAL_RELEASE_PROVIDER_FIXTURE_END,
                "<!-- removed-provider-fixture-end -->",
            ),
        }
        for label, (before, after) in marker_mutations.items():
            with self.subTest(label=label):
                mutated = document_text.replace(before, after, 1)
                failures = self.local_release_provider_failures_from_text(
                    mutated
                )
                self.assertTrue(
                    any("expected exactly one" in failure for failure in failures),
                    f"provider fixture mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

    def test_local_release_provider_fixture_rejects_g0_policy_drift(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        original_g0 = check_docs_hygiene.LOCAL_RELEASE_G0_DECISION.read_text(
            encoding="utf-8"
        )
        mutations = {
            "provider_id": ("id", "ollama-drift"),
            "minimum_version": ("minimumSupportedVersion", "0.32.4"),
            "release_policy": ("releasePolicy", "current_only"),
            "provider_access": ("access", "client_direct"),
        }

        for label, (field, value) in mutations.items():
            with self.subTest(label=label):
                g0 = json.loads(original_g0)
                ollama = next(
                    provider
                    for provider in g0["productScope"]["providers"]
                    if provider["id"] == "ollama"
                )
                ollama[field] = value
                failures = self.local_release_provider_failures_from_text(
                    document_text,
                    g0_text=json.dumps(g0, indent=2, sort_keys=True),
                )
                self.assertTrue(
                    any(
                        "non-security provider IDs, runtime-host access, "
                        "minimum versions, or release policies differ"
                        in failure
                        for failure in failures
                    ),
                    f"G0 provider drift {label!r} was accepted: {failures!r}",
                )


if __name__ == "__main__":
    unittest.main()
