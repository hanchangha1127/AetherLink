from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from script import check_docs_hygiene
from script import run_clean_release_reproducibility
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
            check_docs_hygiene.QA_CURRENT_RELEASE_READBACK_MARKER,
            "The Build 19 readback marker was removed.",
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

        build21_command = (
            "--archive-dir "
            "dist/releases/aetherlink-1.0.0+21-local-v1 --historical"
        )
        without_build21_historical = dict(documents)
        without_build21_historical[progress_path] = documents[
            progress_path
        ].replace(
            build21_command,
            build21_command.removesuffix(" --historical"),
            1,
        )
        self.assertTrue(
            any(
                "historical Build 21" in failure
                for failure in (
                    check_docs_hygiene
                    .release_readback_command_mode_failures(
                        without_build21_historical
                    )
                )
            )
        )

        current_command = (
            "--archive-dir "
            f"dist/releases/{check_docs_hygiene.LOCAL_RELEASE_ID}"
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
                "current Build 22" in failure
                for failure in (
                    check_docs_hygiene
                    .release_readback_command_mode_failures(
                        current_as_historical
                    )
                )
            )
        )

    def test_handoff_separates_build_capture_head_from_recorded_live_refs(
        self,
    ) -> None:
        handoff = (
            check_docs_hygiene.ROOT / "docs/handoff.md"
        ).read_text(encoding="utf-8")
        validator = check_docs_hygiene.current_handoff_git_attribution_failures
        self.assertEqual(validator(handoff), [])

        stale_live_head = re.sub(
            (
                rf"(at the "
                rf"{re.escape(check_docs_hygiene.LATEST_RECORDED_GIT_REFRESH_LABEL)} "
                rf"refresh,\s+`main`\s+and `origin/main` both resolved to\s+)"
                rf"`{check_docs_hygiene.LATEST_RECORDED_GIT_REFRESH_HEAD}`"
            ),
            lambda match: match.group(1) + f"`{'0' * 40}`",
            handoff,
            count=1,
        )
        self.assertNotEqual(stale_live_head, handoff)
        self.assertTrue(
            any(
                "timestamped post-qualification Git refresh" in failure
                for failure in validator(stale_live_head)
            )
        )

        missing_refresh_command = handoff.replace(
            "`git rev-parse origin/main`",
            "`git status --short`",
            1,
        )
        self.assertNotEqual(missing_refresh_command, handoff)
        self.assertTrue(
            any(
                "live origin/main refresh command" in failure
                for failure in validator(missing_refresh_command)
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

    def test_current_release_summary_documents_follow_ledger(self) -> None:
        validator = (
            check_docs_hygiene.current_release_summary_document_failures
        )
        self.assertEqual(validator(), [])
        mutations = {
            "docs/handoff.md": (
                "Build 22 is the latest immutable ledger archive.",
                "Build 21 is the latest immutable ledger archive.",
            ),
            "docs/progress.md": (
                "Local V1 Build 22 Qualification",
                "Local V1 Build 21 Qualification",
            ),
            "docs/qa-evidence.md": (
                "The Build 22 archive is the latest ledger entry",
                "The Build 21 archive is the latest ledger entry",
            ),
            "docs/roadmap.md": (
                "publish-qualified schema-v4 executions",
                "publish-qualified schema-v3 executions",
            ),
        }
        for relative, (current_claim, stale_claim) in mutations.items():
            with self.subTest(relative=relative):
                document_text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                mutated = document_text.replace(
                    current_claim,
                    stale_claim,
                    1,
                )
                self.assertNotEqual(mutated, document_text)
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "ledger-derived current release summary claim"
                        in failure
                        for failure in failures
                    ),
                    f"stale current-release summary in {relative} was accepted",
                )

        competing_stale_claims = {
            "docs/handoff.md": (
                "Build 21 is the latest immutable ledger archive."
            ),
            "docs/progress.md": (
                "Build 21 is the current local qualification record."
            ),
            "docs/qa-evidence.md": (
                "The Build 21 archive is the latest ledger entry."
            ),
            "docs/roadmap.md": (
                "Build 21 is the latest immutable local G6 package "
                "qualification record."
            ),
        }
        for relative, stale_claim in competing_stale_claims.items():
            with self.subTest(relative=relative, mode="competing-stale-claim"):
                document_text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                mutated = stale_claim + "\n\n" + document_text
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "stale previous-release summary claim" in failure
                        for failure in failures
                    ),
                    f"competing stale summary in {relative} was accepted",
                )

        semantic_stale_claims = {
            "docs/handoff.md": (
                "The v3 comparison-only prepublication result remains current."
            ),
            "docs/progress.md": (
                "Build 21 remains the latest local qualification record."
            ),
            "docs/qa-evidence.md": (
                "Build 21 continues as the current ledger qualification."
            ),
            "docs/roadmap.md": (
                "Separate publish-qualified schema-v3 executions remain the "
                "current package evidence."
            ),
        }
        for relative, stale_claim in semantic_stale_claims.items():
            with self.subTest(relative=relative, mode="semantic-stale-claim"):
                document_text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                mutated = stale_claim + "\n\n" + document_text
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "semantically re-attributed" in failure
                        for failure in failures
                    ),
                    f"semantic stale summary in {relative} was accepted",
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

    def test_current_reproducibility_prepublication_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .current_release_reproducibility_prepublication_failures()
            ),
            [],
        )
        result = json.loads(
            (
                check_docs_hygiene
                .LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT
                .read_text(encoding="utf-8")
            )
        )
        result["publication"]["attempted"] = True
        mutated = (
            json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")

        failures = (
            check_docs_hygiene
            .current_release_reproducibility_prepublication_failures(mutated)
        )

        self.assertTrue(
            any(
                "expected identity" in failure
                or "publication.attempted" in failure
                for failure in failures
            )
        )

        result = json.loads(
            (
                check_docs_hygiene
                .LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT
                .read_text(encoding="utf-8")
            )
        )
        arguments = result["toolchainPolicy"]["swiftArguments"]
        sequence_start = arguments.index("-num-threads") - 1
        del arguments[sequence_start : sequence_start + 4]
        mutated = (
            json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
        failures = (
            check_docs_hygiene
            .current_release_reproducibility_prepublication_failures(mutated)
        )
        self.assertTrue(
            any(
                "exact contiguous sequence" in failure
                for failure in failures
            )
        )

        for nullable_key in ("failure", "prepublicationBinding"):
            with self.subTest(nullable_key=nullable_key):
                result = json.loads(
                    (
                        check_docs_hygiene
                        .LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT
                        .read_text(encoding="utf-8")
                    )
                )
                self.assertIsNone(result.pop(nullable_key))
                mutated = (
                    json.dumps(
                        result,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("ascii")
                failures = (
                    check_docs_hygiene
                    .current_release_reproducibility_prepublication_failures(
                        mutated
                    )
                )
                self.assertTrue(
                    any(nullable_key in failure for failure in failures),
                    f"missing nullable key {nullable_key!r} was accepted",
                )

    def test_current_publish_result_semantic_fields_reject_drift(self) -> None:
        source_result = json.loads(
            check_docs_hygiene.LOCAL_RELEASE_REPRODUCIBILITY_RESULT.read_text(
                encoding="utf-8"
            )
        )

        def failures_for(result: dict[str, object]) -> list[str]:
            payload = (
                json.dumps(
                    result,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )
            with tempfile.TemporaryDirectory() as temporary:
                result_path = Path(temporary) / "publish-result.json"
                result_path.write_text(payload, encoding="ascii")
                with patch.object(
                    check_docs_hygiene,
                    "LOCAL_RELEASE_REPRODUCIBILITY_RESULT",
                    result_path,
                ):
                    return check_docs_hygiene.local_release_document_failures()

        for path in (
            ("failure",),
            ("publication", "archiveDirectory"),
            ("publication", "policy"),
            ("publication", "sourceLane"),
        ):
            with self.subTest(path=path):
                result = copy.deepcopy(source_result)
                parent = result
                for key in path[:-1]:
                    parent = parent[key]
                del parent[path[-1]]
                failures = failures_for(result)
                label = ".".join(path)
                self.assertTrue(
                    any(label in failure for failure in failures),
                    f"missing publish field {label!r} was accepted",
                )

        result = copy.deepcopy(source_result)
        result["builds"][0]["archive"]["size"] += 1
        failures = failures_for(result)
        self.assertTrue(
            any("builds[0].archive.size" in failure for failure in failures),
            "publish build archive-size drift was accepted",
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

    def test_macos_packaged_lifecycle_sources_match_recorded_bytes(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene.macos_packaged_lifecycle_source_failures(),
            [],
        )

    def test_macos_clean_home_result_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .macos_clean_home_installed_app_evidence_failures()
            ),
            [],
        )
        result = json.loads(
            (
                check_docs_hygiene
                .MACOS_CLEAN_HOME_INSTALLED_APP_RESULT
                .read_text(encoding="utf-8")
            )
        )
        result["launchServices"]["distinctProcessIdentifiers"] = 1
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
            check_docs_hygiene
            .macos_clean_home_installed_app_evidence_failures(mutated)
        )

        self.assertTrue(
            any("expected identity" in failure for failure in failures)
        )
        self.assertTrue(any("exact closed" in failure for failure in failures))

    def test_macos_clean_home_sources_match_recorded_bytes(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .macos_clean_home_installed_app_source_failures()
            ),
            [],
        )
        with patch.object(
            check_docs_hygiene,
            "CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256",
            "0" * 64,
        ):
            failures = (
                check_docs_hygiene
                .macos_clean_home_installed_app_source_failures()
            )
        self.assertTrue(
            any(
                "run_macos_clean_home_installed_app_smoke.py"
                in failure
                for failure in failures
            )
        )

    def test_historical_build14_clean_home_contract_is_not_current_release_derived(
        self,
    ) -> None:
        installed_app = (
            check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT
        )
        state_recovery = (
            check_docs_hygiene
            .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
        )

        self.assertEqual(installed_app["app"]["buildNumber"], 14)
        self.assertNotEqual(
            installed_app["app"]["buildNumber"],
            check_docs_hygiene.LOCAL_RELEASE_BUILD_NUMBER,
        )
        for expected_result in (installed_app, state_recovery):
            with self.subTest(scope=expected_result["scope"]):
                self.assertEqual(
                    expected_result["app"]["marketingVersion"],
                    (
                        check_docs_hygiene
                        .HISTORICAL_BUILD14_MARKETING_VERSION
                    ),
                )
                self.assertEqual(
                    expected_result["app"]["uuid"],
                    check_docs_hygiene.HISTORICAL_BUILD14_MACOS_UUID,
                )
                self.assertEqual(
                    expected_result["release"],
                    {
                        "archiveSha256": (
                            check_docs_hygiene
                            .HISTORICAL_BUILD14_ARCHIVE_SHA256
                        ),
                        "manifestSha256": (
                            check_docs_hygiene
                            .HISTORICAL_BUILD14_MANIFEST_SHA256
                        ),
                        "releaseId": (
                            check_docs_hygiene.HISTORICAL_BUILD14_RELEASE_ID
                        ),
                    },
                )
                self.assertNotEqual(
                    expected_result["release"]["releaseId"],
                    check_docs_hygiene.LOCAL_RELEASE_ID,
                )
                self.assertNotEqual(
                    expected_result["release"]["archiveSha256"],
                    check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
                )
                self.assertNotEqual(
                    expected_result["release"]["manifestSha256"],
                    check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
                )

    def test_historical_build20_clean_home_contract_is_not_current_release(
        self,
    ) -> None:
        installed_app = (
            check_docs_hygiene
            .CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT
        )
        state_recovery = (
            check_docs_hygiene
            .CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
        )

        for expected_result in (installed_app, state_recovery):
            with self.subTest(scope=expected_result["scope"]):
                self.assertEqual(
                    expected_result["app"]["buildNumber"],
                    20,
                )
                self.assertEqual(
                    expected_result["app"]["marketingVersion"],
                    check_docs_hygiene.LOCAL_RELEASE_MARKETING_VERSION,
                )
                self.assertEqual(
                    expected_result["release"],
                    {
                        "archiveSha256": (
                            check_docs_hygiene
                            .HISTORICAL_BUILD20_ARCHIVE_SHA256
                        ),
                        "manifestSha256": (
                            check_docs_hygiene
                            .HISTORICAL_BUILD20_MANIFEST_SHA256
                        ),
                        "releaseId": (
                            check_docs_hygiene.HISTORICAL_BUILD20_RELEASE_ID
                        ),
                    },
                )
                self.assertNotEqual(
                    expected_result["release"]["releaseId"],
                    check_docs_hygiene.LOCAL_RELEASE_ID,
                )

    def test_historical_build20_clean_home_results_match_closed_contracts(
        self,
    ) -> None:
        cases = (
            (
                check_docs_hygiene
                .CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT,
                check_docs_hygiene
                .current_macos_clean_home_installed_app_evidence_failures,
                ("launchServices", "distinctProcessIdentifiers"),
                1,
            ),
            (
                check_docs_hygiene
                .CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT,
                (
                    check_docs_hygiene
                    .current_macos_clean_home_installed_state_recovery_evidence_failures
                ),
                (
                    "stateRecovery",
                    "installedStateBytesAndModesUnchangedAcrossRelaunch",
                ),
                1,
            ),
        )

        for result_path, validator, mutation_path, replacement in cases:
            with self.subTest(path=result_path.name):
                self.assertEqual(validator(), [])
                result = json.loads(result_path.read_text(encoding="utf-8"))
                result[mutation_path[0]][mutation_path[1]] = replacement
                mutated = (
                    json.dumps(
                        result,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("utf-8")

                failures = validator(mutated)

                self.assertTrue(
                    any("expected identity" in failure for failure in failures)
                )
                self.assertTrue(
                    any("exact closed" in failure for failure in failures)
                )

    def test_historical_build20_local_dmg_result_and_sources_are_bound(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene.current_macos_local_dmg_install_evidence_failures(),
            [],
        )
        result = json.loads(
            check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT.read_text(
                encoding="utf-8"
            )
        )
        result["mount"]["readOnly"] = False
        mutated_result = (
            json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        result_failures = (
            check_docs_hygiene.current_macos_local_dmg_install_evidence_failures(
                result_bytes=mutated_result
            )
        )
        self.assertTrue(
            any(
                "expected identity" in failure
                or "mount.readOnly" in failure
                for failure in result_failures
            )
        )

        runner = check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER
        test = check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_TEST
        source_failures = (
            check_docs_hygiene.current_macos_local_dmg_install_evidence_failures(
                source_bytes_by_path={
                    runner: runner.read_bytes() + b"\n",
                    test: test.read_bytes(),
                }
            )
        )
        self.assertTrue(
            any(
                "local DMG source SHA-256" in failure
                for failure in source_failures
            )
        )

    def test_historical_and_current_clean_home_test_hashes_are_separate(
        self,
    ) -> None:
        self.assertNotEqual(
            (
                check_docs_hygiene
                .MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256
            ),
            (
                check_docs_hygiene
                .CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256
            ),
        )
        self.assertNotEqual(
            (
                check_docs_hygiene
                .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256
            ),
            (
                check_docs_hygiene
                .CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256
            ),
        )

    def test_historical_build20_lifecycle_document_bindings_reject_drift(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .current_macos_clean_home_lifecycle_document_failures()
            ),
            [],
        )
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-20-local-v1.md",
            "docs/releases/1.0.0-build-22-local-v1.md",
        )
        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                start_marker = (
                    check_docs_hygiene
                    .CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
                )
                end_marker = (
                    check_docs_hygiene
                    .CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
                )
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                block = text[start:end]
                mutations = {
                    "result_sha": block.replace(
                        (
                            check_docs_hygiene
                            .CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
                        ),
                        "0" * 64,
                        1,
                    ),
                    "result_size": re.sub(
                        r"3,364(?:-byte| bytes)",
                        "3,365-byte",
                        block,
                        count=1,
                    ),
                    "repeatability": re.sub(
                        r"Both\s+clean-HOME\s+runners\s+were\s+invoked\s+"
                        r"twice\s+and\s+matched\s+their\s+canonical\s+"
                        r"results\.",
                        "One clean-HOME runner was invoked once.",
                        block,
                        count=1,
                    ),
                    "overclaim_boundary": re.sub(
                        r"production\s+readiness",
                        "production qualification",
                        block,
                        count=1,
                    ),
                    "historical_contamination": (
                        block
                        + "\nHistorical Build 14 is current lifecycle evidence.\n"
                    ),
                    "immediate_history_contamination": (
                        block
                        + "\nBuild 19 is part of this current lifecycle evidence.\n"
                    ),
                    "build14_relabel": (
                        block
                        + "\nBuild 14 is part of this current lifecycle evidence.\n"
                    ),
                    "build14_path": (
                        block
                        + "\nmacos-packaged-app-build-14-clean-home-install-v1.json\n"
                    ),
                    "build19_path": (
                        block
                        + "\nmacos-packaged-app-build-19-clean-home-install-v1.json\n"
                    ),
                    "build21_transfer": (
                        block
                        + (
                            "\nThis historical lifecycle evidence is current "
                            "Build 21 evidence and transfers to Build 21.\n"
                        )
                    ),
                    "contradictory_overclaim": (
                        block
                        + (
                            "\nThis current Build 20 evidence qualifies "
                            "clean-machine/account, DMG/Finder, "
                            "signed/notarized distribution, physical-device "
                            "behavior, and production readiness.\n"
                        )
                    ),
                }
                if (
                    "macos-packaged-app-build-20-local-dmg-install-v1.json"
                    in block
                ):
                    mutations.update(
                        {
                            "dmg_path": block.replace(
                                (
                                    "macos-packaged-app-build-20-"
                                    "local-dmg-install-v1.json"
                                ),
                                "removed-current-dmg-result.json",
                                1,
                            ),
                            "dmg_sha": block.replace(
                                (
                                    check_docs_hygiene
                                    .CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256
                                ),
                                "2" * 64,
                                1,
                            ),
                            "dmg_size": re.sub(
                                r"2,434(?:-byte| bytes)",
                                "2,435-byte",
                                block,
                                count=1,
                            ),
                        }
                    )
                if relative in {
                    "docs/releases/1.0.0-build-20-local-v1.md",
                    "docs/releases/1.0.0-build-22-local-v1.md",
                }:
                    mutations["runner_sha"] = block.replace(
                        (
                            check_docs_hygiene
                            .CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
                        ),
                        "1" * 64,
                        1,
                    )
                for label, mutated_block in mutations.items():
                    with self.subTest(relative=relative, label=label):
                        self.assertNotEqual(mutated_block, block)
                        mutated = (
                            text[:start] + mutated_block + text[end:]
                        )

                        failures = (
                            check_docs_hygiene
                            .current_macos_clean_home_lifecycle_document_failures(
                                document_text_by_relative={relative: mutated}
                            )
                        )

                        self.assertTrue(
                            any(
                                relative in failure
                                and "current Build 20" in failure
                                for failure in failures
                            ),
                            (
                                "lifecycle document mutation was accepted: "
                                f"{failures!r}"
                            ),
                        )

                without_start_marker = text.replace(start_marker, "", 1)
                marker_failures = (
                    check_docs_hygiene
                    .current_macos_clean_home_lifecycle_document_failures(
                        document_text_by_relative={
                            relative: without_start_marker
                        }
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exactly one start and end marker" in failure
                        for failure in marker_failures
                    )
                )

    def test_historical_build20_dmg_document_bindings_reject_drift(self) -> None:
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-20-local-v1.md",
            "docs/releases/1.0.0-build-22-local-v1.md",
        )
        bindings = (
            "macos-packaged-app-build-20-local-dmg-install-v1.json",
            (
                check_docs_hygiene
                .CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256
            ),
            "2,434",
        )
        for relative in targets:
            text = (check_docs_hygiene.ROOT / relative).read_text(
                encoding="utf-8"
            )
            for binding in bindings:
                with self.subTest(relative=relative, binding=binding):
                    mutated = text.replace(binding, "REMOVED_DMG_BINDING", 1)
                    self.assertNotEqual(mutated, text)
                    failures = (
                        check_docs_hygiene
                        .current_macos_clean_home_lifecycle_document_failures(
                            document_text_by_relative={relative: mutated}
                        )
                    )
                    self.assertTrue(
                        any(
                            relative in failure
                            and "current Build 20 DMG evidence" in failure
                            for failure in failures
                        ),
                        f"DMG document mutation was accepted: {failures!r}",
                    )

    def test_historical_build20_release_rejects_build21_transfer_claims(
        self,
    ) -> None:
        document_text = (
            check_docs_hygiene.HISTORICAL_BUILD20_RELEASE_DOC.read_text(
                encoding="utf-8"
            )
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        lifecycle_transfer = document_text.replace(
            end_marker,
            (
                "This historical lifecycle evidence is current Build 21 "
                "evidence and transfers to Build 21.\n\n"
                + end_marker
            ),
            1,
        )
        transfer_claims = (
            (
                "dmg_current_evidence",
                "This Build 20 DMG observation is current Build 21 DMG evidence.",
            ),
            (
                "dmg_belongs",
                "This Build 20 DMG observation belongs to Build 21.",
            ),
            (
                "dmg_is_evidence",
                "This Build 20 DMG observation is Build 21 evidence.",
            ),
            (
                "dmg_inherited",
                "Build 21 inherits this Build 20 DMG observation.",
            ),
            (
                "record_validates",
                "This record validates Build 21.",
            ),
            (
                "qualification_relies",
                "Build 21 relies on this record for qualification.",
            ),
            (
                "negation_smuggling",
                "This observation is not Build 21 evidence, but Build 21 "
                "inherits it.",
            ),
            (
                "unrelated_negation",
                "This Build 20 DMG observation belongs to Build 21, not "
                "Build 22.",
            ),
        )
        mutations = [("lifecycle", lifecycle_transfer)]
        mutations.extend(
            (
                label,
                document_text.replace(
                    "## Compatibility And Transition Boundary",
                    (
                        claim
                        + "\n\n"
                        + "## Compatibility And Transition Boundary"
                    ),
                    1,
                ),
            )
            for label, claim in transfer_claims
        )

        for label, mutated in mutations:
            with self.subTest(label=label):
                self.assertNotEqual(mutated, document_text)
                failures = (
                    check_docs_hygiene
                    .historical_build20_release_document_failures(mutated)
                )
                self.assertTrue(
                    any(
                        "transfer or relabeling claim" in failure
                        or "exact immutable document SHA-256" in failure
                        for failure in failures
                    ),
                    f"Build 20 transfer overclaim was accepted: {failures!r}",
                )

    def test_current_build19_runtime_chat_sqlite_cross_process_record_rejects_drift(
        self,
    ) -> None:
        document_text = (
            check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC.read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            (
                check_docs_hygiene
                .current_runtime_chat_sqlite_cross_process_document_failures(
                    document_text
                )
            ),
            [],
        )

        helper_path = (
            "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
            "RuntimeChatSQLiteCrossProcessQA.swift"
        )
        runner_path = "script/run_macos_runtime_chat_cross_process_smoke.py"
        helper_sha = (
            check_docs_hygiene
            .LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS[
                helper_path
            ][1]
        )
        runner_sha = (
            check_docs_hygiene
            .LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS[
                runner_path
            ][1]
        )
        mutations = {
            "busy_timeout": re.sub(
                r"(\bproduction\b.{0,100})(?:five-second|5-second)",
                r"\1unbounded",
                document_text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            ),
            "stable_message": document_text.replace(
                (
                    check_docs_hygiene
                    .CURRENT_RUNTIME_CHAT_SQLITE_STABLE_BUSY_MESSAGE
                ),
                "Runtime chat history failed.",
                1,
            ),
            "helper_identity": document_text.replace(helper_sha, "0" * 64, 1),
            "runner_identity": document_text.replace(runner_sha, "1" * 64, 1),
            "live_count": document_text.replace(
                "48+48=96",
                "48+48=95",
                1,
            ),
            "third_process": re.sub(
                r"third(?: independent|-process).{0,40}readback"
                r".{0,40}process",
                "in-process readback",
                document_text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            ),
            "archive_overclaim": re.sub(
                r"not an? (?:retained (?:Build 19 )?)?archive member",
                "a retained Build 19 archive member",
                document_text,
                count=1,
                flags=re.IGNORECASE,
            ),
        }
        for label, mutated in mutations.items():
            with self.subTest(label=label):
                self.assertNotEqual(mutated, document_text)
                failures = (
                    check_docs_hygiene
                    .current_runtime_chat_sqlite_cross_process_document_failures(
                        mutated
                    )
                )
                self.assertTrue(
                    any(
                        "Runtime-chat SQLite" in failure
                        or "source inventory" in failure
                        for failure in failures
                    ),
                    f"Runtime-chat SQLite mutation {label!r} was accepted",
                )

    def test_current_build19_runtime_chat_sqlite_source_bindings_reject_drift(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene.current_runtime_chat_sqlite_source_failures(),
            [],
        )
        source_paths = tuple(
            (
                check_docs_hygiene
                .LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS
            )
        )
        test_path = (
            "apps/macos/CompanionCore/Tests/"
            "SQLiteRuntimeChatEventStoreTests.swift"
        )
        sources = {
            relative: (
                check_docs_hygiene.ROOT / relative
            ).read_bytes()
            for relative in source_paths + (test_path,)
        }

        missing_test = dict(sources)
        test_name = check_docs_hygiene.CURRENT_RUNTIME_CHAT_SQLITE_SWIFT_TESTS[1]
        missing_test[test_path] = sources[test_path].replace(
            test_name.encode("utf-8"),
            b"removedSQLiteBusyRegression",
            1,
        )
        self.assertTrue(
            any(
                "exact Swift regression" in failure
                for failure in (
                    check_docs_hygiene
                    .current_runtime_chat_sqlite_source_failures(missing_test)
                )
            )
        )

        changed_runner = dict(sources)
        runner_path = "script/run_macos_runtime_chat_cross_process_smoke.py"
        changed_runner[runner_path] = sources[runner_path] + b"\n"
        self.assertTrue(
            any(
                runner_path in failure
                and "source inventory identity" in failure
                for failure in (
                    check_docs_hygiene
                    .current_runtime_chat_sqlite_source_failures(changed_runner)
                )
            )
        )

    def test_historical_build21_abrupt_recovery_documents_reject_overclaims(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_runtime_chat_sqlite_abrupt_recovery_document_failures
        )
        self.assertEqual(validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-22-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        )

        for relative in targets:
            text = (check_docs_hygiene.ROOT / relative).read_text(
                encoding="utf-8"
            )
            overclaims = (
                (
                    "production_and_power_loss",
                    "It proves the production append crash point and "
                    "power-loss recovery.",
                ),
                ("power_loss_passed", "Power-loss recovery passed."),
                (
                    "power_loss_evidence",
                    "This is power-loss recovery evidence.",
                ),
                (
                    "kernel_crash_supported",
                    "Kernel-crash recovery is supported.",
                ),
                (
                    "clause_negation_smuggling",
                    "Power-loss recovery is not yet qualified, but "
                    "kernel-crash recovery passed.",
                ),
                (
                    "unrelated_negation",
                    "Power-loss recovery passed, not merely simulated.",
                ),
                (
                    "production_append_synonym",
                    "Production append recovery passed.",
                ),
                (
                    "loss_of_power_synonym",
                    "Recovery after loss of power passed.",
                ),
            )
            for label, claim in overclaims:
                with self.subTest(
                    relative=relative,
                    mutation=f"overclaim_{label}",
                ):
                    overclaim = text.replace(
                        end_marker,
                        claim + "\n\n" + end_marker,
                        1,
                    )
                    self.assertNotEqual(overclaim, text)
                    failures = validator(
                        document_text_by_relative={relative: overclaim}
                    )
                    self.assertTrue(
                        any(
                            relative in failure
                            and (
                                "forbidden-scope claim" in failure
                                or "exact bounded block SHA-256" in failure
                            )
                            for failure in failures
                        ),
                        (
                            "abrupt-recovery overclaim was accepted: "
                            f"{failures!r}"
                        ),
                    )

            with self.subTest(relative=relative, mutation="marker"):
                without_start = text.replace(start_marker, "", 1)
                self.assertNotEqual(without_start, text)
                failures = validator(
                    document_text_by_relative={relative: without_start}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exactly one start and end marker" in failure
                        for failure in failures
                    )
                )

            with self.subTest(relative=relative, mutation="limitation"):
                block_start = text.index(start_marker) + len(start_marker)
                block_end = text.index(end_marker)
                block = text[block_start:block_end]
                mutated_block = re.sub(
                    r"not\s+clean-machine,\s+signed-distribution,\s+or\s+"
                    r"physical-device\s+evidence",
                    "clean-machine and device evidence",
                    block,
                    count=1,
                )
                self.assertNotEqual(mutated_block, block)
                missing_limitation = (
                    text[:block_start]
                    + mutated_block
                    + text[block_end:]
                )
                failures = validator(
                    document_text_by_relative={
                        relative: missing_limitation
                    }
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "distribution and device exclusion" in failure
                        for failure in failures
                    )
                )

    def test_current_build21_abrupt_recovery_result_is_exact_and_typed(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_runtime_chat_sqlite_abrupt_recovery_evidence_failures
        )
        self.assertEqual(validator(), [])
        result = json.loads(
            check_docs_hygiene
            .CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT.read_text(
                encoding="ascii"
            )
        )

        mutations = []
        boolean_schema = copy.deepcopy(result)
        boolean_schema["schemaVersion"] = True
        mutations.append(boolean_schema)

        missing_limitation = copy.deepcopy(result)
        missing_limitation["limitations"].remove(
            "not-production-append-crash-point"
        )
        mutations.append(missing_limitation)

        false_reap = copy.deepcopy(result)
        false_reap["abruptTermination"][
            "writerProcessReapedBeforeJournalObservation"
        ] = False
        mutations.append(false_reap)

        for index, mutated in enumerate(mutations):
            with self.subTest(index=index):
                payload = (
                    json.dumps(
                        mutated,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("ascii")
                failures = validator(payload)
                self.assertTrue(
                    any("expected abrupt recovery identity" in item
                        for item in failures)
                )
                self.assertTrue(
                    any("exact closed abrupt" in item for item in failures)
                )

    def test_current_android_drawer_search_document_bindings_reject_drift(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .current_android_drawer_search_document_failures()
            ),
            [],
        )
        targets = (
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
        )
        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                start_marker = (
                    check_docs_hygiene
                    .CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START
                )
                end_marker = (
                    check_docs_hygiene
                    .CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_END
                )
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                block = text[start:end]
                normalized_block = re.sub(r"\s+", " ", block).strip()
                mutations = {
                    "touch_action": normalized_block.replace(
                        "explicit touch Search action",
                        "keyboard-only Search action",
                        1,
                    ),
                    "action_state": normalized_block.replace(
                        "exact same-query pending states",
                        "every pending state",
                        1,
                    ),
                    "pending_query": normalized_block.replace(
                        "Only the exact current pending query",
                        "Every pending query",
                        1,
                    ),
                    "result_authority": normalized_block.replace(
                        "Only an exact current-query remote response",
                        "Any remote response",
                        1,
                    ),
                    "full_test_count": normalized_block.replace(
                        "1,194-test",
                        "1,193-test",
                        1,
                    ),
                    "search_test_count": normalized_block.replace(
                        "15 search-related RuntimeClientViewModelTest",
                        "14 search-related RuntimeClientViewModelTest",
                        1,
                    ),
                    "lint_warning_count": normalized_block.replace(
                        "2 SDK-version warnings",
                        "3 SDK-version warnings",
                        1,
                    ),
                    "archive_boundary": re.sub(
                        r"is not part of the immutable Build 17 archive and "
                        r"(?:is|was) first source-bound by the immutable "
                        r"Build 18 archive",
                        "is part of the immutable Build 17 archive and is "
                        "not source-bound by the immutable Build 18 archive",
                        normalized_block,
                        count=1,
                    ),
                    "stale_evidence": (
                        normalized_block
                        + "\nThe previous gate still passes 1,179 tests.\n"
                    ),
                    "stale_response_overclaim": (
                        normalized_block
                        + "\nStale remote responses are adopted.\n"
                    ),
                    "archived_session_overclaim": (
                        normalized_block
                        + "\nArchived sessions are included in current results.\n"
                    ),
                    "provider_device_overclaim": (
                        normalized_block
                        + (
                            "\nProvider, device, network, and signing behavior "
                            "passed qualification.\n"
                        )
                    ),
                    "contradictory_device_claim": (
                        normalized_block
                        + "\nPhysical touch and TalkBack pass qualification.\n"
                    ),
                }
                for label, mutated_block in mutations.items():
                    with self.subTest(relative=relative, label=label):
                        self.assertNotEqual(mutated_block, normalized_block)
                        mutated = (
                            text[:start]
                            + "\n"
                            + mutated_block
                            + "\n"
                            + text[end:]
                        )

                        failures = (
                            check_docs_hygiene
                            .current_android_drawer_search_document_failures(
                                document_text_by_relative={relative: mutated}
                            )
                        )

                        self.assertTrue(
                            any(
                                relative in failure
                                and "current Android drawer search" in failure
                                for failure in failures
                            ),
                            (
                                "Android drawer search document mutation was "
                                f"accepted: {failures!r}"
                            ),
                        )

                without_start_marker = text.replace(start_marker, "", 1)
                marker_failures = (
                    check_docs_hygiene
                    .current_android_drawer_search_document_failures(
                        document_text_by_relative={
                            relative: without_start_marker
                        }
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exactly one start and end marker" in failure
                        for failure in marker_failures
                    )
                )
                without_end_marker = text.replace(end_marker, "", 1)
                end_marker_failures = (
                    check_docs_hygiene
                    .current_android_drawer_search_document_failures(
                        document_text_by_relative={
                            relative: without_end_marker
                        }
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exactly one start and end marker" in failure
                        for failure in end_marker_failures
                    )
                )

                marker_start = text.index(start_marker)
                marker_end = text.index(end_marker) + len(end_marker)
                marked_block = text[marker_start:marker_end]
                duplicate_marker_failures = (
                    check_docs_hygiene
                    .current_android_drawer_search_document_failures(
                        document_text_by_relative={
                            relative: text + "\n" + marked_block + "\n"
                        }
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exactly one start and end marker" in failure
                        for failure in duplicate_marker_failures
                    )
                )
                relocated = (
                    text[:marker_start]
                    + text[marker_end:]
                    + "\n## Historical Checkpoint\n\n"
                    + marked_block
                    + "\n"
                )
                relocation_failures = (
                    check_docs_hygiene
                    .current_android_drawer_search_document_failures(
                        document_text_by_relative={relative: relocated}
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "canonical current section" in failure
                        for failure in relocation_failures
                    ),
                    (
                        "historically relocated Android drawer search block "
                        f"was accepted: {relocation_failures!r}"
                    ),
                )

    def test_historical_build14_clean_home_current_identity_mutations_are_rejected(
        self,
    ) -> None:
        cases = (
            (
                (
                    check_docs_hygiene
                    .MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT
                ),
                (
                    check_docs_hygiene
                    .macos_clean_home_installed_app_evidence_failures
                ),
            ),
            (
                (
                    check_docs_hygiene
                    .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
                ),
                (
                    check_docs_hygiene
                    .macos_clean_home_installed_state_recovery_evidence_failures
                ),
            ),
        )
        mutations = (
            (
                ("app", "buildNumber"),
                check_docs_hygiene.LOCAL_RELEASE_BUILD_NUMBER,
            ),
            (
                ("release", "releaseId"),
                check_docs_hygiene.LOCAL_RELEASE_ID,
            ),
            (
                ("release", "archiveSha256"),
                check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
            ),
            (
                ("release", "manifestSha256"),
                check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
            ),
        )

        for expected_result, validator in cases:
            for path, replacement in mutations:
                with self.subTest(scope=expected_result["scope"], path=path):
                    mutated_result = json.loads(json.dumps(expected_result))
                    mutated_result[path[0]][path[1]] = replacement
                    result_bytes = (
                        json.dumps(
                            mutated_result,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("utf-8")

                    failures = validator(result_bytes)

                    self.assertTrue(
                        any(
                            "expected identity" in failure
                            for failure in failures
                        )
                    )
                    self.assertTrue(
                        any("exact closed" in failure for failure in failures)
                    )

    def test_historical_build14_marketing_version_is_frozen_in_source(
        self,
    ) -> None:
        source = (
            check_docs_hygiene.ROOT
            / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        expected_result_start = source.index(
            "MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT = {"
        )
        expected_result_end = source.index(
            "MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT = {"
        )
        installed_app_contract = source[
            expected_result_start:expected_result_end
        ]

        self.assertIn(
            '"marketingVersion": HISTORICAL_BUILD14_MARKETING_VERSION',
            installed_app_contract,
        )
        self.assertNotIn(
            '"marketingVersion": LOCAL_RELEASE_MARKETING_VERSION',
            installed_app_contract,
        )

    def test_current_android_manifest_readback_contract_rejects_mutations(
        self,
    ) -> None:
        manifest_path = (
            check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR
            / f"{check_docs_hygiene.LOCAL_RELEASE_ID}.manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            (
                check_docs_hygiene
                .current_release_android_manifest_readback_failures(manifest)
            ),
            [],
        )
        mutations = {
            "apk_missing_policy_field": (
                "apkManifestReadback",
                {
                    **check_docs_hygiene.LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK,
                    "verifiedFields": [
                        "allowBackup",
                        "dataExtractionRules",
                    ],
                },
            ),
            "apk_wrong_tool": (
                "apkManifestReadback",
                {
                    **check_docs_hygiene.LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK,
                    "tool": "aapt2 dump xmltree",
                },
            ),
            "bundle_reordered_fields": (
                "bundleManifestReadback",
                {
                    **check_docs_hygiene.LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK,
                    "verifiedFields": list(
                        reversed(
                            check_docs_hygiene
                            .LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK[
                                "verifiedFields"
                            ]
                        )
                    ),
                },
            ),
            "bundle_wrong_member": (
                "bundleManifestReadback",
                {
                    **check_docs_hygiene.LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK,
                    "member": "android/apk/app-release-unsigned.apk",
                },
            ),
        }

        for label, (readback_key, replacement) in mutations.items():
            with self.subTest(label=label):
                mutated_manifest = json.loads(json.dumps(manifest))
                mutated_manifest["platforms"]["android"][
                    readback_key
                ] = replacement

                failures = (
                    check_docs_hygiene
                    .current_release_android_manifest_readback_failures(
                        mutated_manifest
                    )
                )

                self.assertTrue(
                    any(readback_key in failure for failure in failures),
                    f"manifest readback mutation {label!r} was accepted",
                )

    def test_build15_backup_policy_document_claim_mutations_are_rejected(
        self,
    ) -> None:
        claims = (
            check_docs_hygiene
            .LOCAL_RELEASE_ANDROID_BACKUP_POLICY_REQUIRED_CLAIMS
        )
        document_text = "\n".join(claims)
        self.assertEqual(
            (
                check_docs_hygiene
                .current_release_android_backup_policy_document_failures(
                    document_text
                )
            ),
            [],
        )

        for claim in claims:
            with self.subTest(claim=claim):
                mutated = document_text.replace(
                    claim,
                    "REMOVED_BACKUP_POLICY_CLAIM",
                    1,
                )
                failures = (
                    check_docs_hygiene
                    .current_release_android_backup_policy_document_failures(
                        mutated
                    )
                )
                self.assertTrue(
                    any("missing exact" in failure for failure in failures),
                    f"backup-policy claim mutation {claim!r} was accepted",
                )

    def test_macos_clean_home_installed_state_recovery_result_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .macos_clean_home_installed_state_recovery_evidence_failures()
            ),
            [],
        )
        result = json.loads(
            (
                check_docs_hygiene
                .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT
                .read_text(encoding="utf-8")
            )
        )
        result["stateRecovery"][
            "installedStateBytesAndModesUnchangedAcrossRelaunch"
        ] = 1
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
            check_docs_hygiene
            .macos_clean_home_installed_state_recovery_evidence_failures(
                mutated
            )
        )

        self.assertTrue(
            any("expected identity" in failure for failure in failures)
        )
        self.assertTrue(any("exact closed" in failure for failure in failures))

    def test_macos_clean_home_installed_state_recovery_sources_match_recorded_bytes(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .macos_clean_home_installed_state_recovery_source_failures()
            ),
            [],
        )
        with patch.object(
            check_docs_hygiene,
            (
                "CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_"
                "EXPECTED_RUNNER_SHA256"
            ),
            "0" * 64,
        ):
            failures = (
                check_docs_hygiene
                .macos_clean_home_installed_state_recovery_source_failures()
            )
        self.assertTrue(
            any(
                "run_macos_clean_home_installed_state_recovery_smoke.py"
                in failure
                for failure in failures
            )
        )

    def test_macos_packaged_state_recovery_result_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .macos_packaged_state_recovery_evidence_failures()
            ),
            [],
        )
        result = json.loads(
            check_docs_hygiene.MACOS_PACKAGED_STATE_RECOVERY_RESULT.read_text(
                encoding="utf-8"
            )
        )
        result["stateRecovery"]["sqliteCanaryUnchangedAcrossRuns"] = 1
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
            check_docs_hygiene
            .macos_packaged_state_recovery_evidence_failures(mutated)
        )

        self.assertTrue(
            any("expected identity" in failure for failure in failures)
        )
        self.assertTrue(any("exact closed" in failure for failure in failures))

    def test_macos_packaged_state_recovery_sources_match_recorded_bytes(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .macos_packaged_state_recovery_source_failures()
            ),
            [],
        )
        with patch.object(
            check_docs_hygiene,
            "MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256",
            "0" * 64,
        ):
            failures = (
                check_docs_hygiene
                .macos_packaged_state_recovery_source_failures()
            )
        self.assertTrue(
            any(
                "run_macos_packaged_app_state_recovery_smoke.py"
                in failure
                for failure in failures
            )
        )

    def test_build12_state_recovery_result_remains_unpublished(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .historical_build12_state_recovery_absence_failures()
            ),
            [],
        )
        self.assertTrue(
            (
                check_docs_hygiene
                .historical_build12_state_recovery_absence_failures(
                    result_exists=True
                )
            )
        )

    def test_historical_macos_packaged_lifecycle_result_is_preserved(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene
            .historical_macos_packaged_lifecycle_evidence_failures(),
            [],
        )
        result = json.loads(
            check_docs_hygiene
            .HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RESULT
            .read_text(encoding="utf-8")
        )
        result["app"]["buildNumber"] = 10
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
            check_docs_hygiene
            .historical_macos_packaged_lifecycle_evidence_failures(mutated)
        )

        self.assertTrue(any("expected identity" in failure for failure in failures))
        self.assertTrue(any("exact closed" in failure for failure in failures))

    def test_historical_release_documents_follow_current_ledger_record(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene.historical_local_release_document_failures(),
            [],
        )

    def test_historical_build17_immutable_identities_are_pinned(self) -> None:
        document_text = (
            check_docs_hygiene.ROOT
            / "docs/releases/1.0.0-build-17-local-v1.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            check_docs_hygiene
            .historical_build17_release_document_failures(document_text),
            [],
        )

        mutations = {
            "archive": check_docs_hygiene.HISTORICAL_BUILD17_ARCHIVE_SHA256,
            "manifest": (
                check_docs_hygiene.HISTORICAL_BUILD17_MANIFEST_SHA256
            ),
            "source_inventory": (
                check_docs_hygiene
                .HISTORICAL_BUILD17_SOURCE_INVENTORY_SHA256
            ),
            "source_snapshot": (
                check_docs_hygiene
                .HISTORICAL_BUILD17_SOURCE_SNAPSHOT_SHA256
            ),
            "primary_result": (
                check_docs_hygiene
                .HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SHA256
            ),
            "confirmation": (
                check_docs_hygiene
                .HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SHA256
            ),
            "lifecycle_install": (
                check_docs_hygiene
                .HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SHA256
            ),
            "lifecycle_recovery": (
                check_docs_hygiene
                .HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SHA256
            ),
        }
        for label, identity in mutations.items():
            with self.subTest(label=label):
                mutated = document_text.replace(identity, "0" * 64)
                self.assertNotEqual(mutated, document_text)
                failures = (
                    check_docs_hygiene
                    .historical_build17_release_document_failures(mutated)
                )
                self.assertTrue(
                    any("Build 17" in failure for failure in failures),
                    f"Build 17 identity mutation {label!r} was accepted",
                )

    def test_historical_build17_lifecycle_markers_remain_distinct(self) -> None:
        document_text = (
            check_docs_hygiene.ROOT
            / "docs/releases/1.0.0-build-17-local-v1.md"
        ).read_text(encoding="utf-8")
        start = (
            check_docs_hygiene
            .HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START
        )
        end = (
            check_docs_hygiene.HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_END
        )
        current_start = (
            check_docs_hygiene
            .CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        current_end = (
            check_docs_hygiene
            .CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        mutations = {
            "missing_start": document_text.replace(start, "", 1),
            "missing_end": document_text.replace(end, "", 1),
            "duplicate": document_text + f"\n{start}\n{end}\n",
            "current_build19_markers": document_text.replace(
                start,
                current_start,
                1,
            ).replace(end, current_end, 1),
        }
        for label, mutated in mutations.items():
            with self.subTest(label=label):
                failures = (
                    check_docs_hygiene
                    .historical_build17_release_document_failures(mutated)
                )
                self.assertTrue(
                    any(
                        "historical Build 17 lifecycle block" in failure
                        for failure in failures
                    ),
                    f"Build 17 lifecycle marker mutation {label!r} was accepted",
                )

    def test_historical_build18_immutable_identities_survive_build19(self) -> None:
        document_text = (
            check_docs_hygiene.ROOT
            / "docs/releases/1.0.0-build-18-local-v1.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            check_docs_hygiene.historical_build18_release_document_failures(
                document_text
            ),
            [],
        )
        identities = {
            "archive": check_docs_hygiene.HISTORICAL_BUILD18_ARCHIVE_SHA256,
            "manifest": check_docs_hygiene.HISTORICAL_BUILD18_MANIFEST_SHA256,
            "sidecar": check_docs_hygiene.HISTORICAL_BUILD18_CHECKSUM_SHA256,
            "source": (
                check_docs_hygiene
                .HISTORICAL_BUILD18_SOURCE_SNAPSHOT_SHA256
            ),
            "source_inventory": (
                check_docs_hygiene
                .HISTORICAL_BUILD18_SOURCE_INVENTORY_SHA256
            ),
            "installed_app": (
                check_docs_hygiene
                .HISTORICAL_BUILD18_INSTALLED_APP_RESULT_SHA256
            ),
            "state_recovery": (
                check_docs_hygiene
                .HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_SHA256
            ),
        }
        for label, identity in identities.items():
            with self.subTest(label=label):
                mutated = document_text.replace(identity, "0" * 64)
                self.assertNotEqual(mutated, document_text)
                failures = (
                    check_docs_hygiene
                    .historical_build18_release_document_failures(mutated)
                )
                self.assertTrue(
                    any("Build 18 binding" in failure for failure in failures),
                    f"Build 18 identity mutation {label!r} was accepted",
                )

    def test_historical_build19_immutable_identities_survive_build20(self) -> None:
        document_text = (
            check_docs_hygiene.ROOT
            / "docs/releases/1.0.0-build-19-local-v1.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            check_docs_hygiene.historical_build19_release_document_failures(
                document_text
            ),
            [],
        )
        identities = {
            "archive": check_docs_hygiene.HISTORICAL_BUILD19_ARCHIVE_SHA256,
            "manifest": check_docs_hygiene.HISTORICAL_BUILD19_MANIFEST_SHA256,
            "sidecar": check_docs_hygiene.HISTORICAL_BUILD19_CHECKSUM_SHA256,
            "primary": (
                check_docs_hygiene
                .HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SHA256
            ),
            "confirmation": (
                check_docs_hygiene
                .HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SHA256
            ),
            "source": (
                check_docs_hygiene
                .HISTORICAL_BUILD19_SOURCE_SNAPSHOT_SHA256
            ),
            "installed_app": (
                check_docs_hygiene
                .HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SHA256
            ),
            "state_recovery": (
                check_docs_hygiene
                .HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SHA256
            ),
        }
        for label, identity in identities.items():
            with self.subTest(label=label):
                mutated = document_text.replace(identity, "0" * 64)
                self.assertNotEqual(mutated, document_text)
                failures = (
                    check_docs_hygiene
                    .historical_build19_release_document_failures(mutated)
                )
                self.assertTrue(
                    any("Build 19 binding" in failure for failure in failures),
                    f"Build 19 identity mutation {label!r} was accepted",
                )
        marker_mutation = (
            document_text
            + "\n"
            + check_docs_hygiene.CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
            + "\n"
            + check_docs_hygiene.CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
            + "\n"
        )
        marker_failures = (
            check_docs_hygiene.historical_build19_release_document_failures(
                marker_mutation
            )
        )
        self.assertTrue(
            any(
                "current Build 20 lifecycle markers" in failure
                for failure in marker_failures
            )
        )
        stale_readback = document_text.replace(
            "Run this historical source-bound readback with historical mode:",
            "Run the current source-bound readback without historical mode:",
            1,
        )
        stale_readback_failures = (
            check_docs_hygiene.historical_build19_release_document_failures(
                stale_readback
            )
        )
        self.assertTrue(
            any(
                "stale current-state claim" in failure
                for failure in stale_readback_failures
            )
        )

    def test_historical_build21_immutable_identities_survive_build22(self) -> None:
        document_text = (
            check_docs_hygiene.ROOT
            / "docs/releases/1.0.0-build-21-local-v1.md"
        ).read_text(encoding="utf-8")
        validator = (
            check_docs_hygiene.historical_build21_release_document_failures
        )
        self.assertEqual(validator(document_text), [])

        identities = {
            "archive": check_docs_hygiene.HISTORICAL_BUILD21_ARCHIVE_SHA256,
            "manifest": (
                check_docs_hygiene.HISTORICAL_BUILD21_MANIFEST_SHA256
            ),
            "sidecar": (
                check_docs_hygiene.HISTORICAL_BUILD21_CHECKSUM_SHA256
            ),
            "prepublication": (
                check_docs_hygiene
                .HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SHA256
            ),
            "publication": (
                check_docs_hygiene
                .HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SHA256
            ),
            "source": (
                check_docs_hygiene
                .HISTORICAL_BUILD21_SOURCE_SNAPSHOT_SHA256
            ),
            "source_inventory": (
                check_docs_hygiene
                .HISTORICAL_BUILD21_SOURCE_INVENTORY_SHA256
            ),
        }
        for label, identity in identities.items():
            with self.subTest(label=label):
                mutated = document_text.replace(identity, "0" * 64, 1)
                self.assertNotEqual(mutated, document_text)
                self.assertTrue(
                    any(
                        "immutable Build 21 binding" in failure
                        for failure in validator(mutated)
                    ),
                    f"Build 21 identity mutation {label!r} was accepted",
                )

        historical_claim = (
            "Build 21 is an immutable historical local qualification record"
        )
        current_claim = "Build 21 is the current local qualification record"
        mutated = document_text.replace(historical_claim, current_claim, 1)
        self.assertNotEqual(mutated, document_text)
        failures = validator(mutated)
        self.assertTrue(
            any("immutable Build 21 binding" in failure for failure in failures)
        )
        self.assertTrue(
            any("stale current-state claim" in failure for failure in failures)
        )

    def test_readme_current_release_guidance_follows_ledger(self) -> None:
        self.assertEqual(
            check_docs_hygiene.CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION,
            run_clean_release_reproducibility.RESULT_PATH_VERSION,
        )
        ledger_bytes = check_docs_hygiene.LOCAL_RELEASE_LEDGER.read_bytes()
        entries = check_docs_hygiene.parse_release_version_ledger(
            ledger_bytes
        )
        current = entries[-1]
        previous = entries[-2]
        readme = check_docs_hygiene.README_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            check_docs_hygiene.readme_current_local_release_failures(
                ledger_bytes=ledger_bytes,
                readme_text=readme,
            ),
            [],
        )

        current_id = (
            f"aetherlink-{current.marketing_version}"
            f"+{current.build_number}-local-v1"
        )
        previous_id = (
            f"aetherlink-{previous.marketing_version}"
            f"+{previous.build_number}-local-v1"
        )
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
        mutations = {
            "ledger": (
                f"shared build number `{current.build_number}`",
                f"shared build number `{previous.build_number}`",
                "current ledger claim",
            ),
            "output": (
                f"dist/releases/{current_id}/",
                f"dist/releases/{previous_id}/",
                "current output",
            ),
            "qualification": (
                f"The Build {current.build_number} qualification runner",
                f"The Build {previous.build_number} qualification runner",
                "current qualification runner",
            ),
            "record": (
                current_doc,
                previous_doc,
                "current release-record guidance",
            ),
            "historical-range": (
                f"Builds 1 through {current.build_number - 1}",
                f"Builds 1 through {previous.build_number - 1}",
                "historical release range",
            ),
        }
        for label, (before, after, expected_failure) in mutations.items():
            with self.subTest(label=label):
                mutated = readme.replace(before, after, 1)
                self.assertNotEqual(mutated, readme)
                failures = (
                    check_docs_hygiene
                    .readme_current_local_release_failures(
                        ledger_bytes=ledger_bytes,
                        readme_text=mutated,
                    )
                )
                self.assertTrue(
                    any(
                        expected_failure in failure
                        for failure in failures
                    ),
                    f"README mutation {label!r} was accepted: "
                    f"{failures!r}",
                )

        future_build_number = current.build_number + 1
        future_id = (
            f"aetherlink-{current.marketing_version}"
            f"+{future_build_number}-local-v1"
        )
        future_doc = (
            "docs/releases/"
            f"{current.marketing_version}-build-"
            f"{future_build_number}-local-v1.md"
        )
        future_ledger = (
            ledger_bytes
            + f"{future_build_number}\t{current.marketing_version}\n".encode(
                "ascii"
            )
        )
        future_readme = readme
        future_replacements = (
            (
                f"shared build number `{current.build_number}`",
                f"shared build number `{future_build_number}`",
            ),
            (current_id, future_id),
            (
                f"The Build {current.build_number} qualification runner",
                f"The Build {future_build_number} qualification runner",
            ),
            (
                f"Build {current.build_number} preserves compliance profile",
                f"Build {future_build_number} preserves compliance profile",
            ),
            (
                f"Builds 1 through {current.build_number - 1}",
                f"Builds 1 through {future_build_number - 1}",
            ),
            (
                f"build {current.build_number} local qualification record",
                f"build {future_build_number} local qualification record",
            ),
            (current_doc, future_doc),
        )
        for before, after in future_replacements:
            mutated = future_readme.replace(before, after)
            self.assertNotEqual(
                mutated,
                future_readme,
                f"future README replacement was absent: {before!r}",
            )
            future_readme = mutated
        self.assertEqual(
            check_docs_hygiene.readme_current_local_release_failures(
                ledger_bytes=future_ledger,
                readme_text=future_readme,
            ),
            [],
        )

        future_result = (
            f"{future_id}-two-root-v"
            f"{check_docs_hygiene.CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}"
            ".json"
        )
        future_prepublication = (
            f"{future_id}-two-root-v"
            f"{check_docs_hygiene.CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}"
            "-prepublication.json"
        )
        future_mutations = {
            "result": (
                future_result,
                f"{current_id}-two-root-v"
                f"{check_docs_hygiene.CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}"
                ".json",
                "current reproducibility result",
            ),
            "prepublication": (
                future_prepublication,
                f"{current_id}-two-root-v"
                f"{check_docs_hygiene.CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}"
                "-prepublication.json",
                "current reproducibility prepublication",
            ),
            "compliance": (
                f"Build {future_build_number} preserves compliance profile",
                f"Build {current.build_number} preserves compliance profile",
                "current compliance profile",
            ),
        }
        for label, (before, after, expected_failure) in (
            future_mutations.items()
        ):
            with self.subTest(future_build_mutation=label):
                mutated = future_readme.replace(before, after, 1)
                self.assertNotEqual(mutated, future_readme)
                failures = (
                    check_docs_hygiene
                    .readme_current_local_release_failures(
                        ledger_bytes=future_ledger,
                        readme_text=mutated,
                    )
                )
                self.assertTrue(
                    any(
                        expected_failure in failure
                        for failure in failures
                    ),
                    f"future README mutation {label!r} was accepted: "
                    f"{failures!r}",
                )

    def test_multilingual_full_matrix_v3_evidence_is_current(self) -> None:
        self.assertEqual(
            check_docs_hygiene
            .ollama_multilingual_full_matrix_v3_evidence_failures(),
            [],
        )
        relative = "docs/handoff.md"
        handoff = (
            check_docs_hygiene.ROOT / relative
        ).read_text(encoding="utf-8")
        mutations = {
            "ranking": (
                "76/80 ranking",
                "75/80 ranking",
                "76/80 ranking comparisons",
            ),
            "repeatability": (
                "80/80 repeatability",
                "79/80 repeatability",
                "80/80 repeatability comparisons",
            ),
            "Korean coordinate": (
                "Korean and French scenario ordinal 2",
                "Japanese and French scenario ordinal 2",
                "Korean scenario ordinal 2",
            ),
            "French coordinate": (
                "Korean and French scenario ordinal 2",
                "Korean and English scenario ordinal 2",
                "French scenario ordinal 2",
            ),
            "ordinal": (
                "Korean and French scenario ordinal 2",
                "Korean and French scenario ordinal 3",
                "Korean scenario ordinal 2",
            ),
            "recovery": (
                "Both\n  fresh-provider recoveries pass",
                "Both\n  fresh-provider recoveries fail",
                "fresh-provider recoveries pass",
            ),
        }
        for label, (before, after, expected_failure) in mutations.items():
            with self.subTest(v3_claim_mutation=label):
                mutated = handoff.replace(before, after, 1)
                self.assertNotEqual(mutated, handoff)
                failures = (
                    check_docs_hygiene
                    .ollama_multilingual_full_matrix_v3_evidence_failures(
                        document_text_by_relative={relative: mutated}
                    )
                )
                self.assertTrue(
                    any(
                        expected_failure in failure
                        for failure in failures
                    ),
                    f"V3 claim mutation {label!r} was accepted: "
                    f"{failures!r}",
                )

    def test_build16_success_and_failed_repetition_history_is_preserved(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene
            .historical_build16_reproducibility_failures(),
            [],
        )
        document_text = (
            check_docs_hygiene.HISTORICAL_BUILD16_DOC.read_text(
                encoding="utf-8"
            )
        )
        result_paths = (
            check_docs_hygiene.HISTORICAL_BUILD16_RESULT,
            check_docs_hygiene.HISTORICAL_BUILD16_FAILED_ATTEMPT,
            check_docs_hygiene.HISTORICAL_BUILD16_FAILED_CONFIRMATION,
        )
        result_bytes = {
            str(path.relative_to(check_docs_hygiene.ROOT)): path.read_bytes()
            for path in result_paths
        }

        missing_nontransfer = document_text.replace(
            "Build 17 does not retroactively qualify Build 16.",
            "Build 16 history boundary removed.",
            1,
        )
        self.assertTrue(
            any(
                "missing exact Build 16 history claim" in failure
                for failure in (
                    check_docs_hygiene
                    .historical_build16_reproducibility_failures(
                        document_text=missing_nontransfer,
                        result_bytes_by_path=result_bytes,
                    )
                )
            )
        )

        attempt_relative = str(
            check_docs_hygiene.HISTORICAL_BUILD16_FAILED_ATTEMPT.relative_to(
                check_docs_hygiene.ROOT
            )
        )
        mutated_attempt = json.loads(
            result_bytes[attempt_relative].decode("utf-8")
        )
        mutated_attempt["publication"] = {}
        mutated_attempt["comparison"]["memberDifferences"] = (
            mutated_attempt["comparison"]["memberDifferences"][:-1]
        )
        mutated_result_bytes = dict(result_bytes)
        mutated_result_bytes[attempt_relative] = (
            json.dumps(
                mutated_attempt,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        failures = (
            check_docs_hygiene
            .historical_build16_reproducibility_failures(
                document_text=document_text,
                result_bytes_by_path=mutated_result_bytes,
            )
        )
        self.assertTrue(
            any("publication=null" in failure for failure in failures)
        )
        self.assertTrue(
            any("expected failed member paths" in failure for failure in failures)
        )

    def test_historical_release_documents_preserve_own_identity_and_readback(
        self,
    ) -> None:
        ledger_bytes = check_docs_hygiene.LOCAL_RELEASE_LEDGER.read_bytes()
        entries = check_docs_hygiene.parse_release_version_ledger(
            ledger_bytes
        )
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

    def test_build3_fixture_record_requires_every_own_historical_readback(
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
        exact_command = (
            check_docs_hygiene.LOCAL_RELEASE_FIXTURE_READBACK_COMMAND
        )
        fixture_text = documents[fixture_build]
        self.assertEqual(fixture_text.count(exact_command), 2)
        second_command_index = fixture_text.rfind(exact_command)
        self.assertGreater(second_command_index, fixture_text.find(exact_command))

        def replace_second_command(replacement: str) -> str:
            return (
                fixture_text[:second_command_index]
                + replacement
                + fixture_text[second_command_index + len(exact_command):]
            )

        mutations = {
            "missing": fixture_text.replace(
                target,
                "--archive-dir dist/releases/removed-build3-target",
                1,
            ),
            "duplicate": fixture_text.replace(
                target,
                f"{target}\n{target}",
                1,
            ),
            "bare_second_command": replace_second_command(
                "python3 script/check_release_artifact_archive.py",
            ),
            "second_command_without_historical_mode": replace_second_command(
                exact_command.removesuffix(" \\\n  --historical"),
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
                        (
                            "exact historical Build 3 readback command must "
                            "appear twice"
                        )
                        in failure
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
                "`dist/reproducibility/"
                f"{check_docs_hygiene.LOCAL_RELEASE_ID}-two-root-"
                f"v{check_docs_hygiene.CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}"
                "-prepublication.json`"
            ),
            (
                f"{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE:,} "
                "bytes"
            ),
            (
                f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256}`"
            ),
            "`alreadyMatched=false`",
            "`prepublicationBinding.matched=true`",
            "`previous-ledger-entry-archive-v1`",
            (
                f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256}`"
            ),
            "`-Xswiftc -num-threads -Xswiftc 1`",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-clean-home-install-v1.json`"
            ),
            (
                f"`{check_docs_hygiene.CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256}`"
            ),
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-clean-home-state-recovery-v1.json`"
            ),
            (
                f"`{check_docs_hygiene.CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`"
            ),
            (
                check_docs_hygiene
                .CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_REPEATABILITY_CLAIM
            ),
            f"`{check_docs_hygiene.HISTORICAL_BUILD16_RELEASE_ID}`",
            (
                f"{check_docs_hygiene.HISTORICAL_BUILD16_ARCHIVE_SIZE:,} "
                "bytes"
            ),
            f"`{check_docs_hygiene.HISTORICAL_BUILD16_ARCHIVE_SHA256}`",
            (
                f"{check_docs_hygiene.HISTORICAL_BUILD16_RESULT_SIZE:,} "
                "bytes"
            ),
            f"`{check_docs_hygiene.HISTORICAL_BUILD16_RESULT_SHA256}`",
            (
                f"{check_docs_hygiene.HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE:,} "
                "bytes"
            ),
            f"`{check_docs_hygiene.HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256}`",
            (
                f"`{check_docs_hygiene.HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256}`"
            ),
            "`publication=null`",
            "Build 17 does not retroactively qualify Build 16.",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-14-clean-home-install-v1.json`"
            ),
            (
                f"{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
            (
                f"`{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256}`"
            ),
            "`distinctProcessIdentifiers=true`",
            "`regularFileBytesAndModesUnchangedAcrossRelaunch=true`",
            "`totalEventCount=0`",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-14-clean-home-state-recovery-v1.json`"
            ),
            (
                f"{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
            (
                f"`{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`"
            ),
            "`installedStateBytesAndModesUnchangedAcrossRelaunch=true`",
            "`runtimeIdentityFilePresent=true`",
            (
                "Build 14 installed state-recovery evidence remains bound to "
                "Build 14 and is not reinterpreted as Build 17 evidence."
            ),
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-13-state-recovery-v1.json`"
            ),
            (
                f"{check_docs_hygiene.MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
            (
                f"`{check_docs_hygiene.MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`"
            ),
            "`legacyAbsentBeforeSecondRun=true`",
            "`legacyFixturePreservedUnchanged=true`",
            "`sqliteCanaryUnchangedAcrossRuns=true`",
            (
                "`da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef`"
            ),
            (
                "`558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9`"
            ),
            (
                "`ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07`"
            ),
            (
                "Build 12 state-recovery result was not published, and Build "
                "13 evidence is not reinterpreted as Build 12 evidence."
            ),
            (
                "Build 13 state-recovery evidence remains bound to Build 13 "
                "and is not reinterpreted as Build 17 evidence."
            ),
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-10-lifecycle-v1.json`"
            ),
            (
                f"{check_docs_hygiene.MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
            (
                f"`{check_docs_hygiene.MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256}`"
            ),
            (
                "Build 10 observations remain bound to Build 10 and are not "
                "reinterpreted as Build 17 evidence."
            ),
            "`minimumObservationSeconds=5.0`",
            "`observationDeadlineReached=true`",
            "`identityFilePresentAfterRuns=[false, false]`",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-9-lifecycle-v1.json`"
            ),
            (
                f"{check_docs_hygiene.HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
            (
                f"`{check_docs_hygiene.HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256}`"
            ),
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_SHA256}`",
            (
                f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_OVERLAY_SHA256}`"
            ),
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`",
            f"`{check_docs_hygiene.LOCAL_RELEASE_EXPECTED_MACOS_UUID}`",
            "101- and 109-byte source roots",
            "`sourceRootLengthsDiffer=true`",
            "`independentReadback=true`",
            "`publishedBytesEqualLaneA=true`",
            "`sourceSnapshotUnchanged=true`",
            *check_docs_hygiene.LOCAL_RELEASE_ANDROID_BACKUP_POLICY_REQUIRED_CLAIMS,
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
            identity_pattern = r"\s+".join(
                re.escape(part) for part in identity_snippet.split()
            )
            if re.search(identity_pattern, document_text) is None:
                continue
            with self.subTest(identity=identity_snippet):
                mutated = re.sub(
                    identity_pattern,
                    "INVALID_RELEASE_IDENTITY",
                    document_text,
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
