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

    def test_current_release_qa_readback_rejects_stale_claims(
        self,
    ) -> None:
        document_text = check_docs_hygiene.QA_EVIDENCE_DOC.read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            check_docs_hygiene.current_release_qa_evidence_failures(
                document_text
            ),
            [],
        )
        missing_current = document_text.replace(
            "The Build 9 archive remains the latest ledger entry but its "
            "source-bound snapshot predates the current two-stage reranker "
            "worktree",
            "The Build 9 readback marker was removed.",
            1,
        )
        self.assertTrue(
            check_docs_hygiene.current_release_qa_evidence_failures(
                missing_current
            )
        )
        stale = (
            document_text
            + "\n"
            + check_docs_hygiene.QA_STALE_RELEASE_READBACK_MARKERS[0]
            + "."
        )
        self.assertTrue(
            check_docs_hygiene.current_release_qa_evidence_failures(
                stale
            )
        )

    def test_release_readback_commands_require_correct_history_mode(
        self,
    ) -> None:
        documents = {
            str(path.relative_to(check_docs_hygiene.ROOT)): path.read_text(
                encoding="utf-8"
            )
            for path in check_docs_hygiene.RELEASE_READBACK_COMMAND_DOCS
        }
        self.assertEqual(
            check_docs_hygiene.release_readback_command_mode_failures(
                documents
            ),
            [],
        )

        progress_path = "docs/progress.md"
        historical_command = (
            "--archive-dir "
            "dist/releases/aetherlink-1.0.0+7-local-v1 --historical"
        )
        without_historical = dict(documents)
        without_historical[progress_path] = documents[progress_path].replace(
            historical_command,
            historical_command.removesuffix(" --historical"),
            1,
        )
        self.assertTrue(
            any(
                "historical Build 7" in failure
                for failure in (
                    check_docs_hygiene
                    .release_readback_command_mode_failures(
                        without_historical
                    )
                )
            )
        )

        current_command = (
            "--archive-dir "
            "dist/releases/aetherlink-1.0.0+9-local-v1"
        )
        current_as_historical = dict(documents)
        current_as_historical[progress_path] = documents[
            progress_path
        ].replace(
            current_command,
            current_command + " --historical",
            1,
        )
        self.assertTrue(
            any(
                "current Build 9" in failure
                for failure in (
                    check_docs_hygiene
                    .release_readback_command_mode_failures(
                        current_as_historical
                    )
                )
            )
        )

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
                    "LOCAL_RELEASE_CURRENT_DOC",
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

    def local_release_ollama_runner_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene.local_release_ollama_runner_fixture_failures(
                document_text
            )
        )

    def local_release_ollama_model_backed_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene.local_release_ollama_model_backed_fixture_failures(
                document_text
            )
        )

    def local_release_ollama_additional_chat_shape_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene
            .local_release_ollama_additional_chat_shape_fixture_failures(
                document_text
            )
        )

    def local_release_ollama_embedding_model_backed_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        checker = getattr(
            check_docs_hygiene,
            "local_release_ollama_embedding_model_backed_fixture_failures",
        )
        return checker(document_text)

    def local_release_ollama_embedding_semantic_quality_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene
            .local_release_ollama_embedding_semantic_quality_fixture_failures(
                document_text
            )
        )

    def local_release_ollama_embedding_multilingual_semantic_quality_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene
            .local_release_ollama_embedding_multilingual_semantic_quality_fixture_failures(
                document_text
            )
        )

    def local_release_ollama_vision_model_backed_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene.local_release_ollama_vision_model_backed_fixture_failures(
                document_text
            )
        )

    def local_release_ollama_duration_observation_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene
            .local_release_ollama_duration_observation_fixture_failures(
                document_text
            )
        )

    def local_release_ollama_live_fault_injection_failures_from_text(
        self,
        document_text: str,
    ) -> list[str]:
        return (
            check_docs_hygiene
            .local_release_ollama_live_fault_injection_fixture_failures(
                document_text
            )
        )

    def test_current_local_release_document_passes_identity_contract(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC.read_text(
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

    def test_macos_packaged_lifecycle_result_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene.macos_packaged_lifecycle_evidence_failures(),
            [],
        )
        result = json.loads(
            check_docs_hygiene.MACOS_PACKAGED_LIFECYCLE_RESULT.read_text(
                encoding="utf-8"
            )
        )
        result["runs"][0]["finishedLaunching"] = 1
        mutated = (
            json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

        failures = (
            check_docs_hygiene.macos_packaged_lifecycle_evidence_failures(
                mutated
            )
        )

        self.assertTrue(any("expected identity" in failure for failure in failures))
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )

    def test_historical_release_documents_follow_current_ledger_record(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene.historical_local_release_document_failures(),
            [],
        )

    def test_historical_release_document_stale_current_pointers_are_rejected(
        self,
    ) -> None:
        ledger_bytes = check_docs_hygiene.LOCAL_RELEASE_LEDGER.read_bytes()
        entries = check_docs_hygiene.parse_release_version_ledger(
            ledger_bytes
        )
        current = entries[-1]
        previous = entries[-2]
        documents = {
            entry.build_number: (
                check_docs_hygiene.ROOT
                / "docs"
                / "releases"
                / (
                    f"{entry.marketing_version}-build-"
                    f"{entry.build_number}-local-v1.md"
                )
            ).read_text(encoding="utf-8")
            for entry in entries[:-1]
        }
        current_doc = (
            "docs/releases/"
            f"{current.marketing_version}-build-"
            f"{current.build_number}-local-v1.md"
        )
        previous_doc = (
            "docs/releases/"
            f"{previous.marketing_version}-build-"
            f"{previous.build_number}-local-v1.md"
        )
        oldest = entries[0]
        oldest_release_id = (
            f"aetherlink-{oldest.marketing_version}"
            f"+{oldest.build_number}-local-v1"
        )
        previous_release_id = (
            f"aetherlink-{previous.marketing_version}"
            f"+{previous.build_number}-local-v1"
        )
        oldest_build = entries[0].build_number
        mutations = {
            "additional_status": (
                (
                    "Status: superseded local release-engineering candidate, "
                    "not a production release."
                ),
                (
                    "Status: superseded local release-engineering candidate, "
                    "not a production release.\n"
                    "Status: local release-engineering candidate, "
                    "not a production release."
                ),
                "historical status must appear exactly once",
            ),
            "additional_release_id": (
                f"Release ID: `{oldest_release_id}`",
                (
                    f"Release ID: `{oldest_release_id}`\n"
                    f"Release ID: `{previous_release_id}`"
                ),
                "historical Release ID must appear exactly once",
            ),
            "additional_readback_target": (
                f"--archive-dir dist/releases/{oldest_release_id}",
                (
                    f"--archive-dir dist/releases/{oldest_release_id}\n"
                    "python3 script/check_release_artifact_archive.py \\\n"
                    f"  --archive-dir dist/releases/{previous_release_id} \\\n"
                    "  --historical"
                ),
                "historical archive readback target must appear exactly once",
            ),
            "additional_historical_mode": (
                "  --historical",
                "  --historical\n  --historical",
                "historical readback mode must appear exactly once",
            ),
            "current_prose": (
                f"Build {current.build_number} is the current local",
                f"Build {previous.build_number} is the current local",
                "current qualification prose must name build",
            ),
            "additional_stale_qualification_record": (
                f"`{current_doc}`",
                (
                    f"`{current_doc}`\n"
                    f"Stale current qualification record: `{previous_doc}`."
                ),
                "current release document pointer must appear exactly once",
            ),
            "qualification_record": (
                f"`{current_doc}`",
                f"`{previous_doc}`",
                "current qualification record pointer",
            ),
            "additional_stale_fuller_contract": (
                f"contract now lives in the Build {current.build_number} record",
                (
                    f"contract now lives in the build "
                    f"{current.build_number} record.\n"
                    f"The fuller compatibility contract now lives in the "
                    f"build {previous.build_number} record"
                ),
                "fuller contract must point to current build",
            ),
            "fuller_contract": (
                f"Build {current.build_number} record",
                f"Build {previous.build_number} record",
                "fuller contract must point to current build",
            ),
        }
        for label, (before, after, expected_failure) in mutations.items():
            with self.subTest(label=label):
                mutated_documents = dict(documents)
                mutated_documents[oldest_build] = documents[
                    oldest_build
                ].replace(before, after)
                self.assertNotEqual(
                    mutated_documents[oldest_build],
                    documents[oldest_build],
                )
                failures = (
                    check_docs_hygiene
                    .historical_local_release_document_failures(
                        ledger_bytes=ledger_bytes,
                        document_text_by_build=mutated_documents,
                    )
                )
                self.assertTrue(
                    any(
                        expected_failure in failure
                        for failure in failures
                    ),
                    f"historical release mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

    def test_build3_fixture_record_requires_one_own_historical_readback(
        self,
    ) -> None:
        ledger_bytes = check_docs_hygiene.LOCAL_RELEASE_LEDGER.read_bytes()
        entries = check_docs_hygiene.parse_release_version_ledger(
            ledger_bytes
        )
        documents = {
            entry.build_number: (
                check_docs_hygiene.ROOT
                / "docs"
                / "releases"
                / (
                    f"{entry.marketing_version}-build-"
                    f"{entry.build_number}-local-v1.md"
                )
            ).read_text(encoding="utf-8")
            for entry in entries[:-1]
        }
        fixture_build = check_docs_hygiene.LOCAL_RELEASE_FIXTURE_BUILD_NUMBER
        fixture_release_id = check_docs_hygiene.LOCAL_RELEASE_FIXTURE_ID
        target = f"--archive-dir dist/releases/{fixture_release_id}"

        mutations = {
            "missing": documents[fixture_build].replace(
                target,
                "--archive-dir dist/releases/removed-build3-target",
                1,
            ),
            "duplicate": documents[fixture_build].replace(
                target,
                f"{target}\n{target}",
                1,
            ),
        }
        for label, mutated_fixture in mutations.items():
            with self.subTest(label=label):
                mutated_documents = dict(documents)
                mutated_documents[fixture_build] = mutated_fixture
                failures = (
                    check_docs_hygiene
                    .historical_local_release_document_failures(
                        ledger_bytes=ledger_bytes,
                        document_text_by_build=mutated_documents,
                    )
                )
                self.assertTrue(
                    any(
                        "historical archive readback target must include "
                        "exactly one" in failure
                        for failure in failures
                    ),
                    f"build 3 readback mutation {label!r} was accepted: "
                    f"{failures!r}",
                )

    def test_every_local_release_identity_mutation_is_rejected(self) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC.read_text(
            encoding="utf-8"
        )
        identity_snippets = (
            f"`{check_docs_hygiene.LOCAL_RELEASE_ID}`",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MEMBER_COUNT} payload members",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT}-file source inventory",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SIZE:,} bytes",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE:,} bytes",
            f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE:,} bytes",
            (
                f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE:,} "
                "bytes"
            ),
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SHA256}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256}`",
            (
                f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256}`"
            ),
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-9-lifecycle-v1.json`"
            ),
            (
                f"{check_docs_hygiene.MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
            (
                f"`{check_docs_hygiene.MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256}`"
            ),
            "`minimumObservationSeconds=5.0`",
            "`observationDeadlineReached=true`",
            "`identityFilePresentAfterRuns=[false, false]`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_SHA256}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MACOS_UUID}`",
            "101- and 109-byte source roots",
            "`sourceRootLengthsDiffer=true`",
            "`independentReadback=true`",
            "`publishedBytesEqualLaneA=true`",
            "`sourceSnapshotUnchanged=true`",
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
            b"4\t1.0.0\n"
            b"5\t1.0.0\n"
        )

        failures = self.local_release_transition_failures_from_text(
            document_text,
            ledger_bytes=drifted_ledger,
        )

        self.assertTrue(
            any(
                "cannot cross-check local release transition fixture"
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
            b"1\t1.0.0\n"
            b"MALFORMED\n"
            b"2\t1.0.0\n"
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
            "isolated_model_backed_cancel_drift": (
                '"chatCancellationPassed": true',
                '"chatCancellationPassed": false',
            ),
            "recorded_date_drift": (
                '"recordedDate": "2026-07-29"',
                '"recordedDate": "2026-07-30"',
            ),
            "isolated_run_count_drift": (
                '"executed": 4',
                '"executed": 3',
            ),
            "test_count_type_confusion": (
                '"executed": 71',
                '"executed": 71.0',
            ),
            "ollama_executed_count": (
                '"ollama": {\n      "executed": 78,',
                '"ollama": {\n      "executed": 77,',
            ),
            "ollama_skipped_count": (
                '"passed": 72,\n      "skipped": 6\n    },\n'
                '    "testKind"',
                '"passed": 72,\n      "skipped": 5\n    },\n'
                '    "testKind"',
            ),
            "evidence_overclaim": (
                '"exact-version-isolated-ollama-empty-catalog-and-existing-'
                'chat-plus-embedding-plus-vision-model-cold-restart-plus-'
                'focused-default-tests-no-lm-studio-live-or-semantic-'
                'qualification"',
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

    def test_local_release_ollama_runner_fixture_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        mutations = {
            "archive_hash": (
                '"archiveSha256": '
                '"5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"',
                '"archiveSha256": '
                '"0000000000000000000000000000000000000000000000000000000000000000"',
            ),
            "archive_url": (
                '"archiveUrl": "https://github.com/ollama/ollama/releases/'
                'download/v0.32.5/ollama-darwin.tgz"',
                '"archiveUrl": "https://example.invalid/ollama-darwin.tgz"',
            ),
            "cold_start_result": (
                '"adapterTestPassed": true',
                '"adapterTestPassed": false',
            ),
            "restart_stop_result": (
                '"restart": {\n        "adapterTestPassed": true,\n'
                '        "endpointUnavailableAfterStop": true',
                '"restart": {\n        "adapterTestPassed": true,\n'
                '        "endpointUnavailableAfterStop": false',
            ),
            "test_run_count": (
                '"testRuns": 2',
                '"testRuns": 1',
            ),
            "version": (
                '"version": "0.32.5"',
                '"version": "0.32.6"',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "versions"',
                '"schemaVersion": 1,\n  "schemaVersion": 1,\n  "versions"',
            ),
        }
        start_index = document_text.index(
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START
        )
        end_index = document_text.index(
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END
        ) + len(check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END)
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
                failures = (
                    self.local_release_ollama_runner_failures_from_text(
                        mutated
                    )
                )
                expected_failure = (
                    "invalid ollama-exact-version-run fixture JSON"
                    if label == "duplicate_root_key"
                    else "must match the runner's canonical exact values"
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    f"runner fixture mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

        marker_mutations = {
            "missing_start_marker": (
                check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START,
                "<!-- removed-ollama-runner-fixture-start -->",
            ),
            "missing_end_marker": (
                check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END,
                "<!-- removed-ollama-runner-fixture-end -->",
            ),
        }
        for label, (before, after) in marker_mutations.items():
            with self.subTest(label=label):
                mutated = document_text.replace(before, after, 1)
                failures = (
                    self.local_release_ollama_runner_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any("expected exactly one" in failure for failure in failures),
                    f"runner fixture mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

    def test_local_release_ollama_runner_fixture_rejects_runner_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_text = (
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
                encoding="utf-8"
            )
        )
        mutated_runner = runner_text.replace(
            'RUNNER_ID = "aetherlink-ollama-exact-version-runner-v1"',
            'RUNNER_ID = "aetherlink-ollama-exact-version-runner-drift"',
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(mutated_runner, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                failures = (
                    self.local_release_ollama_runner_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "must match the runner's canonical exact values" in failure
                for failure in failures
            ),
            f"runner contract drift was accepted: {failures!r}",
        )

    def test_local_release_ollama_model_backed_fixture_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        mutations = {
            "blob_count": (
                '"blobCount": 2138',
                '"blobCount": 2137',
            ),
            "manifest_size": (
                '"manifestBytes": 460486',
                '"manifestBytes": 460485',
            ),
            "model_artifact_size": (
                '"modelArtifactBytes": 9639236355',
                '"modelArtifactBytes": 9639236354',
            ),
            "download_overclaim": (
                '"modelDownloadAttempted": false',
                '"modelDownloadAttempted": true',
            ),
            "model_name_retention": (
                '"modelNameRetained": false',
                '"modelNameRetained": true',
            ),
            "source_catalog_count": (
                '"catalogModelCount": 4',
                '"catalogModelCount": 5',
            ),
            "source_version": (
                '"providerVersion": "0.32.4"',
                '"providerVersion": "0.32.5"',
            ),
            "chat_cancellation": (
                '"chatCancellationConfirmed": true',
                '"chatCancellationConfirmed": false',
            ),
            "post_cancel_recovery": (
                '"postCancellationRecoveryPassed": true',
                '"postCancellationRecoveryPassed": false',
            ),
            "snapshot_changed": (
                '"snapshotUnchanged": true',
                '"snapshotUnchanged": false',
            ),
            "test_run_count": (
                '"testRuns": 2',
                '"testRuns": 1',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "snapshot"',
                '"schemaVersion": 1,\n  "schemaVersion": 1,\n  "snapshot"',
            ),
        }
        start_index = document_text.index(
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_START
        )
        end_index = document_text.index(
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_END
        ) + len(
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_END
        )
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
                failures = (
                    self.local_release_ollama_model_backed_failures_from_text(
                        mutated
                    )
                )
                expected_failure = (
                    "invalid ollama-model-backed-run fixture JSON"
                    if label == "duplicate_root_key"
                    else "must match the runner's canonical exact values"
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    f"model-backed fixture mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

        marker_mutations = {
            "missing_start_marker": (
                check_docs_hygiene.LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_START,
                "<!-- removed-ollama-model-backed-fixture-start -->",
            ),
            "missing_end_marker": (
                check_docs_hygiene.LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_END,
                "<!-- removed-ollama-model-backed-fixture-end -->",
            ),
        }
        for label, (before, after) in marker_mutations.items():
            with self.subTest(label=label):
                mutated = document_text.replace(before, after, 1)
                failures = (
                    self.local_release_ollama_model_backed_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any("expected exactly one" in failure for failure in failures),
                    f"model-backed marker mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

    def test_local_release_ollama_model_backed_fixture_rejects_runner_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_text = (
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
                encoding="utf-8"
            )
        )
        mutated_runner = runner_text.replace(
            'MODEL_BACKED_RUNNER_ID = "aetherlink-ollama-model-backed-runner-v1"',
            'MODEL_BACKED_RUNNER_ID = "aetherlink-ollama-model-backed-runner-drift"',
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(mutated_runner, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                failures = (
                    self.local_release_ollama_model_backed_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "must match the runner's canonical exact values" in failure
                for failure in failures
            ),
            f"model-backed runner contract drift was accepted: {failures!r}",
        )

    def test_local_release_ollama_additional_chat_shape_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        start_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_START
        )
        end_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_END
        )
        start_index = document_text.index(start_marker)
        end_index = document_text.index(end_marker) + len(end_marker)
        fixture_block = document_text[start_index:end_index]
        mutations = {
            "observation_count": (
                '"observationCount": 4',
                '"observationCount": 3',
            ),
            "selection_ordinal": (
                '"selectionOrdinal": 2',
                '"selectionOrdinal": 1',
            ),
            "target_capability_count": (
                '"targetCapabilityCount": 3',
                '"targetCapabilityCount": 2',
            ),
            "target_vision": (
                '"targetVisionCapable": false',
                '"targetVisionCapable": true',
            ),
            "blob_count": (
                '"blobCount": 991',
                '"blobCount": 990',
            ),
            "manifest_size": (
                '"manifestBytes": 213712',
                '"manifestBytes": 213711',
            ),
            "artifact_size": (
                '"modelArtifactBytes": 16679502421',
                '"modelArtifactBytes": 16679502420',
            ),
            "download_attempt": (
                '"modelDownloadAttempted": false',
                '"modelDownloadAttempted": true',
            ),
            "source_bytes": (
                '"selectedFileBytesUnchanged": true',
                '"selectedFileBytesUnchanged": false',
            ),
            "runner_binding": (
                '"runnerSourceSha256": '
                '"318a08ed99fae1ea797ed736fc24f7ad4e199f2f8b85518ba67b9c71fb7bb5a5"',
                '"runnerSourceSha256": '
                f'"{"0" * 64}"',
            ),
            "chat_cancellation": (
                '"chatCancellationConfirmed": true',
                '"chatCancellationConfirmed": false',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "selection"',
                '"schemaVersion": 1,\n'
                '  "schemaVersion": 1,\n'
                '  "selection"',
            ),
        }

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated_block = fixture_block.replace(before, after, 1)
                self.assertNotEqual(mutated_block, fixture_block)
                mutated = (
                    document_text[:start_index]
                    + mutated_block
                    + document_text[end_index:]
                )
                failures = (
                    self.local_release_ollama_additional_chat_shape_failures_from_text(
                        mutated
                    )
                )
                expected_failure = (
                    "invalid ollama-additional-chat-shape fixture JSON"
                    if label == "duplicate_root_key"
                    else "must match the runner's canonical exact values"
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    f"additional chat-shape mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

        for marker in (start_marker, end_marker):
            with self.subTest(marker=marker):
                mutated = document_text.replace(
                    marker,
                    "<!-- removed-additional-chat-shape-marker -->",
                    1,
                )
                failures = (
                    self.local_release_ollama_additional_chat_shape_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any(
                        "expected exactly one" in failure
                        for failure in failures
                    ),
                    "additional chat-shape marker mutation produced "
                    f"unexpected failures: {failures!r}",
                )

    def test_local_release_ollama_additional_chat_shape_rejects_runner_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_path = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_RUNNER
        )
        runner_text = runner_path.read_text(encoding="utf-8")
        mutated_runner = runner_text.replace(
            'FIXTURE_ID = "aetherlink-ollama-additional-chat-shape-v1"',
            'FIXTURE_ID = "aetherlink-ollama-additional-chat-shape-drift"',
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT
        ) as temporary_directory:
            temporary_runner = (
                Path(temporary_directory)
                / "run_ollama_additional_chat_shape_matrix.py"
            )
            temporary_runner.write_text(
                mutated_runner,
                encoding="utf-8",
            )
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_RUNNER",
                temporary_runner,
            ):
                failures = (
                    self.local_release_ollama_additional_chat_shape_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "cannot derive canonical additional chat-shape fixture"
                in failure
                for failure in failures
            ),
            "additional chat-shape runner-source drift was accepted: "
            f"{failures!r}",
        )

    def test_local_release_ollama_embedding_model_backed_fixture_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        mutations = {
            "blob_count": (
                '"blobCount": 4',
                '"blobCount": 5',
            ),
            "manifest_size": (
                '"manifestBytes": 741',
                '"manifestBytes": 742',
            ),
            "model_artifact_size": (
                '"modelArtifactBytes": 621875917',
                '"modelArtifactBytes": 621875918',
            ),
            "download_overclaim": (
                '"modelDownloadAttempted": false',
                '"modelDownloadAttempted": true',
            ),
            "model_name_retention": (
                '"modelNameRetained": false',
                '"modelNameRetained": true',
            ),
            "embedding_batch": (
                '"embeddingBatchCompleted": true',
                '"embeddingBatchCompleted": false',
            ),
            "embedding_shape": (
                '"embeddingShapeValidated": true',
                '"embeddingShapeValidated": false',
            ),
            "model_unload": (
                '"modelUnloadConfirmed": true',
                '"modelUnloadConfirmed": false',
            ),
            "snapshot_changed": (
                '"snapshotUnchanged": true',
                '"snapshotUnchanged": false',
            ),
            "test_run_count": (
                '"testRuns": 2',
                '"testRuns": 1',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "snapshot"',
                '"schemaVersion": 1,\n  "schemaVersion": 1,\n  "snapshot"',
            ),
        }
        start_marker = getattr(
            check_docs_hygiene,
            "LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_START",
        )
        end_marker = getattr(
            check_docs_hygiene,
            "LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_END",
        )
        start_index = document_text.index(start_marker)
        end_index = document_text.index(end_marker) + len(end_marker)
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
                failures = self.local_release_ollama_embedding_model_backed_failures_from_text(
                    mutated
                )
                expected_failure = (
                    "invalid ollama-embedding-model-backed-run fixture JSON"
                    if label == "duplicate_root_key"
                    else "must match the runner's canonical exact values"
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    f"embedding-model-backed fixture mutation {label!r} "
                    f"produced unexpected failures: {failures!r}",
                )

        marker_mutations = {
            "missing_start_marker": (
                start_marker,
                "<!-- removed-ollama-embedding-model-backed-start -->",
            ),
            "missing_end_marker": (
                end_marker,
                "<!-- removed-ollama-embedding-model-backed-end -->",
            ),
        }
        for label, (before, after) in marker_mutations.items():
            with self.subTest(label=label):
                mutated = document_text.replace(before, after, 1)
                failures = self.local_release_ollama_embedding_model_backed_failures_from_text(
                    mutated
                )
                self.assertTrue(
                    any("expected exactly one" in failure for failure in failures),
                    f"embedding-model-backed marker mutation {label!r} "
                    f"produced unexpected failures: {failures!r}",
                )

    def test_local_release_ollama_embedding_model_backed_fixture_rejects_runner_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_text = (
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
                encoding="utf-8"
            )
        )
        mutated_runner = runner_text.replace(
            "aetherlink-ollama-embedding-model-backed-runner-v1",
            "aetherlink-ollama-embedding-model-backed-runner-drift",
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(mutated_runner, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                failures = self.local_release_ollama_embedding_model_backed_failures_from_text(
                    document_text
                )

        self.assertTrue(
            any(
                "must match the runner's canonical exact values" in failure
                for failure in failures
            ),
            "embedding-model-backed runner contract drift was accepted: "
            f"{failures!r}",
        )

    def test_local_release_ollama_embedding_semantic_quality_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        start_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_START
        )
        end_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_END
        )
        start_index = document_text.index(start_marker)
        end_index = document_text.index(end_marker) + len(end_marker)
        fixture_block = document_text[start_index:end_index]
        mutations = {
            "task_sha": (
                '"sha256": '
                '"e00f27d91a11f73f6f5f74eef9a4681b2dd2d70c45090456de17a5642b67023f"',
                f'"sha256": "{"0" * 64}"',
            ),
            "margin_threshold": (
                '"minimumPositiveMarginBasisPoints": 200',
                '"minimumPositiveMarginBasisPoints": 199',
            ),
            "repeat_threshold": (
                '"minimumRepeatCosineBasisPoints": 9990',
                '"minimumRepeatCosineBasisPoints": 9989',
            ),
            "boolean_count": (
                '"semanticObservationCount": 2',
                '"semanticObservationCount": true',
            ),
            "semantic_result": (
                '"repeatabilityPassed": true',
                '"repeatabilityPassed": false',
            ),
            "process_group": (
                '"processGroupReaped": true',
                '"processGroupReaped": false',
            ),
            "recovery_result": (
                '"catalogPopulated": true',
                '"catalogPopulated": false',
            ),
            "archive_identity": (
                '"archiveSha256": '
                '"5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"',
                f'"archiveSha256": "{"0" * 64}"',
            ),
            "scorer_source_identity": (
                '"semanticScorerSha256": '
                '"4578680bf2e4548afcdbef4ba95022da81d15eecceb86acbfa088d068c6b0546"',
                f'"semanticScorerSha256": "{"0" * 64}"',
            ),
            "live_assertion_source_identity": (
                '"liveAssertionsSha256": '
                '"e48dc934496c0473866d7c819cffa20bacd8411271628ed55e52be5ba34881c0"',
                f'"liveAssertionsSha256": "{"0" * 64}"',
            ),
            "exact_test_execution": (
                '"exactTestCaseExecuted": true',
                '"exactTestCaseExecuted": false',
            ),
            "swift_source_preservation": (
                '"swiftSourcesUnchanged": true',
                '"swiftSourcesUnchanged": false',
            ),
            "extra_semantic_key": (
                '"allMarginsPassed": true,',
                '"allMarginsPassed": true,\n'
                '        "unexpected": true,',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "semanticObservationCount"',
                '"schemaVersion": 1,\n'
                '  "schemaVersion": 1,\n'
                '  "semanticObservationCount"',
            ),
        }

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated_block = fixture_block.replace(before, after, 1)
                self.assertNotEqual(mutated_block, fixture_block)
                mutated = (
                    document_text[:start_index]
                    + mutated_block
                    + document_text[end_index:]
                )
                failures = (
                    self.local_release_ollama_embedding_semantic_quality_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    failures,
                    f"semantic-quality mutation {label!r} was accepted",
                )
                self.assertTrue(
                    any(
                        "ollama-embedding-semantic-quality" in failure
                        for failure in failures
                    ),
                    f"semantic-quality mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

        for marker in (start_marker, end_marker):
            with self.subTest(marker=marker):
                mutated = document_text.replace(
                    marker,
                    "<!-- removed-ollama-embedding-semantic-marker -->",
                    1,
                )
                failures = (
                    self.local_release_ollama_embedding_semantic_quality_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any(
                        "expected exactly one" in failure
                        for failure in failures
                    ),
                    "semantic-quality marker mutation produced unexpected "
                    f"failures: {failures!r}",
                )

    def test_local_release_ollama_embedding_semantic_quality_rejects_runner_source_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_text = (
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
                encoding="utf-8"
            )
        )
        mutated_runner = runner_text.replace(
            "EMBEDDING_SEMANTIC_QUALITY_ADAPTER_DEADLINE_SECONDS = 120",
            "EMBEDDING_SEMANTIC_QUALITY_ADAPTER_DEADLINE_SECONDS = 121",
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(mutated_runner, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                failures = (
                    self.local_release_ollama_embedding_semantic_quality_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "runner source differs from the recorded normalized SHA-256"
                in failure
                for failure in failures
            ),
            "semantic-quality executable runner-source drift was accepted: "
            f"{failures!r}",
        )

    def test_local_release_ollama_embedding_semantic_quality_rejects_swift_source_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        cases = (
            (
                "semantic scorer",
                "LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE",
                (
                    check_docs_hygiene
                    .LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE
                ),
                "semantic scorer source bytes differ",
            ),
            (
                "live assertion",
                (
                    "LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_"
                    "LIVE_ASSERTION_SOURCE"
                ),
                (
                    check_docs_hygiene
                    .LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_LIVE_ASSERTION_SOURCE
                ),
                "semantic live assertion source bytes differ",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for label, attribute, source_path, expected_failure in cases:
                with self.subTest(label=label):
                    mutated_source_path = root / f"{label}.swift"
                    mutated_source_path.write_bytes(
                        source_path.read_bytes() + b"\n"
                    )
                    with patch.object(
                        check_docs_hygiene,
                        attribute,
                        mutated_source_path,
                    ):
                        failures = (
                            self.local_release_ollama_embedding_semantic_quality_failures_from_text(
                                document_text
                            )
                        )
                    self.assertTrue(
                        any(
                            expected_failure in failure
                            for failure in failures
                        ),
                        f"{label} source drift was accepted: {failures!r}",
                    )

    def test_local_release_ollama_embedding_multilingual_semantic_quality_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        start_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_START
        )
        end_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_END
        )
        start_index = document_text.index(start_marker)
        end_index = document_text.index(end_marker) + len(end_marker)
        fixture_block = document_text[start_index:end_index]
        mutations = {
            "task_sha": (
                '"sha256": '
                '"a4dde8d94f661fe9682103875ed53db703761722c19ec32b35ceba72ecae2e31"',
                f'"sha256": "{"0" * 64}"',
            ),
            "runner_sha": (
                '"runnerSourceSha256": '
                '"45cd9fe57e15bcc8adc1b335ead87d36a888545d37de9720ef4c7f5d49697078"',
                f'"runnerSourceSha256": "{"0" * 64}"',
            ),
            "locale": (
                '"failureLocale": "ko"',
                '"failureLocale": "ja"',
            ),
            "failure_ordinal": (
                '"failureScenarioOrdinalWithinLocale": 2',
                '"failureScenarioOrdinalWithinLocale": 1',
            ),
            "quality_gate": (
                '"qualityGatePassed": false',
                '"qualityGatePassed": true',
            ),
            "semantic_result": (
                '"adapterTestPassed": false',
                '"adapterTestPassed": true',
            ),
            "recovery_result": (
                '"catalogPopulated": true',
                '"catalogPopulated": false',
            ),
            "locale_count": (
                '"localeCount": 5',
                '"localeCount": 4',
            ),
            "embedding_count": (
                '"embeddingCountPerVersion": 160',
                '"embeddingCountPerVersion": 159',
            ),
            "source_identity": (
                '"scorerAndLiveAssertionSha256": '
                '"054639797cc9a07f336034f8858772017d63f43970a269f810c24fb3f23c8d40"',
                f'"scorerAndLiveAssertionSha256": "{"0" * 64}"',
            ),
            "embedding_contract_identity": (
                '"embeddingRequestContractSha256": '
                '"708a22934bb8f28218e5ddaeab6a7b469d8beddaa77e5887746e35be40125505"',
                f'"embeddingRequestContractSha256": "{"0" * 64}"',
            ),
            "ollama_adapter_identity": (
                '"ollamaEmbeddingAdapterSha256": '
                '"5c10154d96c9c6e69f10bb214abaefdaded4646f85cacdc781c55ffb6e48a06d"',
                f'"ollamaEmbeddingAdapterSha256": "{"0" * 64}"',
            ),
            "aggregate_identity": (
                '"aggregateRolePreservationSha256": '
                '"808b434913bb004883b4cfa77c70a4b46dfceebc562615a2223dd27de02d5c99"',
                f'"aggregateRolePreservationSha256": "{"0" * 64}"',
            ),
            "router_identity": (
                '"routerRoleAssignmentSha256": '
                '"7e6443295993b3ac9e19e78a45c989d8eb3b00e40d237191067ee14c70df6a97"',
                f'"routerRoleAssignmentSha256": "{"0" * 64}"',
            ),
            "fingerprint_identity": (
                '"semanticFingerprintSha256": '
                '"bca3faff000112e59945fb558815b1108a1704c6a438eed3e347cf15d685ac8c"',
                f'"semanticFingerprintSha256": "{"0" * 64}"',
            ),
            "boolean_count": (
                '"semanticFailureObservationCount": 2',
                '"semanticFailureObservationCount": true',
            ),
            "extra_semantic_key": (
                '"allLocalesPassed": false,',
                '"allLocalesPassed": false,\n'
                '        "unexpected": true,',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 4,\n'
                '  "semanticFailureObservationCount"',
                '"schemaVersion": 4,\n'
                '  "schemaVersion": 4,\n'
                '  "semanticFailureObservationCount"',
            ),
        }

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated_block = fixture_block.replace(before, after, 1)
                self.assertNotEqual(mutated_block, fixture_block)
                mutated = (
                    document_text[:start_index]
                    + mutated_block
                    + document_text[end_index:]
                )
                failures = (
                    self.local_release_ollama_embedding_multilingual_semantic_quality_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    failures,
                    "multilingual semantic mutation "
                    f"{label!r} was accepted",
                )
                self.assertTrue(
                    any(
                        "multilingual-semantic-quality" in failure
                        or "multilingual semantic" in failure
                        for failure in failures
                    ),
                    "multilingual semantic mutation "
                    f"{label!r} produced unexpected failures: "
                    f"{failures!r}",
                )

        for marker in (start_marker, end_marker):
            with self.subTest(marker=marker):
                mutated = document_text.replace(
                    marker,
                    "<!-- removed-multilingual-semantic-marker -->",
                    1,
                )
                failures = (
                    self.local_release_ollama_embedding_multilingual_semantic_quality_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any(
                        "expected exactly one" in failure
                        for failure in failures
                    ),
                    "multilingual semantic marker mutation produced "
                    f"unexpected failures: {failures!r}",
                )

    def test_local_release_ollama_vision_model_backed_fixture_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        start_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_START
        )
        end_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_END
        )
        start_index = document_text.index(start_marker)
        end_index = document_text.index(end_marker) + len(end_marker)
        fixture_block = document_text[start_index:end_index]
        mutations = {
            "blob_count": (
                '"blobCount": 997',
                '"blobCount": 996',
            ),
            "manifest_size": (
                '"manifestBytes": 207279',
                '"manifestBytes": 207278',
            ),
            "image_attachment": (
                '"imageAttachmentCompleted": true',
                '"imageAttachmentCompleted": false',
            ),
            "source_catalog_projection": (
                '"catalogIdentityProjectionUnchanged": true',
                '"catalogIdentityProjectionUnchanged": false',
            ),
            "source_running_identity_set": (
                '"runningIdentitySetUnchanged": true',
                '"runningIdentitySetUnchanged": false',
            ),
            "selected_source_file_bytes": (
                '"selectedFileBytesUnchanged": true',
                '"selectedFileBytesUnchanged": false',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "snapshot"',
                '"schemaVersion": 1,\n  "schemaVersion": 1,\n  "snapshot"',
            ),
        }

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated_block = fixture_block.replace(before, after, 1)
                self.assertNotEqual(mutated_block, fixture_block)
                mutated = (
                    document_text[:start_index]
                    + mutated_block
                    + document_text[end_index:]
                )
                failures = (
                    self.local_release_ollama_vision_model_backed_failures_from_text(
                        mutated
                    )
                )
                expected_failure = (
                    "invalid ollama-vision-model-backed-run fixture JSON"
                    if label == "duplicate_root_key"
                    else "must match the runner's canonical exact values"
                )
                self.assertTrue(
                    any(expected_failure in failure for failure in failures),
                    f"vision fixture mutation {label!r} produced "
                    f"unexpected failures: {failures!r}",
                )

        for marker in (start_marker, end_marker):
            with self.subTest(marker=marker):
                mutated = document_text.replace(
                    marker,
                    "<!-- removed-ollama-vision-fixture-marker -->",
                    1,
                )
                failures = (
                    self.local_release_ollama_vision_model_backed_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any("expected exactly one" in failure for failure in failures),
                    f"vision marker mutation produced unexpected failures: "
                    f"{failures!r}",
                )

    def test_local_release_ollama_vision_model_backed_fixture_rejects_runner_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_text = (
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
                encoding="utf-8"
            )
        )
        mutated_runner = runner_text.replace(
            'VISION_BACKED_RUNNER_ID = "aetherlink-ollama-vision-model-backed-runner-v1"',
            'VISION_BACKED_RUNNER_ID = "aetherlink-ollama-vision-model-backed-runner-drift"',
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(mutated_runner, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                failures = (
                    self.local_release_ollama_vision_model_backed_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "must match the runner's canonical exact values" in failure
                for failure in failures
            ),
            "vision-model-backed runner contract drift was accepted: "
            f"{failures!r}",
        )

    def test_local_release_ollama_duration_observation_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        start_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_START
        )
        end_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_END
        )
        start_index = document_text.index(start_marker)
        end_index = document_text.index(end_marker) + len(end_marker)
        fixture_block = document_text[start_index:end_index]
        mutations = {
            "canonical_fixture_sha256": (
                '"canonicalFixtureSha256": '
                '"f0f342172d4ac8ba54936997251cb47dff5fe0eaeb35e68a7e20c603949e15ac"',
                '"canonicalFixtureSha256": '
                f'"{"0" * 64}"',
            ),
            "duration_value": (
                '"providerReadyMs": 5533',
                '"providerReadyMs": 5534',
            ),
            "phase_count": (
                '"phaseObservationCount": 12',
                '"phaseObservationCount": 11',
            ),
            "deadline_result": (
                '"allBoundedOperationsWithinDeadline": true',
                '"allBoundedOperationsWithinDeadline": false',
            ),
            "boolean_type_confusion": (
                '"sampleCountPerPhase": 1',
                '"sampleCountPerPhase": true',
            ),
            "extra_phase_key": (
                '"adapterMs": 4592,',
                '"adapterMs": 4592,\n              "unexpectedMs": 1,',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1\n}',
                '"schemaVersion": 1,\n  "schemaVersion": 1\n}',
            ),
        }

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated_block = fixture_block.replace(before, after, 1)
                self.assertNotEqual(mutated_block, fixture_block)
                mutated = (
                    document_text[:start_index]
                    + mutated_block
                    + document_text[end_index:]
                )
                failures = (
                    self.local_release_ollama_duration_observation_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    failures,
                    f"duration mutation {label!r} was accepted",
                )
                self.assertTrue(
                    any(
                        "duration-observation" in failure
                        for failure in failures
                    ),
                    f"duration mutation {label!r} produced unexpected "
                    f"failures: {failures!r}",
                )

        for marker in (start_marker, end_marker):
            with self.subTest(marker=marker):
                mutated = document_text.replace(
                    marker,
                    "<!-- removed-ollama-duration-marker -->",
                    1,
                )
                failures = (
                    self.local_release_ollama_duration_observation_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any("expected exactly one" in failure for failure in failures),
                    f"duration marker mutation produced unexpected failures: "
                    f"{failures!r}",
                )

    def test_local_release_ollama_duration_observation_rejects_runner_hash_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_text = (
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
                encoding="utf-8"
            )
        )
        recorded_sha256 = (
            "aec82dc92f82f49681ed8854d0bea204f071004fd9aaa767678c0ed8290dfb13"
        )
        mutated_runner = runner_text.replace(
            recorded_sha256,
            "0" * 64,
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(mutated_runner, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                failures = (
                    self.local_release_ollama_duration_observation_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "differs from the recorded runner SHA-256" in failure
                for failure in failures
            ),
            "duration-observation runner hash drift was accepted: "
            f"{failures!r}",
        )

    def test_local_release_ollama_live_fault_injection_mutations_are_rejected(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        start_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_START
        )
        end_marker = (
            check_docs_hygiene
            .LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_END
        )
        start_index = document_text.index(start_marker)
        end_index = document_text.index(end_marker) + len(end_marker)
        fixture_block = document_text[start_index:end_index]
        mutations = {
            "canonical_fixture_sha256": (
                '"canonicalFixtureSha256": '
                '"f0f342172d4ac8ba54936997251cb47dff5fe0eaeb35e68a7e20c603949e15ac"',
                '"canonicalFixtureSha256": '
                f'"{"0" * 64}"',
            ),
            "fault_observation_count": (
                '"faultObservationCount": 6',
                '"faultObservationCount": 5',
            ),
            "deadline_type_confusion": (
                '"processGroupReap": 2000',
                '"processGroupReap": true',
            ),
            "fault_order": (
                '"faultId": "provider-unavailable-before-request"',
                '"faultId": "provider-exit-after-first-delta"',
            ),
            "recovery_result": (
                '"recoveryPassed": true',
                '"recoveryPassed": false',
            ),
            "archive_sha256": (
                '"archiveSha256": '
                '"5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"',
                '"archiveSha256": '
                f'"{"0" * 64}"',
            ),
            "extra_fault_key": (
                '"endpointUnavailableAfterFault": true,',
                '"endpointUnavailableAfterFault": true,\n'
                '          "unexpected": true,',
            ),
            "duplicate_root_key": (
                '"schemaVersion": 1,\n  "snapshot"',
                '"schemaVersion": 1,\n'
                '  "schemaVersion": 1,\n'
                '  "snapshot"',
            ),
        }

        for label, (before, after) in mutations.items():
            with self.subTest(label=label):
                mutated_block = fixture_block.replace(before, after, 1)
                self.assertNotEqual(mutated_block, fixture_block)
                mutated = (
                    document_text[:start_index]
                    + mutated_block
                    + document_text[end_index:]
                )
                failures = (
                    self.local_release_ollama_live_fault_injection_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    failures,
                    f"live-fault mutation {label!r} was accepted",
                )
                self.assertTrue(
                    any(
                        "ollama-live-fault-injection" in failure
                        for failure in failures
                    ),
                    f"live-fault mutation {label!r} produced unexpected "
                    f"failures: {failures!r}",
                )

        for marker in (start_marker, end_marker):
            with self.subTest(marker=marker):
                mutated = document_text.replace(
                    marker,
                    "<!-- removed-ollama-live-fault-marker -->",
                    1,
                )
                failures = (
                    self.local_release_ollama_live_fault_injection_failures_from_text(
                        mutated
                    )
                )
                self.assertTrue(
                    any("expected exactly one" in failure for failure in failures),
                    "live-fault marker mutation produced unexpected failures: "
                    f"{failures!r}",
                )

    def test_local_release_ollama_live_fault_injection_rejects_fixture_and_source_hash_drift(
        self,
    ) -> None:
        document_text = check_docs_hygiene.LOCAL_RELEASE_DOC.read_text(
            encoding="utf-8"
        )
        runner_text = (
            check_docs_hygiene.LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
                encoding="utf-8"
            )
        )
        recorded_sha256 = (
            "226d7b367e2311ea4e664804bd614d93af59172d332e07afc5443f9c166c31cf"
        )
        mutated_runner = runner_text.replace(
            recorded_sha256,
            "0" * 64,
            1,
        )
        self.assertNotEqual(mutated_runner, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(mutated_runner, encoding="utf-8")
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                failures = (
                    self.local_release_ollama_live_fault_injection_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "differs from the recorded runner SHA-256" in failure
                for failure in failures
            ),
            "live-fault-injection runner hash drift was accepted: "
            f"{failures!r}",
        )

        lifecycle_mutation = runner_text.replace(
            "LIVE_FAULT_POLL_SECONDS = 0.01",
            "LIVE_FAULT_POLL_SECONDS = 0.02",
            1,
        )
        self.assertNotEqual(lifecycle_mutation, runner_text)

        with tempfile.TemporaryDirectory() as temporary_directory:
            runner_path = Path(temporary_directory) / "runner.py"
            runner_path.write_text(
                lifecycle_mutation,
                encoding="utf-8",
            )
            with patch.object(
                check_docs_hygiene,
                "LOCAL_RELEASE_OLLAMA_RUNNER",
                runner_path,
            ):
                source_failures = (
                    self.local_release_ollama_live_fault_injection_failures_from_text(
                        document_text
                    )
                )

        self.assertTrue(
            any(
                "runner source differs from the recorded normalized SHA-256"
                in failure
                for failure in source_failures
            ),
            "live-fault executable runner-source drift was accepted: "
            f"{source_failures!r}",
        )


if __name__ == "__main__":
    unittest.main()
