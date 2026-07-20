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


if __name__ == "__main__":
    unittest.main()
