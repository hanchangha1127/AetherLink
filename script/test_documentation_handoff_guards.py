from __future__ import annotations

import ast
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from script import check_docs_hygiene
from script import run_clean_release_reproducibility
from script.check_copy_hygiene import macos_pairing_callback_wiring_failures


def _static_truth_value(expression: ast.expr) -> bool | None:
    if isinstance(expression, ast.UnaryOp) and isinstance(
        expression.op,
        ast.Not,
    ):
        operand = _static_truth_value(expression.operand)
        return None if operand is None else not operand
    if isinstance(expression, ast.BoolOp):
        values = [_static_truth_value(value) for value in expression.values]
        if isinstance(expression.op, ast.And):
            if False in values:
                return False
            return True if all(value is True for value in values) else None
        if isinstance(expression.op, ast.Or):
            if True in values:
                return True
            return False if all(value is False for value in values) else None
        return None
    if isinstance(expression, ast.Compare):
        try:
            values = [
                ast.literal_eval(node)
                for node in (expression.left, *expression.comparators)
            ]
        except (ValueError, TypeError, SyntaxError):
            return None
        comparisons: list[bool] = []
        for left, operator, right in zip(
            values,
            expression.ops,
            values[1:],
        ):
            try:
                if isinstance(operator, ast.Eq):
                    comparisons.append(left == right)
                elif isinstance(operator, ast.NotEq):
                    comparisons.append(left != right)
                elif isinstance(operator, ast.Is):
                    comparisons.append(left is right)
                elif isinstance(operator, ast.IsNot):
                    comparisons.append(left is not right)
                elif isinstance(operator, ast.Lt):
                    comparisons.append(left < right)
                elif isinstance(operator, ast.LtE):
                    comparisons.append(left <= right)
                elif isinstance(operator, ast.Gt):
                    comparisons.append(left > right)
                elif isinstance(operator, ast.GtE):
                    comparisons.append(left >= right)
                else:
                    return None
            except TypeError:
                return None
        return all(comparisons)
    try:
        return bool(ast.literal_eval(expression))
    except (ValueError, TypeError, SyntaxError):
        return None


def _reachable_main_extend_counts(
    source: str,
    required_calls: tuple[str, ...],
) -> dict[str, int]:
    module = ast.parse(source)
    main_function = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    counts = {name: 0 for name in required_calls}

    def statement_definitely_terminates(statement: ast.stmt) -> bool:
        if isinstance(statement, (ast.Return, ast.Raise)):
            return True
        if isinstance(statement, ast.Try):
            if block_definitely_terminates(statement.finalbody):
                return True
            return (
                block_definitely_terminates(statement.body)
                and all(
                    block_definitely_terminates(handler.body)
                    for handler in statement.handlers
                )
            )
        if (
            isinstance(statement, ast.If)
            and _static_truth_value(statement.test) is True
        ):
            return block_definitely_terminates(statement.body)
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
        ):
            function = statement.value.func
            return (
                isinstance(function, ast.Name)
                and function.id in {"exit", "quit"}
            ) or (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "sys"
                and function.attr == "exit"
            )
        return False

    def block_definitely_terminates(
        statements: list[ast.stmt],
    ) -> bool:
        return any(
            statement_definitely_terminates(statement)
            for statement in statements
        )

    for statement in main_function.body:
        if statement_definitely_terminates(statement):
            break
        if not (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Attribute)
            and statement.value.func.attr == "extend"
            and isinstance(statement.value.func.value, ast.Name)
            and statement.value.func.value.id == "failures"
            and len(statement.value.args) == 1
            and not statement.value.keywords
        ):
            continue
        validator_call = statement.value.args[0]
        if not (
            isinstance(validator_call, ast.Call)
            and isinstance(validator_call.func, ast.Name)
            and not validator_call.args
            and not validator_call.keywords
        ):
            continue
        if validator_call.func.id in counts:
            counts[validator_call.func.id] += 1
    return counts


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
    def test_tracked_document_contract_mode_excludes_ignored_evidence_readback(
        self,
    ) -> None:
        excluded_validators = (
            "current_source_g6_reproducibility_failures",
            "current_source_g6_swift_root_diagnostic_failures",
            "current_source_g6_lifecycle_two_evidence_failures",
            "current_source_g6_lane_a_local_dmg_evidence_failures",
            (
                "current_build24_macos_current_unsealed_install_"
                "recovery_source_failures"
            ),
            "current_build24_reverse_version_readback_source_failures",
            "current_build24_macos_idle_resource_stability_evidence_failures",
        )
        patches = [
            patch.object(
                check_docs_hygiene,
                name,
                side_effect=AssertionError(
                    f"tracked mode invoked ignored evidence validator {name}"
                ),
            )
            for name in excluded_validators
        ]
        for validator_patch in patches:
            validator_patch.start()
        try:
            self.assertEqual(
                check_docs_hygiene.tracked_document_contract_failures(),
                [],
            )
        finally:
            for validator_patch in reversed(patches):
                validator_patch.stop()

    def test_tracked_document_contract_cli_is_explicit_and_bounded(self) -> None:
        with (
            patch.object(
                check_docs_hygiene,
                "tracked_document_contract_failures",
                return_value=[],
            ) as tracked,
            patch.object(
                check_docs_hygiene,
                "current_source_g6_reproducibility_failures",
                side_effect=AssertionError("full evidence mode was reached"),
            ),
            patch("builtins.print") as print_mock,
        ):
            self.assertEqual(
                check_docs_hygiene.main(
                    [check_docs_hygiene.TRACKED_CONTRACTS_ONLY_ARGUMENT]
                ),
                0,
            )
        tracked.assert_called_once_with()
        self.assertTrue(
            any(
                "ignored dist evidence bytes were not read" in str(call)
                for call in print_mock.call_args_list
            )
        )

        with patch("builtins.print") as print_mock:
            self.assertEqual(check_docs_hygiene.main(["--unknown"]), 2)
        self.assertTrue(
            any(
                "usage: check_docs_hygiene.py" in str(call)
                for call in print_mock.call_args_list
            )
        )

    def test_current_g7_nonsecurity_merge_full_local_candidate_block_is_exact_and_fail_closed(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_g7_nonsecurity_merge_full_local_candidate_document_failures
        )
        self.assertEqual([], validator())
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_G7_NONSECURITY_MERGE_FULL_LOCAL_CANDIDATE_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_G7_NONSECURITY_MERGE_FULL_LOCAL_CANDIDATE_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_G7_NONSECURITY_MERGE_FULL_LOCAL_CANDIDATE_DOCUMENT_BODY
        )
        complete_block = start_marker + "\n" + expected_body + "\n" + end_marker
        self.assertEqual(
            (
                check_docs_hygiene
                .CURRENT_G7_NONSECURITY_MERGE_FULL_LOCAL_CANDIDATE_DOCUMENT_BODY_SHA256
            ),
            hashlib.sha256((expected_body + "\n").encode("utf-8")).hexdigest(),
        )

        for relative in targets:
            with self.subTest(relative=relative):
                text = (check_docs_hygiene.ROOT / relative).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(1, text.count(complete_block))
                mutations = (
                    text.replace(
                        complete_block,
                        complete_block.replace(
                            "67 exact ordered commands",
                            "66 exact ordered commands",
                            1,
                        ),
                        1,
                    ),
                    text.replace(start_marker, "", 1),
                    text.replace(end_marker, "", 1),
                    text.replace(
                        complete_block,
                        end_marker + "\n" + start_marker,
                        1,
                    ),
                    text.rstrip() + "\n\n" + complete_block + "\n",
                    text.replace(complete_block + "\n\n", "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n",
                    text.replace(
                        complete_block,
                        "<details hidden>\n" + complete_block + "\n</details>",
                        1,
                    ),
                )
                for mutation in mutations:
                    failures = validator(
                        document_text_by_relative={relative: mutation}
                    )
                    self.assertTrue(
                        any(relative in failure for failure in failures),
                        failures,
                    )
                self.assertTrue(any(
                    relative in failure and "visible Markdown" in failure
                    for failure in validator(
                        document_text_by_relative={relative: mutations[-1]}
                    )
                ))

    def test_current_g7_nonsecurity_merge_full_local_candidate_validator_is_wired_once(
        self,
    ) -> None:
        validator_name = (
            "current_g7_nonsecurity_merge_full_local_candidate_document_failures"
        )
        source = Path(check_docs_hygiene.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            {validator_name: 1},
            _reachable_main_extend_counts(source, (validator_name,)),
        )
        module = ast.parse(source)
        tracked = next(
            node
            for node in module.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "tracked_document_contract_failures"
            )
        )
        self.assertEqual(
            1,
            sum(
                1
                for node in ast.walk(tracked)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == validator_name
                )
            ),
        )

    def test_current_g6_release_diagnostics_document_block_is_exact_and_fail_closed(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene.current_g6_release_diagnostics_document_failures
        )
        self.assertEqual([], validator())
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene.CURRENT_G6_RELEASE_DIAGNOSTICS_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene.CURRENT_G6_RELEASE_DIAGNOSTICS_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene.CURRENT_G6_RELEASE_DIAGNOSTICS_DOCUMENT_BODY
        )
        complete_block = start_marker + "\n" + expected_body + "\n" + end_marker
        self.assertEqual(
            check_docs_hygiene.CURRENT_G6_RELEASE_DIAGNOSTICS_DOCUMENT_BODY_SHA256,
            hashlib.sha256((expected_body + "\n").encode("utf-8")).hexdigest(),
        )

        for relative in targets:
            with self.subTest(relative=relative):
                text = (check_docs_hygiene.ROOT / relative).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(1, text.count(complete_block))
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(expected_body, text[start:end].strip("\n"))
                mutations = (
                    text.replace(
                        complete_block,
                        complete_block.replace("24/24", "23/24", 1),
                        1,
                    ),
                    text.replace(start_marker, "", 1),
                    text.replace(end_marker, "", 1),
                    text.rstrip() + "\n\n" + complete_block + "\n",
                    (
                        text.replace(complete_block, "", 1).rstrip()
                        + "\n\n"
                        + complete_block
                        + "\n"
                    ),
                    text.replace(
                        complete_block,
                        "<details hidden>\n" + complete_block + "\n</details>",
                        1,
                    ),
                )
                for mutation in mutations:
                    failures = validator(
                        document_text_by_relative={relative: mutation}
                    )
                    self.assertTrue(
                        any(relative in failure for failure in failures),
                        failures,
                    )

                hidden_failures = validator(
                    document_text_by_relative={relative: mutations[-1]}
                )
                self.assertTrue(
                    any(
                        relative in failure and "visible Markdown" in failure
                        for failure in hidden_failures
                    )
                )

    def test_current_g6_release_diagnostics_validator_is_wired_once(self) -> None:
        validator_name = "current_g6_release_diagnostics_document_failures"
        source = Path(check_docs_hygiene.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            {validator_name: 1},
            _reachable_main_extend_counts(source, (validator_name,)),
        )
        module = ast.parse(source)
        tracked = next(
            node
            for node in module.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "tracked_document_contract_failures"
            )
        )
        tracked_calls = sum(
            1
            for node in ast.walk(tracked)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == validator_name
            )
        )
        self.assertEqual(1, tracked_calls)

    def test_current_g7_document_ingestion_asan_block_is_exact_and_fail_closed(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene.
            current_g7_document_ingestion_asan_document_failures
        )
        self.assertEqual([], validator())
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_ASAN_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_ASAN_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_ASAN_DOCUMENT_BODY
        )
        complete_block = start_marker + "\n" + expected_body + "\n" + end_marker
        self.assertEqual(
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_ASAN_DOCUMENT_BODY_SHA256,
            hashlib.sha256((expected_body + "\n").encode("utf-8")).hexdigest(),
        )

        for relative in targets:
            with self.subTest(relative=relative):
                text = (check_docs_hygiene.ROOT / relative).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(1, text.count(complete_block))
                mutations = (
                    text.replace(
                        complete_block,
                        complete_block.replace("57/57", "56/57", 1),
                        1,
                    ),
                    text.replace(start_marker, "", 1),
                    text.replace(end_marker, "", 1),
                    text.replace(
                        complete_block,
                        end_marker + "\n" + start_marker,
                        1,
                    ),
                    text.rstrip() + "\n\n" + complete_block + "\n",
                    text.replace(complete_block + "\n\n", "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n",
                    text.replace(
                        complete_block,
                        "<details hidden>\n" + complete_block + "\n</details>",
                        1,
                    ),
                )
                for mutation in mutations:
                    failures = validator(
                        document_text_by_relative={relative: mutation}
                    )
                    self.assertTrue(
                        any(relative in failure for failure in failures),
                        failures,
                    )
                self.assertTrue(any(
                    relative in failure and "visible Markdown" in failure
                    for failure in validator(
                        document_text_by_relative={relative: mutations[-1]}
                    )
                ))

    def test_current_g7_document_ingestion_asan_validator_is_wired_once(
        self,
    ) -> None:
        validator_name = "current_g7_document_ingestion_asan_document_failures"
        source = Path(check_docs_hygiene.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            {validator_name: 1},
            _reachable_main_extend_counts(source, (validator_name,)),
        )
        module = ast.parse(source)
        tracked = next(
            node
            for node in module.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "tracked_document_contract_failures"
            )
        )
        self.assertEqual(
            1,
            sum(
                1
                for node in ast.walk(tracked)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == validator_name
                )
            ),
        )

    def test_current_g7_document_ingestion_mutation_block_is_exact_and_fail_closed(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene.
            current_g7_document_ingestion_mutation_document_failures
        )
        self.assertEqual([], validator())
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_MUTATION_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_MUTATION_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_MUTATION_DOCUMENT_BODY
        )
        complete_block = start_marker + "\n" + expected_body + "\n" + end_marker
        self.assertEqual(
            check_docs_hygiene.
            CURRENT_G7_DOCUMENT_INGESTION_MUTATION_DOCUMENT_BODY_SHA256,
            hashlib.sha256((expected_body + "\n").encode("utf-8")).hexdigest(),
        )
        self.assertIn(
            "values are run-scoped",
            expected_body,
        )
        self.assertNotRegex(
            expected_body,
            r"console has\s+SHA-256",
        )

        for relative in targets:
            with self.subTest(relative=relative):
                text = (check_docs_hygiene.ROOT / relative).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(1, text.count(complete_block))
                mutations = (
                    text.replace(
                        complete_block,
                        complete_block.replace("96/96", "95/96", 1),
                        1,
                    ),
                    text.replace(start_marker, "", 1),
                    text.replace(end_marker, "", 1),
                    text.replace(
                        complete_block,
                        end_marker + "\n" + start_marker,
                        1,
                    ),
                    text.rstrip() + "\n\n" + complete_block + "\n",
                    text.replace(complete_block + "\n\n", "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n",
                    text.replace(
                        complete_block,
                        "<details hidden>\n" + complete_block + "\n</details>",
                        1,
                    ),
                )
                for mutation in mutations:
                    failures = validator(
                        document_text_by_relative={relative: mutation}
                    )
                    self.assertTrue(
                        any(relative in failure for failure in failures),
                        failures,
                    )
                self.assertTrue(any(
                    relative in failure and "visible Markdown" in failure
                    for failure in validator(
                        document_text_by_relative={relative: mutations[-1]}
                    )
                ))

    def test_current_g7_document_ingestion_mutation_validator_is_wired_once(
        self,
    ) -> None:
        validator_name = (
            "current_g7_document_ingestion_mutation_document_failures"
        )
        source = Path(check_docs_hygiene.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            {validator_name: 1},
            _reachable_main_extend_counts(source, (validator_name,)),
        )
        module = ast.parse(source)
        tracked = next(
            node
            for node in module.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "tracked_document_contract_failures"
            )
        )
        self.assertEqual(
            1,
            sum(
                1
                for node in ast.walk(tracked)
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == validator_name
                )
            ),
        )

    def test_current_g7_android_nightly_document_block_is_exact_and_fail_closed(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_g7_android_headless_nightly_document_failures
        )
        self.assertEqual([], validator())
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_G7_ANDROID_HEADLESS_NIGHTLY_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_G7_ANDROID_HEADLESS_NIGHTLY_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_G7_ANDROID_HEADLESS_NIGHTLY_DOCUMENT_BODY
        )
        complete_block = (
            start_marker + "\n" + expected_body + "\n" + end_marker
        )
        self.assertEqual(
            check_docs_hygiene
            .CURRENT_G7_ANDROID_HEADLESS_NIGHTLY_DOCUMENT_BODY_SHA256,
            hashlib.sha256((expected_body + "\n").encode("utf-8")).hexdigest(),
        )

        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                self.assertEqual(1, text.count(complete_block))
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(expected_body, text[start:end].strip("\n"))

                reversed_markers = (
                    text.replace(start_marker, "__G7_START__", 1)
                    .replace(end_marker, start_marker, 1)
                    .replace("__G7_START__", end_marker, 1)
                )
                empty_body = text[:start] + "\n" + text[end:]
                mutations = (
                    text.replace("97/97 tests", "96/96 tests", 1),
                    text.replace(start_marker, "", 1),
                    text.replace(end_marker, "", 1),
                    text.rstrip() + "\n\n" + complete_block + "\n",
                    reversed_markers,
                    empty_body,
                    (
                        text.replace(complete_block, "", 1).rstrip()
                        + "\n\n"
                        + complete_block
                        + "\n"
                    ),
                    text.replace(
                        complete_block,
                        "<details hidden>\n"
                        + complete_block
                        + "\n</details>",
                        1,
                    ),
                )
                for mutation in mutations:
                    failures = validator(
                        document_text_by_relative={relative: mutation}
                    )
                    self.assertTrue(
                        any(relative in failure for failure in failures),
                        failures,
                    )

                hidden = mutations[-1]
                hidden_failures = validator(
                    document_text_by_relative={relative: hidden}
                )
                self.assertTrue(
                    any(
                        relative in failure and "visible Markdown" in failure
                        for failure in hidden_failures
                    )
                )

    def test_current_g7_android_nightly_validator_is_wired_once(self) -> None:
        validator_name = "current_g7_android_headless_nightly_document_failures"
        source = Path(check_docs_hygiene.__file__).read_text(encoding="utf-8")
        self.assertEqual(
            {validator_name: 1},
            _reachable_main_extend_counts(source, (validator_name,)),
        )
        module = ast.parse(source)
        tracked = next(
            node
            for node in module.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "tracked_document_contract_failures"
            )
        )
        tracked_calls = sum(
            1
            for node in ast.walk(tracked)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == validator_name
            )
        )
        self.assertEqual(1, tracked_calls)

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

    def g6_swift_root_diagnostic_payloads(self) -> dict[str, bytes]:
        return {
            contract.label: contract.path.read_bytes()
            for contract in (
                check_docs_hygiene
                .CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS
            )
        }

    def g6_lifecycle_two_payloads(self) -> dict[str, bytes]:
        payloads = {
            contract.role: contract.path.read_bytes()
            for contract in (
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS
            )
        }
        payloads["parent"] = (
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT
            .read_bytes()
        )
        return payloads

    @staticmethod
    def canonical_json_bytes(value: object) -> bytes:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")

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

        previous_build_number = check_docs_hygiene.parse_release_version_ledger(
            check_docs_hygiene.LOCAL_RELEASE_LEDGER.read_bytes()
        )[-2].build_number
        previous_build_command = (
            "--archive-dir "
            "dist/releases/aetherlink-1.0.0+"
            f"{previous_build_number}-local-v1 --historical"
        )
        without_previous_historical = dict(documents)
        without_previous_historical[progress_path] = documents[
            progress_path
        ].replace(
            previous_build_command,
            previous_build_command.removesuffix(" --historical"),
            1,
        )
        self.assertTrue(
            any(
                f"historical Build {previous_build_number}" in failure
                for failure in (
                    check_docs_hygiene
                    .release_readback_command_mode_failures(
                        without_previous_historical
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
                (
                    f"current Build "
                    f"{check_docs_hygiene.LOCAL_RELEASE_BUILD_NUMBER}"
                )
                in failure
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
                rf"refresh,\s+`main`\s+and\s+`origin/main` both resolved to\s+)"
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
                "Build 24 is the latest immutable ledger archive.",
                "Build 23 is the latest immutable ledger archive.",
            ),
            "docs/progress.md": (
                "Local V1 Build 24 Qualification",
                "Local V1 Build 23 Qualification",
            ),
            "docs/qa-evidence.md": (
                "The Build 24 archive is the latest ledger entry",
                "The Build 23 archive is the latest ledger entry",
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

        handoff_relative = "docs/handoff.md"
        handoff_text = (
            check_docs_hygiene.ROOT / handoff_relative
        ).read_text(encoding="utf-8")
        summary_boundary = (
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
        )
        missing_boundary = handoff_text.replace(summary_boundary, "", 1)
        self.assertTrue(
            any(
                handoff_relative in failure
                and "lifecycle boundary marker" in failure
                for failure in validator(
                    document_text_by_relative={
                        handoff_relative: missing_boundary,
                    }
                )
            )
        )

        current_handoff_claim = (
            "Build 24 is the latest immutable ledger archive."
        )
        moved_claim = handoff_text.replace(current_handoff_claim, "", 1)
        moved_claim = moved_claim.replace(
            summary_boundary,
            summary_boundary + "\n" + current_handoff_claim,
            1,
        )
        self.assertTrue(
            any(
                handoff_relative in failure
                and "ledger-derived current release summary claim" in failure
                for failure in validator(
                    document_text_by_relative={handoff_relative: moved_claim}
                )
            )
        )

        competing_stale_claims = {
            "docs/handoff.md": (
                "Build 23 is the latest immutable ledger archive."
            ),
            "docs/progress.md": (
                "Build 23 is the current local qualification record."
            ),
            "docs/qa-evidence.md": (
                "The Build 23 archive is the latest ledger entry."
            ),
            "docs/roadmap.md": (
                "Build 23 is the latest immutable local G6 package "
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
                "Build 23 remains the latest local qualification record."
            ),
            "docs/qa-evidence.md": (
                "Build 23 continues as the current ledger qualification."
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

    def test_current_source_g6_reproducibility_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            check_docs_hygiene.current_source_g6_reproducibility_failures(),
            [],
        )

    def test_current_source_g6_swift_root_diagnostics_match_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .current_source_g6_swift_root_diagnostic_failures()
            ),
            [],
        )
        payloads = self.g6_swift_root_diagnostic_payloads()
        self.assertEqual(
            payloads["distinct-unequal-utf8-length"],
            payloads["distinct-unequal-utf8-length-repeat-two"],
        )

    def test_current_source_g6_swift_root_diagnostics_reject_identity_shape_and_noncanonical_json(
        self,
    ) -> None:
        payloads = self.g6_swift_root_diagnostic_payloads()
        missing = dict(payloads)
        del missing["same-physical-root"]
        failures = (
            check_docs_hygiene
            .current_source_g6_swift_root_diagnostic_failures(missing)
        )
        self.assertTrue(
            any("payload labels must be exactly" in failure for failure in failures)
        )

        pretty = dict(payloads)
        pretty_result = json.loads(pretty["same-physical-root"])
        pretty["same-physical-root"] = (
            json.dumps(pretty_result, indent=2) + "\n"
        ).encode("ascii")
        failures = (
            check_docs_hygiene
            .current_source_g6_swift_root_diagnostic_failures(pretty)
        )
        self.assertTrue(
            any("expected identity" in failure for failure in failures)
        )
        self.assertTrue(
            any(
                "canonical sorted compact ASCII JSON" in failure
                for failure in failures
            )
        )

        contracts = list(
            check_docs_hygiene.CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS
        )
        contracts[-1] = replace(contracts[-1], path=contracts[-2].path)
        with patch.object(
            check_docs_hygiene,
            "CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS",
            tuple(contracts),
        ):
            failures = (
                check_docs_hygiene
                .current_source_g6_swift_root_diagnostic_failures()
            )
        self.assertTrue(
            any("paths must be four distinct files" in failure for failure in failures)
        )
        self.assertTrue(
            any("must use canonical path" in failure for failure in failures)
        )

    def test_current_source_g6_swift_root_diagnostics_reject_root_geometry_and_promotion(
        self,
    ) -> None:
        payloads = self.g6_swift_root_diagnostic_payloads()
        promoted = dict(payloads)
        promoted_result = json.loads(promoted["distinct-unequal-utf8-length"])
        promoted_result["scratch"]["sourceRoots"]["policy"] = (
            "distinct-unequal-utf8-byte-length-v1"
        )
        promoted["distinct-unequal-utf8-length"] = self.canonical_json_bytes(
            promoted_result
        )
        failures = (
            check_docs_hygiene
            .current_source_g6_swift_root_diagnostic_failures(promoted)
        )
        self.assertTrue(
            any("scratch.sourceRoots.policy" in failure for failure in failures)
        )

        invalid_length = dict(payloads)
        invalid_result = json.loads(invalid_length["same-physical-root"])
        invalid_result["scratch"]["sourceRoots"]["sourceRootByteLengths"][
            "build-a"
        ] = False
        invalid_length["same-physical-root"] = self.canonical_json_bytes(
            invalid_result
        )
        failures = (
            check_docs_hygiene
            .current_source_g6_swift_root_diagnostic_failures(invalid_length)
        )
        self.assertTrue(
            any(
                "scratch.sourceRoots.sourceRootByteLengths" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_swift_root_diagnostics_reject_cross_mode_and_repeat_two_drift(
        self,
    ) -> None:
        payloads = self.g6_swift_root_diagnostic_payloads()
        archive_drift = dict(payloads)
        drift_result = json.loads(
            archive_drift["distinct-equal-utf8-length"]
        )
        for build in drift_result["builds"]:
            build["archive"]["sha256"] = "0" * 64
        archive_drift["distinct-equal-utf8-length"] = (
            self.canonical_json_bytes(drift_result)
        )
        failures = (
            check_docs_hygiene
            .current_source_g6_swift_root_diagnostic_failures(archive_drift)
        )
        self.assertTrue(
            any(
                "archives must match exactly across all eight builds"
                in failure
                for failure in failures
            )
        )

        repeat_drift = dict(payloads)
        repeat_result = json.loads(
            repeat_drift["distinct-unequal-utf8-length-repeat-two"]
        )
        repeat_result["gradleCache"]["fileCount"] += 1
        repeat_drift["distinct-unequal-utf8-length-repeat-two"] = (
            self.canonical_json_bytes(repeat_result)
        )
        failures = (
            check_docs_hygiene
            .current_source_g6_swift_root_diagnostic_failures(repeat_drift)
        )
        self.assertTrue(
            any("repeat-two result bytes" in failure for failure in failures)
        )

    def test_current_source_g6_reproducibility_rejects_semantic_drift(
        self,
    ) -> None:
        def canonical_bytes(result: dict[str, object]) -> bytes:
            return (
                json.dumps(
                    result,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")

        source_result = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
            .read_text(encoding="ascii")
        )
        source_result["publication"]["attempted"] = True
        failures = (
            check_docs_hygiene.current_source_g6_reproducibility_failures(
                canonical_bytes(source_result)
            )
        )
        self.assertTrue(
            any("publication.attempted" in failure for failure in failures)
        )

        source_result = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
            .read_text(encoding="ascii")
        )
        source_result["builds"][1]["archive"]["sha256"] = "0" * 64
        failures = (
            check_docs_hygiene.current_source_g6_reproducibility_failures(
                canonical_bytes(source_result)
            )
        )
        self.assertTrue(
            any(
                "builds[1].archive.sha256" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any(
                "archive inventories must match exactly" in failure
                for failure in failures
            )
        )

        source_result = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
            .read_text(encoding="ascii")
        )
        source_result["builds"][0]["commandExitCode"] = False
        failures = (
            check_docs_hygiene.current_source_g6_reproducibility_failures(
                canonical_bytes(source_result)
            )
        )
        self.assertTrue(
            any(
                "builds[0].commandExitCode" in failure
                for failure in failures
            )
        )

        source_result = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
            .read_text(encoding="ascii")
        )
        for build in source_result["builds"]:
            build["archive"]["members"][0] = []
            build["archive"]["members"][1]["path"] = "manifest.json"
        failures = (
            check_docs_hygiene.current_source_g6_reproducibility_failures(
                canonical_bytes(source_result)
            )
        )
        self.assertTrue(
            any(
                "members must start with manifest.json" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_swift_root_diagnostics_retain_recorded_source(
        self,
    ) -> None:
        with patch.object(
            check_docs_hygiene.package_release_artifacts,
            "source_snapshot",
            side_effect=AssertionError("live source must not be read"),
        ):
            failures = (
                check_docs_hygiene
                .current_source_g6_swift_root_diagnostic_failures()
            )
        self.assertEqual(failures, [])

    def test_current_source_g6_reproducibility_rejects_noncanonical_json(
        self,
    ) -> None:
        result = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
            .read_text(encoding="ascii")
        )
        pretty = (json.dumps(result, indent=2) + "\n").encode("ascii")
        failures = (
            check_docs_hygiene.current_source_g6_reproducibility_failures(
                pretty
            )
        )
        self.assertTrue(
            any(
                "canonical sorted compact ASCII JSON" in failure
                for failure in failures
            )
        )

        failures = (
            check_docs_hygiene.current_source_g6_reproducibility_failures(
                b'{"schemaVersion":4,"schemaVersion":4}\n'
            )
        )
        self.assertTrue(
            any("duplicate JSON key" in failure for failure in failures)
        )

    def test_current_source_g6_lifecycle_two_matches_runner_contract(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_source_g6_lifecycle_two_evidence_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(validator(self.g6_lifecycle_two_payloads()), [])

        stable_reader = (
            check_docs_hygiene._stable_current_source_g6_evidence_bytes
        )
        read_labels: list[str] = []

        def record_read(*, path: Path, label: str):
            read_labels.append(label)
            return stable_reader(path=path, label=label)

        with patch.object(
            check_docs_hygiene,
            "_stable_current_source_g6_evidence_bytes",
            side_effect=record_read,
        ):
            self.assertEqual(validator(), [])
        self.assertEqual(
            read_labels,
            [
                "G6 lifecycle-two install",
                "G6 lifecycle-two uninstall_reinstall",
                "G6 lifecycle-two state_recovery",
                "G6 lifecycle-two abrupt_process",
                "G6 lifecycle-two abrupt_receipt",
                "G6 lifecycle-two idle",
                "G6 lifecycle-two parent",
                "G6 lifecycle-two parent commit-marker reread",
            ],
        )

    def test_current_source_g6_lifecycle_two_rejects_parent_and_child_drift(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_source_g6_lifecycle_two_evidence_failures
        )
        payloads = self.g6_lifecycle_two_payloads()

        incomplete = dict(payloads)
        del incomplete["idle"]
        failures = validator(incomplete)
        self.assertTrue(
            any("supplied roles must be exactly" in failure for failure in failures)
        )

        boolean_parent = dict(payloads)
        parent = json.loads(boolean_parent["parent"])
        for build in parent["builds"]:
            build["archive"]["size"] = True
        boolean_parent["parent"] = self.canonical_json_bytes(parent)
        failures = validator(boolean_parent)
        self.assertTrue(
            any(
                "builds[0].archive.size" in failure
                for failure in failures
            )
        )

        child_drift = dict(payloads)
        uninstall = json.loads(child_drift["uninstall_reinstall"])
        uninstall["release"]["archiveSha256"] = "0" * 64
        child_drift["uninstall_reinstall"] = self.canonical_json_bytes(
            uninstall
        )
        failures = validator(child_drift)
        self.assertTrue(
            any(
                "semantic/cross-binding validation failed" in failure
                for failure in failures
            )
        )

        pretty_child = dict(payloads)
        install = json.loads(pretty_child["install"])
        pretty_child["install"] = (
            json.dumps(install, ensure_ascii=True, indent=2) + "\n"
        ).encode("ascii")
        failures = validator(pretty_child)
        self.assertTrue(any("expected lifecycle-two" in failure for failure in failures))
        self.assertTrue(
            any(
                "semantic/cross-binding validation failed" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_lifecycle_two_rejects_path_alias_missing_and_symlink(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_source_g6_lifecycle_two_evidence_failures
        )
        contracts = list(
            check_docs_hygiene.CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS
        )
        source_contract = contracts[0]
        contracts[-1] = replace(contracts[-1], path=source_contract.path)
        with patch.object(
            check_docs_hygiene,
            "CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS",
            tuple(contracts),
        ):
            failures = validator()
        self.assertTrue(
            any("paths must be seven distinct files" in failure for failure in failures)
        )
        self.assertTrue(
            any("must use canonical path" in failure for failure in failures)
        )

        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT / "dist/lifecycle"
        ) as temporary:
            temporary_root = Path(temporary)
            missing = temporary_root / "missing.json"
            contracts = list(
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS
            )
            contracts[0] = replace(source_contract, path=missing)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS",
                tuple(contracts),
            ):
                failures = validator()
            self.assertTrue(
                any("missing current-source" in failure for failure in failures)
            )

            symlink = temporary_root / "symlink.json"
            symlink.symlink_to(source_contract.path)
            contracts[0] = replace(source_contract, path=symlink)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_LIFECYCLE_TWO_CHILD_RESULTS",
                tuple(contracts),
            ):
                failures = validator()
            self.assertTrue(
                any("must not be a symlink" in failure for failure in failures)
            )

        actual_parent = (
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT
        )
        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT / "dist/reproducibility"
        ) as temporary:
            temporary_root = Path(temporary)
            missing_parent = temporary_root / "missing-parent.json"
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT",
                missing_parent,
            ):
                failures = validator()
            self.assertTrue(
                any("missing current-source" in failure for failure in failures)
            )

            symlink_parent = temporary_root / "symlink-parent.json"
            symlink_parent.symlink_to(actual_parent)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_LIFECYCLE_TWO_REPRODUCIBILITY_RESULT",
                symlink_parent,
            ):
                failures = validator()
            self.assertTrue(
                any("must not be a symlink" in failure for failure in failures)
            )

        stable_reader = (
            check_docs_hygiene._stable_current_source_g6_evidence_bytes
        )

        def parent_reread_drift(*, path: Path, label: str):
            payload, failures = stable_reader(path=path, label=label)
            if (
                payload is not None
                and label == "G6 lifecycle-two parent commit-marker reread"
            ):
                return payload + b" ", failures
            return payload, failures

        with patch.object(
            check_docs_hygiene,
            "_stable_current_source_g6_evidence_bytes",
            side_effect=parent_reread_drift,
        ):
            failures = validator()
        self.assertTrue(
            any("parent commit marker changed" in failure for failure in failures)
        )

    def test_current_source_g6_lifecycle_two_uses_recorded_source_and_avoids_physical_helpers(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_source_g6_lifecycle_two_evidence_failures
        )
        with patch.object(
            check_docs_hygiene.package_release_artifacts,
            "source_snapshot",
            side_effect=AssertionError("live source must not be read"),
        ):
            failures = validator(self.g6_lifecycle_two_payloads())
        self.assertEqual(failures, [])

        runner = check_docs_hygiene.clean_release_reproducibility
        with (
            patch.object(
                runner,
                "lane_archive_identities",
                side_effect=AssertionError("physical archive access"),
            ),
            patch.object(
                runner,
                "publish_lane_a_local_dmg_suite",
                side_effect=AssertionError("publication access"),
            ),
            patch.object(
                runner,
                "validate_lane_a_local_dmg_suite_parent_result_path",
                side_effect=AssertionError("result-path mutation access"),
            ),
        ):
            self.assertEqual(
                validator(self.g6_lifecycle_two_payloads()),
                [],
            )

    def test_current_source_g6_lifecycle_two_is_full_mode_only(
        self,
    ) -> None:
        module = ast.parse(
            (check_docs_hygiene.ROOT / "script/check_docs_hygiene.py")
            .read_text(encoding="utf-8")
        )
        functions = {
            node.name: node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
        }

        def call_count(function_name: str) -> int:
            return sum(
                1
                for node in ast.walk(functions[function_name])
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id
                    == "current_source_g6_lifecycle_two_evidence_failures"
                )
            )

        self.assertEqual(call_count("main"), 1)
        self.assertEqual(call_count("tracked_document_contract_failures"), 0)
        lifecycle_path_assignments = [
            statement
            for statement in module.body
            if (
                isinstance(statement, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "CURRENT_SOURCE_G6_LIFECYCLE_TWO_PATHS"
                    for target in statement.targets
                )
            )
        ]
        self.assertEqual(len(lifecycle_path_assignments), 1)
        lifecycle_path_assignment = lifecycle_path_assignments[0]
        lifecycle_path_calls = [
            node
            for node in ast.walk(lifecycle_path_assignment.value)
            if isinstance(node, ast.Call)
        ]
        self.assertEqual(len(lifecycle_path_calls), 1)
        self.assertIs(lifecycle_path_calls[0], lifecycle_path_assignment.value)
        constructor = lifecycle_path_calls[0].func
        self.assertIsInstance(constructor, ast.Attribute)
        self.assertEqual(constructor.attr, "LaneALocalDMGSuitePaths")
        self.assertIsInstance(constructor.value, ast.Name)
        self.assertEqual(
            constructor.value.id,
            "clean_release_reproducibility",
        )

    def test_current_source_g6_lane_a_local_dmg_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .current_source_g6_lane_a_local_dmg_evidence_failures()
            ),
            [],
        )

        self.assertEqual(
            (
                check_docs_hygiene
                .current_source_g6_lane_a_local_dmg_evidence_failures(
                    result_bytes=(
                        check_docs_hygiene
                        .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT
                        .read_bytes()
                    ),
                    primary_result_bytes=(
                        check_docs_hygiene
                        .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
                        .read_bytes()
                    ),
                    uninstall_reinstall_result_bytes=(
                        check_docs_hygiene
                        .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT
                        .read_bytes()
                    ),
                    state_recovery_result_bytes=(
                        check_docs_hygiene
                        .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT
                        .read_bytes()
                    ),
                    abrupt_process_result_bytes=(
                        check_docs_hygiene
                        .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT
                        .read_bytes()
                    ),
                    abrupt_process_receipt_bytes=(
                        check_docs_hygiene
                        .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT
                        .read_bytes()
                    ),
                    idle_resource_result_bytes=(
                        check_docs_hygiene
                        .CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT
                        .read_bytes()
                    ),
                )
            ),
            [],
        )

    def test_current_source_g6_lane_a_idle_resource_matches_closed_contract(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .current_source_g6_lane_a_idle_resource_evidence_failures()
            ),
            [],
        )

    def test_current_source_g6_lane_a_idle_resource_rejects_drift(
        self,
    ) -> None:
        def canonical_bytes(result: dict[str, object]) -> bytes:
            return (
                json.dumps(
                    result,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")

        path = (
            check_docs_hygiene.CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT
        )

        result = json.loads(path.read_text(encoding="ascii"))
        result["unexpected"] = True
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_idle_resource_evidence_failures(
                canonical_bytes(result)
            )
        )
        self.assertTrue(
            any("root keys must be exactly" in failure for failure in failures)
        )

        result = json.loads(path.read_text(encoding="ascii"))
        pretty = (json.dumps(result, indent=2) + "\n").encode("ascii")
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_idle_resource_evidence_failures(pretty)
        )
        self.assertTrue(
            any("canonical sorted compact ASCII JSON" in failure for failure in failures)
        )

        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_idle_resource_evidence_failures(
                b'{"schemaVersion":1,"schemaVersion":1}\n'
            )
        )
        self.assertTrue(
            any("duplicate JSON key" in failure for failure in failures)
        )

        result = json.loads(path.read_text(encoding="ascii"))
        result["measurement"]["run"]["samples"][0]["ordinal"] = True
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_idle_resource_evidence_failures(
                canonical_bytes(result)
            )
        )
        self.assertTrue(
            any("sample 1 schedule is invalid" in failure for failure in failures)
        )

        result = json.loads(path.read_text(encoding="ascii"))
        result["measurement"]["run"]["summary"][
            "openFileDescriptors"
        ]["finalDelta"] = 1
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_idle_resource_evidence_failures(
                canonical_bytes(result)
            )
        )
        self.assertTrue(
            any("independently recomputed sample summary" in failure for failure in failures)
        )

    def test_current_source_g6_lane_a_idle_resource_rejects_crossbinding_drift(
        self,
    ) -> None:
        def canonical_bytes(result: dict[str, object]) -> bytes:
            return (
                json.dumps(
                    result,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")

        path = (
            check_docs_hygiene.CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT
        )
        relative = str(path.relative_to(check_docs_hygiene.ROOT))

        result = json.loads(path.read_text(encoding="ascii"))
        result["release"]["archiveSha256"] = "0" * 64
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                idle_resource_result_bytes=canonical_bytes(result)
            )
        )
        self.assertTrue(
            any(
                relative in failure
                and "idle-resource release identity must cross-bind" in failure
                for failure in failures
            )
        )

        result = json.loads(path.read_text(encoding="ascii"))
        result["archiveReadback"]["snapshotFiles"][
            f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip"
        ]["size"] = True
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                idle_resource_result_bytes=canonical_bytes(result)
            )
        )
        self.assertTrue(
            any(
                relative in failure
                and "idle-resource snapshot identities must cross-bind" in failure
                for failure in failures
            )
        )

        result = json.loads(path.read_text(encoding="ascii"))
        result["artifact"]["appTree"]["sha256"] = "0" * 64
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                idle_resource_result_bytes=canonical_bytes(result)
            )
        )
        self.assertTrue(
            any(
                relative in failure
                and "idle-resource app tree must cross-bind" in failure
                for failure in failures
            )
        )

        result = json.loads(path.read_text(encoding="ascii"))
        result["sourceSnapshot"]["sha256"] = "0" * 64
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                idle_resource_result_bytes=canonical_bytes(result)
            )
        )
        self.assertTrue(
            any(
                relative in failure
                and "idle-resource source snapshot must cross-bind" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_lane_a_local_dmg_rejects_drift(
        self,
    ) -> None:
        def canonical_bytes(result: dict[str, object]) -> bytes:
            return (
                json.dumps(
                    result,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")

        source_result = json.loads(
            (
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT
                .read_text(encoding="ascii")
            )
        )
        source_result["release"]["archiveSha256"] = "0" * 64
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                canonical_bytes(source_result)
            )
        )
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )
        self.assertTrue(
            any("release identity must cross-bind" in failure for failure in failures)
        )

        source_result = json.loads(
            (
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT
                .read_text(encoding="ascii")
            )
        )
        snapshot_files = source_result["archiveReadback"]["snapshotFiles"]
        snapshot_files[
            f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip"
        ]["size"] = True
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                canonical_bytes(source_result)
            )
        )
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )
        self.assertTrue(
            any(
                "snapshot identities must cross-bind" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_lane_a_local_dmg_rejects_shape_and_encoding(
        self,
    ) -> None:
        source_result = json.loads(
            (
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT
                .read_text(encoding="ascii")
            )
        )
        source_result["unexpected"] = True
        mutated = (
            json.dumps(
                source_result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(mutated)
        )
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )

        pretty = (json.dumps(source_result, indent=2) + "\n").encode("ascii")
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(pretty)
        )
        self.assertTrue(
            any("not canonical JSON" in failure for failure in failures)
        )

        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                b'{"schemaVersion":2,"schemaVersion":2}\n'
            )
        )
        self.assertTrue(
            any("duplicate JSON key" in failure for failure in failures)
        )

    def test_current_source_g6_lane_a_followups_reject_shape_and_encoding(
        self,
    ) -> None:
        followups = (
            (
                "uninstall_reinstall_result_bytes",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT,
            ),
            (
                "state_recovery_result_bytes",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT,
            ),
            (
                "abrupt_process_result_bytes",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT,
            ),
            (
                "abrupt_process_receipt_bytes",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT,
            ),
        )
        for keyword, path in followups:
            with self.subTest(keyword=keyword):
                result = json.loads(path.read_text(encoding="ascii"))
                result["unexpected"] = True
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
                    .current_source_g6_lane_a_local_dmg_evidence_failures(
                        **{keyword: mutated}
                    )
                )
                self.assertTrue(
                    any("exact closed" in failure for failure in failures)
                )

                pretty = (json.dumps(result, indent=2) + "\n").encode(
                    "ascii"
                )
                failures = (
                    check_docs_hygiene
                    .current_source_g6_lane_a_local_dmg_evidence_failures(
                        **{keyword: pretty}
                    )
                )
                self.assertTrue(
                    any(
                        "not canonical JSON" in failure
                        for failure in failures
                    )
                )

                failures = (
                    check_docs_hygiene
                    .current_source_g6_lane_a_local_dmg_evidence_failures(
                        **{
                            keyword: (
                                b'{"schemaVersion":1,"schemaVersion":1}\n'
                            )
                        }
                    )
                )
                self.assertTrue(
                    any(
                        "duplicate JSON key" in failure
                        for failure in failures
                    )
                )

    def test_current_source_g6_lane_a_followups_reject_crossbinding_drift(
        self,
    ) -> None:
        def canonical_bytes(result: dict[str, object]) -> bytes:
            return (
                json.dumps(
                    result,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")

        uninstall_reinstall = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT
            .read_text(encoding="ascii")
        )
        uninstall_reinstall["installation"]["tree"]["sha256"] = "0" * 64
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                uninstall_reinstall_result_bytes=canonical_bytes(
                    uninstall_reinstall
                )
            )
        )
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )
        self.assertTrue(
            any("installed tree must be identical" in failure for failure in failures)
        )

        state_recovery = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT
            .read_text(encoding="ascii")
        )
        state_recovery["archiveReadback"]["snapshotFiles"][
            f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip"
        ]["size"] = True
        state_recovery["uninstall"]["removalCount"] = 3
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                state_recovery_result_bytes=canonical_bytes(state_recovery)
            )
        )
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )
        self.assertTrue(
            any(
                "snapshot identities must cross-bind" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any(
                "uninstall contract must be identical" in failure
                for failure in failures
            )
        )

        abrupt_process = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT
            .read_text(encoding="ascii")
        )
        abrupt_process["installation"]["tree"]["sha256"] = "0" * 64
        abrupt_process["archiveReadback"]["snapshotFiles"][
            f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip"
        ]["size"] = True
        abrupt_process["uninstall"]["removalCount"] = 3
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                abrupt_process_result_bytes=canonical_bytes(abrupt_process)
            )
        )
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )
        self.assertTrue(
            any(
                "snapshot identities must cross-bind" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any(
                "installed tree must be identical" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any(
                "uninstall contract must be identical" in failure
                for failure in failures
            )
        )

        receipt = json.loads(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT
            .read_text(encoding="ascii")
        )
        receipt["canonicalResult"]["sha256"] = "0" * 64
        receipt["runs"][1]["size"] += 1
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_evidence_failures(
                abrupt_process_receipt_bytes=canonical_bytes(receipt)
            )
        )
        self.assertTrue(
            any("exact closed" in failure for failure in failures)
        )
        self.assertTrue(
            any(
                "must bind the pinned canonical result" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any(
                "must bind both independent runs" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_lane_a_local_dmg_rejects_missing_and_symlink(
        self,
    ) -> None:
        actual_result = (
            check_docs_hygiene.CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT
        )
        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT / "dist/lifecycle"
        ) as temporary:
            temporary_root = Path(temporary)
            missing_result = temporary_root / "missing.json"
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT",
                missing_result,
            ):
                failures = (
                    check_docs_hygiene
                    .current_source_g6_lane_a_local_dmg_evidence_failures()
                )
            self.assertTrue(
                any("missing current-source" in failure for failure in failures)
            )

            symlink_result = temporary_root / "symlink.json"
            symlink_result.symlink_to(actual_result)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_RESULT",
                symlink_result,
            ):
                failures = (
                    check_docs_hygiene
                    .current_source_g6_lane_a_local_dmg_evidence_failures()
                )
            self.assertTrue(
                any("must not be a symlink" in failure for failure in failures)
            )

    def test_current_source_g6_lane_a_followups_reject_missing_and_symlink(
        self,
    ) -> None:
        followups = (
            (
                "CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT,
            ),
            (
                "CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_STATE_RECOVERY_RESULT,
            ),
            (
                "CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RESULT,
            ),
            (
                "CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_ABRUPT_PROCESS_RECEIPT,
            ),
            (
                "CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT,
            ),
        )
        for constant_name, actual_result in followups:
            with self.subTest(constant_name=constant_name):
                with tempfile.TemporaryDirectory(
                    dir=check_docs_hygiene.ROOT / "dist/lifecycle"
                ) as temporary:
                    temporary_root = Path(temporary)
                    missing_result = temporary_root / "missing.json"
                    with patch.object(
                        check_docs_hygiene,
                        constant_name,
                        missing_result,
                    ):
                        failures = (
                            check_docs_hygiene
                            .current_source_g6_lane_a_local_dmg_evidence_failures()
                        )
                    self.assertTrue(
                        any(
                            "missing current-source" in failure
                            for failure in failures
                        )
                    )

                    symlink_result = temporary_root / "symlink.json"
                    symlink_result.symlink_to(actual_result)
                    with patch.object(
                        check_docs_hygiene,
                        constant_name,
                        symlink_result,
                    ):
                        failures = (
                            check_docs_hygiene
                            .current_source_g6_lane_a_local_dmg_evidence_failures()
                        )
                    self.assertTrue(
                        any(
                            "must not be a symlink" in failure
                            for failure in failures
                        )
                    )

    def test_lifecycle_source_binding_rejects_historical_successor_mix(
        self,
    ) -> None:
        runner = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER
        )
        test = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_TEST
        )
        expected_sources = {
            runner,
            test,
            check_docs_hygiene.CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER
            ),
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
        }
        source_bytes = {path: path.read_bytes() for path in expected_sources}
        runner_sha256 = hashlib.sha256(source_bytes[runner]).hexdigest()
        successor_map = dict(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LIFECYCLE_SUCCESSOR_SHA256_BY_PATH
        )
        successor_map[runner] = "f" * 64
        with (
            patch.object(
                check_docs_hygiene,
                (
                    "CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_"
                    "EXPECTED_RUNNER_SHA256"
                ),
                runner_sha256,
            ),
            patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_LIFECYCLE_SUCCESSOR_SHA256_BY_PATH",
                successor_map,
            ),
            patch.object(
                check_docs_hygiene,
                "current_build24_macos_local_dmg_install_evidence_failures",
                return_value=[],
            ),
        ):
            failures = (
                check_docs_hygiene
                .current_build24_macos_local_dmg_uninstall_reinstall_evidence_failures(
                    source_bytes_by_path=source_bytes
                )
            )
        self.assertTrue(
            any(
                "complete historical or current-source G6 successor tuple"
                in failure
                for failure in failures
            )
        )
        self.assertFalse(
            any(
                str(runner.relative_to(check_docs_hygiene.ROOT)) in failure
                and "found" in failure
                for failure in failures
            )
        )
        self.assertFalse(
            any(
                str(test.relative_to(check_docs_hygiene.ROOT)) in failure
                and "found" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_primary_rejects_missing_and_symlink(
        self,
    ) -> None:
        actual_result = (
            check_docs_hygiene.CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
        )
        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT / "dist/reproducibility"
        ) as temporary:
            temporary_root = Path(temporary)
            missing_result = temporary_root / "missing.json"
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT",
                missing_result,
            ):
                failures = (
                    check_docs_hygiene
                    .current_source_g6_reproducibility_failures()
                )
            self.assertTrue(
                any("missing current-source G6" in failure for failure in failures)
            )

            symlink_result = temporary_root / "symlink.json"
            symlink_result.symlink_to(actual_result)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT",
                symlink_result,
            ):
                failures = (
                    check_docs_hygiene
                    .current_source_g6_reproducibility_failures()
                )
            self.assertTrue(
                any("must not be a symlink" in failure for failure in failures)
            )

    def test_current_source_g6_swift_root_diagnostics_reject_missing_and_symlink(
        self,
    ) -> None:
        contracts = list(
            check_docs_hygiene.CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS
        )
        source_contract = contracts[0]
        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT / "dist/reproducibility"
        ) as temporary:
            temporary_root = Path(temporary)
            missing_result = temporary_root / "missing.json"
            contracts[0] = replace(source_contract, path=missing_result)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS",
                tuple(contracts),
            ):
                failures = (
                    check_docs_hygiene
                    .current_source_g6_swift_root_diagnostic_failures()
                )
            self.assertTrue(
                any("missing current-source" in failure for failure in failures)
            )

            symlink_result = temporary_root / "symlink.json"
            symlink_result.symlink_to(source_contract.path)
            contracts[0] = replace(source_contract, path=symlink_result)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_SWIFT_ROOT_DIAGNOSTIC_RESULTS",
                tuple(contracts),
            ):
                failures = (
                    check_docs_hygiene
                    .current_source_g6_swift_root_diagnostic_failures()
                )
            self.assertTrue(
                any("must not be a symlink" in failure for failure in failures)
            )

    def test_current_source_g6_evidence_rejects_read_time_symlink_swap(
        self,
    ) -> None:
        cases = (
            (
                "primary",
                "dist/reproducibility",
                "CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT,
                check_docs_hygiene
                .current_source_g6_reproducibility_failures,
            ),
            (
                "idle",
                "dist/lifecycle",
                "CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT",
                check_docs_hygiene
                .CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT,
                check_docs_hygiene
                .current_source_g6_lane_a_idle_resource_evidence_failures,
            ),
        )
        for (
            label,
            temporary_parent,
            constant_name,
            source_path,
            validator,
        ) in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory(
                    dir=check_docs_hygiene.ROOT / temporary_parent
                ) as temporary:
                    temporary_root = Path(temporary)
                    candidate = temporary_root / "candidate.json"
                    identical_target = temporary_root / "identical.json"
                    source_bytes = source_path.read_bytes()
                    candidate.write_bytes(source_bytes)
                    identical_target.write_bytes(source_bytes)
                    real_read = check_docs_hygiene.os.read
                    swapped = False

                    def swapping_read(
                        descriptor: int,
                        count: int,
                    ) -> bytes:
                        nonlocal swapped
                        chunk = real_read(descriptor, count)
                        if chunk and not swapped:
                            candidate.unlink()
                            candidate.symlink_to(identical_target)
                            swapped = True
                        return chunk

                    with (
                        patch.object(
                            check_docs_hygiene,
                            constant_name,
                            candidate,
                        ),
                        patch.object(
                            check_docs_hygiene.os,
                            "read",
                            side_effect=swapping_read,
                        ),
                    ):
                        failures = validator()

                    self.assertTrue(swapped)
                    self.assertTrue(
                        any(
                            "changed during stable no-follow read" in failure
                            or "must not be a symlink" in failure
                            or "final path identity differs" in failure
                            for failure in failures
                        ),
                        failures,
                    )

    def test_current_source_g6_lane_a_local_dmg_crossbinds_primary_bytes(
        self,
    ) -> None:
        primary_result = json.loads(
            (
                check_docs_hygiene
                .CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT
                .read_text(encoding="ascii")
            )
        )
        for build in primary_result["builds"]:
            build["archive"]["sha256"] = "0" * 64
        primary_result["source"]["sha256"] = "0" * 64
        primary_bytes = (
            json.dumps(
                primary_result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT / "dist/reproducibility"
        ) as temporary:
            primary_path = Path(temporary) / "mutated-primary.json"
            primary_path.write_bytes(primary_bytes)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_SOURCE_G6_REPRODUCIBILITY_RESULT",
                primary_path,
            ):
                failures = (
                    check_docs_hygiene
                    .current_source_g6_lane_a_local_dmg_evidence_failures()
                )
        self.assertTrue(
            any(
                "release identity must cross-bind" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any(
                "snapshot identities must cross-bind" in failure
                for failure in failures
            )
        )
        idle_relative = str(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_IDLE_RESOURCE_RESULT
            .relative_to(check_docs_hygiene.ROOT)
        )
        for binding in (
            "idle-resource release identity must cross-bind",
            "idle-resource snapshot identities must cross-bind",
            "idle-resource source snapshot must cross-bind",
        ):
            self.assertTrue(
                any(
                    idle_relative in failure and binding in failure
                    for failure in failures
                )
            )

    def test_current_source_g6_lane_a_local_dmg_documents_match(
        self,
    ) -> None:
        self.assertEqual(
            (
                check_docs_hygiene
                .current_source_g6_lane_a_local_dmg_document_failures()
            ),
            [],
        )
        body = (
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_BODY
        )
        normalized_body = " ".join(body.split())
        for required in (
            "run bound 266 release inputs",
            "g6-macos-unsealed-gate-source-binding-one.json",
            "six child results followed by the parent",
            "all seven evidence files",
            "four retained comparison-only diagnostic result files",
            "a4a3615717ac4786086220e5894d2c196d70e31f03892c2fc7e609ede4e50274",
            "Publication remained disabled",
        ):
            self.assertIn(required, normalized_body)

    def test_current_source_g6_lane_a_local_dmg_documents_reject_mutation(
        self,
    ) -> None:
        document_paths = (
            check_docs_hygiene.README_PATH,
            check_docs_hygiene.ROOT / "docs/roadmap.md",
            check_docs_hygiene.ROOT / "docs/handoff.md",
            check_docs_hygiene.ROOT / "docs/progress.md",
            check_docs_hygiene.ROOT / "docs/qa-evidence.md",
            check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC,
        )
        documents = {
            str(path.relative_to(check_docs_hygiene.ROOT)): path.read_text(
                encoding="utf-8"
            )
            for path in document_paths
        }
        readme = documents["README.md"]
        documents["README.md"] = readme.replace(
            "63eeefbd7d13bf86452f39fc69337246f8a7ed0b945b5793f7f3ed33f3974c42",
            "0" * 64,
            1,
        )
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_document_failures(
                document_text_by_relative=documents
            )
        )
        self.assertTrue(
            any(
                "README.md" in failure
                and "exact canonical body" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_lane_a_local_dmg_documents_reject_move(
        self,
    ) -> None:
        document_paths = (
            check_docs_hygiene.README_PATH,
            check_docs_hygiene.ROOT / "docs/roadmap.md",
            check_docs_hygiene.ROOT / "docs/handoff.md",
            check_docs_hygiene.ROOT / "docs/progress.md",
            check_docs_hygiene.ROOT / "docs/qa-evidence.md",
            check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC,
        )
        documents = {
            str(path.relative_to(check_docs_hygiene.ROOT)): path.read_text(
                encoding="utf-8"
            )
            for path in document_paths
        }
        readme = documents["README.md"]
        start = readme.index(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_START
        )
        end = readme.index(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_END
        ) + len(
            check_docs_hygiene
            .CURRENT_SOURCE_G6_LANE_A_LOCAL_DMG_DOCUMENT_END
        )
        block = readme[start:end]
        documents["README.md"] = (
            readme[:start] + readme[end:] + "\n\n" + block + "\n"
        )
        failures = (
            check_docs_hygiene
            .current_source_g6_lane_a_local_dmg_document_failures(
                document_text_by_relative=documents
            )
        )
        self.assertTrue(
            any(
                "README.md" in failure
                and "canonical document location" in failure
                for failure in failures
            )
        )

    def test_current_source_g6_default_gate_selectors_are_wired(
        self,
    ) -> None:
        gate_path = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        )
        gate_text = gate_path.read_text(encoding="utf-8")
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_default_gate_failures
        )
        self.assertEqual(validator(gate_text=gate_text), [])
        selectors = tuple(
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            + name
            for name in (
                "test_current_source_g6_reproducibility_matches_closed_contract",
                "test_current_source_g6_reproducibility_rejects_semantic_drift",
                "test_current_source_g6_reproducibility_rejects_noncanonical_json",
                "test_current_source_g6_swift_root_diagnostics_match_closed_contract",
                "test_current_source_g6_swift_root_diagnostics_reject_identity_shape_and_noncanonical_json",
                "test_current_source_g6_swift_root_diagnostics_reject_root_geometry_and_promotion",
                "test_current_source_g6_swift_root_diagnostics_reject_cross_mode_and_repeat_two_drift",
                "test_current_source_g6_swift_root_diagnostics_retain_recorded_source",
                "test_current_source_g6_swift_root_diagnostics_reject_missing_and_symlink",
                "test_current_source_g6_lifecycle_two_matches_runner_contract",
                "test_current_source_g6_lifecycle_two_rejects_parent_and_child_drift",
                "test_current_source_g6_lifecycle_two_rejects_path_alias_missing_and_symlink",
                "test_current_source_g6_lifecycle_two_uses_recorded_source_and_avoids_physical_helpers",
                "test_current_source_g6_lifecycle_two_is_full_mode_only",
                "test_current_source_g6_lane_a_local_dmg_matches_closed_contract",
                "test_current_source_g6_lane_a_idle_resource_matches_closed_contract",
                "test_current_source_g6_lane_a_idle_resource_rejects_drift",
                "test_current_source_g6_lane_a_idle_resource_rejects_crossbinding_drift",
                "test_current_source_g6_lane_a_local_dmg_rejects_drift",
                "test_current_source_g6_lane_a_local_dmg_rejects_shape_and_encoding",
                "test_current_source_g6_lane_a_followups_reject_shape_and_encoding",
                "test_current_source_g6_lane_a_followups_reject_crossbinding_drift",
                "test_current_source_g6_lane_a_local_dmg_rejects_missing_and_symlink",
                "test_current_source_g6_lane_a_followups_reject_missing_and_symlink",
                "test_current_source_g6_primary_rejects_missing_and_symlink",
                "test_current_source_g6_evidence_rejects_read_time_symlink_swap",
                "test_current_source_g6_lane_a_local_dmg_crossbinds_primary_bytes",
                "test_current_source_g6_lane_a_local_dmg_documents_match",
                "test_current_source_g6_lane_a_local_dmg_documents_reject_mutation",
                "test_current_source_g6_lane_a_local_dmg_documents_reject_move",
                "test_current_g7_nonsecurity_merge_full_local_candidate_block_is_exact_and_fail_closed",
                "test_current_g7_nonsecurity_merge_full_local_candidate_validator_is_wired_once",
                "test_current_g6_release_diagnostics_document_block_is_exact_and_fail_closed",
                "test_current_g6_release_diagnostics_validator_is_wired_once",
                "test_current_g7_document_ingestion_asan_block_is_exact_and_fail_closed",
                "test_current_g7_document_ingestion_asan_validator_is_wired_once",
                "test_current_g7_document_ingestion_mutation_block_is_exact_and_fail_closed",
                "test_current_g7_document_ingestion_mutation_validator_is_wired_once",
            )
        )
        for selector in selectors:
            with self.subTest(selector=selector):
                self.assertEqual(gate_text.count(selector), 1)
                failures = validator(
                    gate_text=gate_text.replace(
                        selector,
                        "REMOVED_CURRENT_SOURCE_G6_SELECTOR",
                        1,
                    )
                )
                self.assertTrue(
                    any(
                        "current-source G6" in failure
                        for failure in failures
                    )
                )

        product_ci_contract = (
            "run python3 -B script/check_product_ci.py\n"
            "run python3 -B script/check_product_ci.py --self-test\n"
        )
        self.assertEqual(gate_text.count(product_ci_contract), 1)
        for command in (
            "run python3 -B script/check_product_ci.py\n",
            "run python3 -B script/check_product_ci.py --self-test\n",
        ):
            with self.subTest(command=command.strip()):
                failures = validator(
                    gate_text=gate_text.replace(command, "", 1)
                )
                self.assertTrue(
                    any("product CI" in failure for failure in failures),
                    failures,
                )

        asan_mutation_commands = (
            "run bash -c 'swift test list > "
            ".build/aetherlink-product-ci-swift-test-list-v1.txt'\n"
            "run python3 -B script/check_product_ci.py "
            "--prepare-document-ingestion-asan-run\n"
            "run python3 -B script/check_product_ci.py "
            "--run-document-ingestion-asan-tests\n"
            "run python3 -B script/check_product_ci.py "
            "--write-document-ingestion-asan-binding\n"
            "run python3 -B script/check_product_ci.py "
            "--document-ingestion-asan-results\n"
            "run python3 -B script/check_product_ci.py "
            "--prepare-document-ingestion-mutation-run\n"
            "run python3 -B script/check_product_ci.py "
            "--run-document-ingestion-mutation-tests\n"
            "run python3 -B script/check_product_ci.py "
            "--write-document-ingestion-mutation-binding\n"
            "run python3 -B script/check_product_ci.py "
            "--document-ingestion-mutation-results\n"
        )
        self.assertEqual(gate_text.count(asan_mutation_commands), 1)
        for command in asan_mutation_commands.splitlines(keepends=True):
            with self.subTest(command=command.strip()):
                failures = validator(
                    gate_text=gate_text.replace(command, "", 1)
                )
                self.assertTrue(
                    any(
                        "DocumentIngestion ASan/mutation" in failure
                        for failure in failures
                    ),
                    failures,
                )
                duplicated = gate_text.rstrip() + "\n" + command
                duplicate_failures = validator(gate_text=duplicated)
                self.assertTrue(
                    any(
                        "DocumentIngestion ASan/mutation" in failure
                        for failure in duplicate_failures
                    ),
                    duplicate_failures,
                )
        reordered = asan_mutation_commands.replace(
            "run python3 -B script/check_product_ci.py "
            "--prepare-document-ingestion-asan-run\n"
            "run python3 -B script/check_product_ci.py "
            "--run-document-ingestion-asan-tests\n",
            "run python3 -B script/check_product_ci.py "
            "--run-document-ingestion-asan-tests\n"
            "run python3 -B script/check_product_ci.py "
            "--prepare-document-ingestion-asan-run\n",
            1,
        )
        failures = validator(
            gate_text=gate_text.replace(
                asan_mutation_commands,
                reordered,
                1,
            )
        )
        self.assertTrue(
            any(
                "DocumentIngestion ASan/mutation" in failure
                for failure in failures
            ),
            failures,
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

    def test_current_build24_clean_home_results_match_closed_contracts(
        self,
    ) -> None:
        cases = (
            (
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT
                ),
                (
                    check_docs_hygiene
                    .current_build24_macos_clean_home_installed_app_evidence_failures
                ),
                ("app", "buildNumber"),
            ),
            (
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT
                ),
                (
                    check_docs_hygiene
                    .current_build24_macos_clean_home_installed_state_recovery_evidence_failures
                ),
                ("stateRecovery", "migrationSQLite", "totalEventCount"),
            ),
        )

        for result_path, validator, mutation_path in cases:
            with self.subTest(path=result_path.name):
                self.assertEqual(validator(), [])
                result = json.loads(result_path.read_text(encoding="utf-8"))
                target = result
                for key in mutation_path[:-1]:
                    target = target[key]
                target[mutation_path[-1]] = True
                mutated = (
                    json.dumps(
                        result,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("ascii")

                failures = validator(mutated)
                self.assertTrue(
                    any("expected identity" in failure for failure in failures)
                )
                self.assertTrue(
                    any("exact closed" in failure for failure in failures)
                )

        for expected_result in (
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
            ),
        ):
            with self.subTest(scope=expected_result["scope"]):
                self.assertEqual(
                    expected_result["app"]["buildNumber"],
                    check_docs_hygiene.LOCAL_RELEASE_BUILD_NUMBER,
                )
                self.assertEqual(
                    expected_result["release"],
                    {
                        "archiveSha256": (
                            check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SHA256
                        ),
                        "manifestSha256": (
                            check_docs_hygiene
                            .LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256
                        ),
                        "releaseId": check_docs_hygiene.LOCAL_RELEASE_ID,
                    },
                )

    def test_current_build24_clean_home_sources_and_documents_are_bound(
        self,
    ) -> None:
        source_cases = (
            (
                check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_APP_RUNNER,
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256
                ),
            ),
            (
                check_docs_hygiene.MACOS_CLEAN_HOME_INSTALLED_APP_TEST,
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256
                ),
            ),
            (
                (
                    check_docs_hygiene
                    .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER
                ),
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
                ),
            ),
            (
                (
                    check_docs_hygiene
                    .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_TEST
                ),
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256
                ),
            ),
        )
        for path, expected_sha256 in source_cases:
            with self.subTest(path=path.name):
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    expected_sha256,
                )

        validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_BODY
        )
        for relative in targets:
            with self.subTest(relative=relative):
                path = check_docs_hygiene.ROOT / relative
                text = path.read_text(encoding="utf-8")
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end].strip(), expected_body)
                mutated_body = expected_body.replace(
                    "The canonical 2,250-byte result",
                    "A 2,250-byte result",
                    1,
                )
                self.assertNotEqual(mutated_body, expected_body)
                mutated = text[:start] + "\n" + mutated_body + "\n" + text[end:]
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exact canonical body SHA-256" in failure
                        for failure in failures
                    )
                )
                complete_block = (
                    start_marker
                    + "\n"
                    + expected_body
                    + "\n"
                    + end_marker
                )
                self.assertEqual(text.count(complete_block), 1)
                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                relocation_failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "canonical document location" in failure
                        for failure in relocation_failures
                    )
                )

        readme = check_docs_hygiene.README_PATH.read_text(encoding="utf-8")
        marker_mutations = (
            readme.replace(start_marker, "", 1),
            readme.replace(end_marker, "", 1),
            readme + f"\n{start_marker}\n{expected_body}\n{end_marker}\n",
            readme.replace(start_marker, "__BUILD24_START__", 1)
            .replace(end_marker, start_marker, 1)
            .replace("__BUILD24_START__", end_marker, 1),
        )
        for mutated in marker_mutations:
            failures = validator(
                document_text_by_relative={"README.md": mutated}
            )
            self.assertTrue(
                any(
                    "README.md" in failure
                    and "current Build 24 clean-HOME lifecycle" in failure
                    for failure in failures
                )
            )

    def test_current_build24_clean_home_validators_are_wired_into_main(
        self,
    ) -> None:
        required_calls = (
            "current_build24_macos_clean_home_installed_app_evidence_failures",
            (
                "current_build24_macos_clean_home_installed_state_"
                "recovery_evidence_failures"
            ),
            "current_build24_macos_clean_home_lifecycle_document_failures",
        )

        def top_level_extend_counts(source: str) -> dict[str, int]:
            module = ast.parse(source)
            main_function = next(
                node
                for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name == "main"
            )
            counts = {name: 0 for name in required_calls}

            def statement_definitely_terminates(
                statement: ast.stmt,
            ) -> bool:
                if isinstance(statement, (ast.Return, ast.Raise)):
                    return True
                if (
                    isinstance(statement, ast.If)
                    and _static_truth_value(statement.test) is True
                ):
                    return block_definitely_terminates(statement.body)
                if (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                ):
                    function = statement.value.func
                    return (
                        isinstance(function, ast.Name)
                        and function.id in {"exit", "quit"}
                    ) or (
                        isinstance(function, ast.Attribute)
                        and isinstance(function.value, ast.Name)
                        and function.value.id == "sys"
                        and function.attr == "exit"
                    )
                return False

            def block_definitely_terminates(
                statements: list[ast.stmt],
            ) -> bool:
                return any(
                    statement_definitely_terminates(statement)
                    for statement in statements
                )

            for statement in main_function.body:
                if statement_definitely_terminates(statement):
                    break
                if not (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Attribute)
                    and statement.value.func.attr == "extend"
                    and isinstance(statement.value.func.value, ast.Name)
                    and statement.value.func.value.id == "failures"
                    and len(statement.value.args) == 1
                    and not statement.value.keywords
                ):
                    continue
                validator_call = statement.value.args[0]
                if not (
                    isinstance(validator_call, ast.Call)
                    and isinstance(validator_call.func, ast.Name)
                    and not validator_call.args
                    and not validator_call.keywords
                ):
                    continue
                if validator_call.func.id in counts:
                    counts[validator_call.func.id] += 1
            return counts

        source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            top_level_extend_counts(source),
            {name: 1 for name in required_calls},
        )

        for name in required_calls:
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            self.assertEqual(source.count(wrapper), 1)
            mutations = {
                "bare_call": source.replace(
                    wrapper,
                    f"    {name}()",
                    1,
                ),
                "dead_branch": source.replace(
                    wrapper,
                    (
                        "    if False:\n"
                        "        failures.extend(\n"
                        f"            {name}()\n"
                        "        )"
                    ),
                    1,
                ),
            }
            for label, mutated in mutations.items():
                with self.subTest(name=name, label=label):
                    counts = top_level_extend_counts(mutated)
                    self.assertEqual(counts[name], 0)

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

    def test_current_build24_local_dmg_result_and_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_install_evidence_failures
        )
        self.assertEqual(validator(), [])

        result_path = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RESULT
        )
        baseline = json.loads(result_path.read_text(encoding="utf-8"))
        mutations: list[dict[str, object]] = []

        schema_bool = copy.deepcopy(baseline)
        schema_bool["schemaVersion"] = True
        mutations.append(schema_bool)

        boolean_integer = copy.deepcopy(baseline)
        boolean_integer["mount"]["readOnly"] = 1
        mutations.append(boolean_integer)

        integer_float = copy.deepcopy(baseline)
        integer_float["state"]["databaseCount"] = 3.0
        mutations.append(integer_float)

        nested_string = copy.deepcopy(baseline)
        nested_string["archiveReadback"]["mode"] = "historical"
        mutations.append(nested_string)

        missing_key = copy.deepcopy(baseline)
        missing_key["image"].pop("verified")
        mutations.append(missing_key)

        unknown_key = copy.deepcopy(baseline)
        unknown_key["unexpected"] = True
        mutations.append(unknown_key)

        reversed_runs = copy.deepcopy(baseline)
        reversed_runs["launchServices"]["runs"].reverse()
        mutations.append(reversed_runs)

        changed_sqlite = copy.deepcopy(baseline)
        changed_sqlite["state"]["sqlite"][0]["unexpected"] = True
        mutations.append(changed_sqlite)

        for mutation in mutations:
            with self.subTest(mutation=mutation):
                payload = (
                    json.dumps(
                        mutation,
                        ensure_ascii=True,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                ).encode("ascii")
                failures = validator(result_bytes=payload)
                self.assertTrue(
                    any(
                        "expected identity" in failure
                        for failure in failures
                    )
                )
                self.assertTrue(
                    any(
                        "exact closed" in failure
                        for failure in failures
                    )
                )

        baseline_bytes = result_path.read_bytes()
        duplicate = baseline_bytes.replace(
            b'"schemaVersion":2',
            b'"schemaVersion":2,"schemaVersion":2',
            1,
        )
        for label, payload in (
            ("duplicate", duplicate),
            ("malformed", b"{"),
        ):
            with self.subTest(label=label):
                failures = validator(result_bytes=payload)
                self.assertTrue(
                    any(
                        "invalid packaged-app lifecycle JSON" in failure
                        for failure in failures
                    )
                )

        expected_sources = {
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_TEST
            ),
            check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
        }
        source_bytes = {
            path: path.read_bytes()
            for path in expected_sources
        }
        for path in expected_sources:
            with self.subTest(source=path.name, mutation="bytes"):
                mutated_sources = dict(source_bytes)
                mutated_sources[path] += b"\n"
                failures = validator(
                    source_bytes_by_path=mutated_sources
                )
                self.assertTrue(
                    any(
                        str(path.relative_to(check_docs_hygiene.ROOT))
                        in failure
                        and "source SHA-256" in failure
                        for failure in failures
                    )
                )
            with self.subTest(source=path.name, mutation="missing"):
                missing_sources = dict(source_bytes)
                missing_sources.pop(path)
                failures = validator(
                    source_bytes_by_path=missing_sources
                )
                self.assertTrue(
                    any(
                        str(path.relative_to(check_docs_hygiene.ROOT))
                        in failure
                        and "cannot read" in failure
                        for failure in failures
                    )
                )

        release_map_failures = validator(release_bytes_by_path={})
        self.assertTrue(
            any(
                "release byte map must contain exactly" in failure
                for failure in release_map_failures
            )
        )

        archive_path = (
            check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR
            / f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip"
        )
        manifest_path = (
            check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR
            / f"{check_docs_hygiene.LOCAL_RELEASE_ID}.manifest.json"
        )
        checksum_path = (
            check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR
            / f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip.sha256"
        )
        release_bytes = {
            path: path.read_bytes()
            for path in (archive_path, manifest_path, checksum_path)
        }
        self.assertEqual(
            validator(release_bytes_by_path=release_bytes),
            [],
        )

        archive_payload = release_bytes[archive_path]
        mutated_release = dict(release_bytes)
        mutated_release[archive_path] = (
            bytes((archive_payload[0] ^ 1,))
            + archive_payload[1:]
        )
        failures = validator(release_bytes_by_path=mutated_release)
        self.assertTrue(
            any("checksum sidecar differs" in failure for failure in failures)
        )
        self.assertTrue(
            any("snapshot identities do not match" in failure for failure in failures)
        )
        self.assertTrue(
            any("release identity does not match" in failure for failure in failures)
        )
        del mutated_release

        mutated_release = dict(release_bytes)
        mutated_release[checksum_path] = (
            release_bytes[checksum_path] + b" "
        )
        failures = validator(release_bytes_by_path=mutated_release)
        self.assertTrue(
            any("checksum sidecar differs" in failure for failure in failures)
        )
        self.assertTrue(
            any("snapshot identities do not match" in failure for failure in failures)
        )

        manifest = json.loads(
            release_bytes[manifest_path].decode("utf-8")
        )
        manifest["release"]["buildNumber"] = (
            check_docs_hygiene.LOCAL_RELEASE_BUILD_NUMBER + 1
        )
        mutated_release = dict(release_bytes)
        mutated_release[manifest_path] = (
            json.dumps(
                manifest,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
        failures = validator(release_bytes_by_path=mutated_release)
        self.assertTrue(
            any(
                "manifest release.buildNumber differs" in failure
                for failure in failures
            )
        )

        manifest = json.loads(
            release_bytes[manifest_path].decode("utf-8")
        )
        app_member = next(
            row
            for row in manifest["members"]
            if row["path"].startswith("macos/AetherLink.app/")
        )
        app_member["size"] += 1
        mutated_release = dict(release_bytes)
        mutated_release[manifest_path] = (
            json.dumps(
                manifest,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
        failures = validator(release_bytes_by_path=mutated_release)
        self.assertTrue(
            any(
                "installed app tree does not derive" in failure
                for failure in failures
            )
        )

        expected_result = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT
        )
        self.assertEqual(
            expected_result["release"]["releaseId"],
            check_docs_hygiene.LOCAL_RELEASE_ID,
        )
        self.assertEqual(
            expected_result["archiveReadback"]["snapshotFiles"][
                f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip"
            ]["sha256"],
            check_docs_hygiene.LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
        )
        historical = json.loads(
            check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT.read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            historical["release"]["releaseId"],
            check_docs_hygiene.HISTORICAL_BUILD20_RELEASE_ID,
        )

    def test_current_build24_local_dmg_uninstall_reinstall_result_and_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_uninstall_reinstall_evidence_failures
        )
        self.assertEqual(validator(), [])

        result_path = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RESULT
        )
        baseline = json.loads(result_path.read_text(encoding="utf-8"))
        mutations: list[dict[str, object]] = []

        schema_bool = copy.deepcopy(baseline)
        schema_bool["schemaVersion"] = True
        mutations.append(schema_bool)

        install_count_bool = copy.deepcopy(baseline)
        install_count_bool["installation"]["installCount"] = True
        mutations.append(install_count_bool)

        install_count_float = copy.deepcopy(baseline)
        install_count_float["installation"]["installCount"] = 2.0
        mutations.append(install_count_float)

        cycle_count_bool = copy.deepcopy(baseline)
        cycle_count_bool["mount"]["cycleCount"] = True
        mutations.append(cycle_count_bool)

        wrong_origin = copy.deepcopy(baseline)
        wrong_origin["installation"]["origin"] = "extracted-archive"
        mutations.append(wrong_origin)

        wrong_image = copy.deepcopy(baseline)
        wrong_image["image"]["sameImageBytesUsedForBothInstalls"] = False
        mutations.append(wrong_image)

        missing_key = copy.deepcopy(baseline)
        missing_key["uninstall"].pop("removalCount")
        mutations.append(missing_key)

        unknown_key = copy.deepcopy(baseline)
        unknown_key["unexpected"] = True
        mutations.append(unknown_key)

        reversed_runs = copy.deepcopy(baseline)
        reversed_runs["launchServices"]["runs"].reverse()
        mutations.append(reversed_runs)

        with patch.object(
            check_docs_hygiene,
            "current_build24_macos_local_dmg_install_evidence_failures",
            return_value=[],
        ):
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    payload = (
                        json.dumps(
                            mutation,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("ascii")
                    failures = validator(result_bytes=payload)
                    self.assertTrue(
                        any(
                            "expected identity" in failure
                            for failure in failures
                        )
                    )
                    self.assertTrue(
                        any(
                            "exact closed" in failure
                            for failure in failures
                        )
                    )

            baseline_bytes = result_path.read_bytes()
            duplicate = baseline_bytes.replace(
                b'"schemaVersion":1',
                b'"schemaVersion":1,"schemaVersion":1',
                1,
            )
            for label, payload in (
                ("duplicate", duplicate),
                ("malformed", b"{"),
            ):
                with self.subTest(label=label):
                    failures = validator(result_bytes=payload)
                    self.assertTrue(
                        any(
                            "invalid packaged-app lifecycle JSON" in failure
                            for failure in failures
                        )
                    )

        expected_sources = {
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_TEST
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER
            ),
            check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER
            ),
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
        }
        source_bytes = {
            path: path.read_bytes()
            for path in expected_sources
        }
        with patch.object(
            check_docs_hygiene,
            "current_build24_macos_local_dmg_install_evidence_failures",
            return_value=[],
        ):
            for path in expected_sources:
                with self.subTest(source=path.name, mutation="bytes"):
                    mutated_sources = dict(source_bytes)
                    mutated_sources[path] += b"\n"
                    failures = validator(
                        source_bytes_by_path=mutated_sources
                    )
                    self.assertTrue(
                        any(
                            str(
                                path.relative_to(check_docs_hygiene.ROOT)
                            )
                            in failure
                            and "source SHA-256" in failure
                            for failure in failures
                        )
                    )
                with self.subTest(source=path.name, mutation="missing"):
                    missing_sources = dict(source_bytes)
                    missing_sources.pop(path)
                    failures = validator(
                        source_bytes_by_path=missing_sources
                    )
                    self.assertTrue(
                        any(
                            "exactly the six bound source files" in failure
                            for failure in failures
                        )
                    )
                    self.assertTrue(
                        any(
                            str(
                                path.relative_to(check_docs_hygiene.ROOT)
                            )
                            in failure
                            and "cannot read" in failure
                            for failure in failures
                        )
                    )

        archive_path = (
            check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR
            / f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip"
        )
        manifest_path = (
            check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR
            / f"{check_docs_hygiene.LOCAL_RELEASE_ID}.manifest.json"
        )
        checksum_path = (
            check_docs_hygiene.LOCAL_RELEASE_ARCHIVE_DIR
            / f"{check_docs_hygiene.LOCAL_RELEASE_ID}.zip.sha256"
        )
        release_bytes = {
            path: path.read_bytes()
            for path in (archive_path, manifest_path, checksum_path)
        }
        self.assertEqual(
            validator(release_bytes_by_path=release_bytes),
            [],
        )
        archive_payload = release_bytes[archive_path]
        mutated_release = dict(release_bytes)
        mutated_release[archive_path] = (
            bytes((archive_payload[0] ^ 1,))
            + archive_payload[1:]
        )
        failures = validator(release_bytes_by_path=mutated_release)
        self.assertTrue(
            any(
                "checksum sidecar differs" in failure
                for failure in failures
            )
        )
        self.assertTrue(
            any(
                "snapshot identities do not match" in failure
                for failure in failures
            )
        )

    def test_current_build24_local_dmg_uninstall_reinstall_documents_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_uninstall_reinstall_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_BODY
        )
        complete_block = (
            start_marker
            + "\n"
            + expected_body
            + "\n"
            + end_marker
        )
        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end].strip(), expected_body)
                self.assertEqual(text.count(complete_block), 1)

                mutated_body = expected_body.replace(
                    "same canonical 3,485-byte result",
                    "a 3,485-byte result",
                    1,
                )
                mutated = (
                    text[:start]
                    + "\n"
                    + mutated_body
                    + "\n"
                    + text[end:]
                )
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exact canonical body SHA-256" in failure
                        for failure in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "canonical document location" in failure
                        for failure in failures
                    )
                )

        readme = check_docs_hygiene.README_PATH.read_text(encoding="utf-8")
        marker_mutations = (
            readme.replace(start_marker, "", 1),
            readme.replace(end_marker, "", 1),
            readme + f"\n{complete_block}\n",
            readme.replace(
                complete_block,
                start_marker + "\n" + end_marker,
                1,
            ),
        )
        for mutated in marker_mutations:
            failures = validator(
                document_text_by_relative={"README.md": mutated}
            )
            self.assertTrue(
                any(
                    "README.md" in failure
                    and "uninstall/reinstall lifecycle" in failure
                    for failure in failures
                )
            )

        chain_start = readme.index(
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
        )
        chain_end = readme.index(end_marker) + len(end_marker)
        hidden = (
            readme[:chain_start]
            + "<details>\n"
            + readme[chain_start:chain_end]
            + "\n</details>"
            + readme[chain_end:]
        )
        failures = chain_validator(
            document_text_by_relative={"README.md": hidden}
        )
        self.assertTrue(
            any(
                "README.md" in failure
                and "hidden Markdown or HTML" in failure
                for failure in failures
            )
        )

        body_mutations = (
            (
                "result path",
                (
                    "macos-packaged-app-build-24-local-dmg-"
                    "uninstall-reinstall-v1.json"
                ),
                (
                    "macos-packaged-app-build-24-local-dmg-"
                    "uninstall-reinstall-v2.json"
                ),
            ),
            ("size", "3,485-byte", "3,486-byte"),
            (
                "result sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RESULT_SHA256
                ),
                "0" * 64,
            ),
            (
                "runner sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_RUNNER_SHA256
                ),
                "1" * 64,
            ),
            (
                "test sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_EXPECTED_TEST_SHA256
                ),
                "2" * 64,
            ),
            (
                "boundary",
                (
                    "same-created-image uninstall/reinstall observation. "
                    "It does not establish"
                ),
                (
                    "same-created-image uninstall/reinstall observation. "
                    "It establishes"
                ),
            ),
        )
        for label, old, new in body_mutations:
            with self.subTest(label=label):
                mutated = readme.replace(old, new, 1)
                failures = validator(
                    document_text_by_relative={"README.md": mutated}
                )
                self.assertTrue(
                    any(
                        "README.md" in failure
                        and "exact canonical body SHA-256" in failure
                        for failure in failures
                    )
                )

    def test_current_build24_local_dmg_documents_are_bound(self) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_lifecycle_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_LIFECYCLE_DOCUMENT_BODY
        )
        complete_block = (
            start_marker
            + "\n"
            + expected_body
            + "\n"
            + end_marker
        )
        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end].strip(), expected_body)
                self.assertEqual(text.count(complete_block), 1)

                mutated_body = expected_body.replace(
                    "The canonical 3,038-byte result",
                    "A 3,038-byte result",
                    1,
                )
                mutated = (
                    text[:start]
                    + "\n"
                    + mutated_body
                    + "\n"
                    + text[end:]
                )
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "exact canonical body SHA-256" in failure
                        for failure in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "canonical document location" in failure
                        for failure in failures
                    )
                )

                chain_start = text.index(
                    check_docs_hygiene
                    .CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
                )
                chain_terminal = (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_END
                )
                chain_end = (
                    text.index(chain_terminal) + len(chain_terminal)
                )
                chain = text[chain_start:chain_end]
                relocated_chain = (
                    text[:chain_start]
                    + text[chain_end:]
                    + "\n\n"
                    + chain
                    + "\n"
                )
                chain_failures = chain_validator(
                    document_text_by_relative={
                        relative: relocated_chain,
                    }
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "canonical external predecessor" in failure
                        for failure in chain_failures
                    )
                )

                predecessor = (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LIFECYCLE_CHAIN_PREDECESSOR_BY_DOCUMENT[
                        relative
                    ]
                )
                outer_span_start = text.index(predecessor)
                terminal_start = (
                    text.index(chain_terminal) + len(chain_terminal)
                )
                outer_span_end = text.find("\n\n", terminal_start + 2)
                if outer_span_end == -1:
                    outer_span_end = len(text)
                outer_span = text[outer_span_start:outer_span_end]
                relocated_outer_span = (
                    text[:outer_span_start]
                    + text[outer_span_end:]
                ).rstrip() + "\n\n" + outer_span + "\n"
                outer_failures = chain_validator(
                    document_text_by_relative={
                        relative: relocated_outer_span,
                    }
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "outer document identity" in failure
                        for failure in outer_failures
                    )
                )

        readme = check_docs_hygiene.README_PATH.read_text(encoding="utf-8")
        marker_mutations = (
            readme.replace(start_marker, "", 1),
            readme.replace(end_marker, "", 1),
            readme + f"\n{complete_block}\n",
            readme.replace(
                complete_block,
                start_marker + "\n" + end_marker,
                1,
            ),
            readme.replace(start_marker, "__DMG_START__", 1)
            .replace(end_marker, start_marker, 1)
            .replace("__DMG_START__", end_marker, 1),
        )
        for mutated in marker_mutations:
            failures = validator(
                document_text_by_relative={"README.md": mutated}
            )
            self.assertTrue(
                any(
                    "README.md" in failure
                    and "current Build 24 local-DMG lifecycle" in failure
                    for failure in failures
                )
            )

        readme_chain_start = readme.index(
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
        )
        chain_terminal = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_DOCUMENT_END
        )
        readme_chain_end = (
            readme.index(chain_terminal) + len(chain_terminal)
        )
        for label, opening, closing in (
            ("fence", "```\n", "\n```"),
            (
                "invalid-closing-fence",
                "```\n```not-a-valid-closing-fence\n",
                "\n```",
            ),
            ("html-comment", "<!--\n", "\n-->"),
            ("details", "<details>\n", "\n</details>"),
            ("pre", "<pre>\n", "\n</pre>"),
            ("hidden-container", "<div hidden>\n", "\n</div>"),
        ):
            with self.subTest(hidden_context=label):
                hidden = (
                    readme[:readme_chain_start]
                    + opening
                    + readme[readme_chain_start:readme_chain_end]
                    + closing
                    + readme[readme_chain_end:]
                )
                failures = chain_validator(
                    document_text_by_relative={"README.md": hidden}
                )
                self.assertTrue(
                    any(
                        "README.md" in failure
                        and "hidden Markdown or HTML" in failure
                        for failure in failures
                    )
                )

        body_mutations = (
            (
                "result path",
                "macos-packaged-app-build-24-local-dmg-install-v2.json",
                "macos-packaged-app-build-24-local-dmg-install-v1.json",
            ),
            ("size", "3,038-byte", "3,039-byte"),
            (
                "result sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256
                ),
                "0" * 64,
            ),
            (
                "runner sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256
                ),
                "1" * 64,
            ),
            (
                "test sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256
                ),
                "2" * 64,
            ),
            (
                "boundary",
                "does not establish Finder",
                "establishes Finder",
            ),
        )
        for label, old, new in body_mutations:
            with self.subTest(label=label):
                mutated = readme.replace(old, new, 1)
                failures = validator(
                    document_text_by_relative={"README.md": mutated}
                )
                self.assertTrue(
                    any(
                        "README.md" in failure
                        and "exact canonical body SHA-256" in failure
                        for failure in failures
                    )
                )

    def test_current_build24_local_dmg_validators_are_wired_into_main(
        self,
    ) -> None:
        required_calls = (
            "current_build24_macos_local_dmg_install_evidence_failures",
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "evidence_failures"
            ),
            "current_build24_macos_local_dmg_lifecycle_document_failures",
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "document_failures"
            ),
            "current_build24_macos_local_dmg_default_gate_failures",
        )

        def top_level_extend_counts(source: str) -> dict[str, int]:
            module = ast.parse(source)
            main_function = next(
                node
                for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name == "main"
            )
            counts = {name: 0 for name in required_calls}

            def statement_definitely_terminates(
                statement: ast.stmt,
            ) -> bool:
                if isinstance(statement, (ast.Return, ast.Raise)):
                    return True
                if (
                    isinstance(statement, ast.If)
                    and _static_truth_value(statement.test) is True
                ):
                    return block_definitely_terminates(statement.body)
                if (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                ):
                    function = statement.value.func
                    return (
                        isinstance(function, ast.Name)
                        and function.id in {"exit", "quit"}
                    ) or (
                        isinstance(function, ast.Attribute)
                        and isinstance(function.value, ast.Name)
                        and function.value.id == "sys"
                        and function.attr == "exit"
                    )
                return False

            def block_definitely_terminates(
                statements: list[ast.stmt],
            ) -> bool:
                return any(
                    statement_definitely_terminates(statement)
                    for statement in statements
                )

            for statement in main_function.body:
                if statement_definitely_terminates(statement):
                    break
                if not (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Attribute)
                    and statement.value.func.attr == "extend"
                    and isinstance(statement.value.func.value, ast.Name)
                    and statement.value.func.value.id == "failures"
                    and len(statement.value.args) == 1
                    and not statement.value.keywords
                ):
                    continue
                validator_call = statement.value.args[0]
                if not (
                    isinstance(validator_call, ast.Call)
                    and isinstance(validator_call.func, ast.Name)
                    and not validator_call.args
                    and not validator_call.keywords
                ):
                    continue
                if validator_call.func.id in counts:
                    counts[validator_call.func.id] += 1
            return counts

        checker_path = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        )
        source = checker_path.read_text(encoding="utf-8")
        self.assertEqual(
            top_level_extend_counts(source),
            {name: 1 for name in required_calls},
        )
        for name in required_calls:
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            self.assertEqual(source.count(wrapper), 1)
            mutations = (
                source.replace(wrapper, f"    {name}()", 1),
                source.replace(
                    wrapper,
                    (
                        "    if False:\n"
                        "        failures.extend(\n"
                        f"            {name}()\n"
                        "        )"
                    ),
                    1,
                ),
            )
            for mutated in mutations:
                with self.subTest(name=name):
                    self.assertEqual(
                        top_level_extend_counts(mutated)[name],
                        0,
                    )
            for label, terminator in (
                (
                    "constant_return",
                    "    if True:\n        return 0\n",
                ),
                (
                    "truthy_integer_return",
                    "    if 1:\n        return 0\n",
                ),
                (
                    "constant_not_return",
                    "    if not False:\n        return 0\n",
                ),
                (
                    "constant_compare_return",
                    "    if 1 == 1:\n        return 0\n",
                ),
                (
                    "raise",
                    "    raise RuntimeError('stop')\n",
                ),
                (
                    "exit",
                    "    sys.exit(0)\n",
                ),
            ):
                with self.subTest(name=name, terminator=label):
                    unreachable = source.replace(
                        wrapper,
                        terminator + wrapper,
                        1,
                    )
                    self.assertEqual(
                        top_level_extend_counts(unreachable)[name],
                        0,
                    )

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        gate_validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_default_gate_failures
        )
        self.assertEqual(gate_validator(gate_text=gate_source), [])
        selector_names = (
            "test_current_build24_local_dmg_result_and_sources_are_bound",
            "test_current_build24_local_dmg_documents_are_bound",
            "test_current_build24_local_dmg_validators_are_wired_into_main",
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "result_and_sources_are_bound"
            ),
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "documents_are_bound"
            ),
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "validators_are_wired_into_main"
            ),
        )
        for selector_name in selector_names:
            selector = (
                "script.test_documentation_handoff_guards."
                "DocumentationHandoffGuardTests."
                + selector_name
            )
            with self.subTest(selector=selector_name):
                self.assertEqual(gate_source.count(selector), 1)

        target_selector = (
            "  script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
            "test_current_build24_local_dmg_result_and_sources_are_bound \\"
        )
        gate_block_start = gate_source.index(
            "run python3 script/check_docs_hygiene.py\n"
            "run python3 -B -m unittest \\"
        )
        gate_block_end = gate_source.index(
            "run python3 script/check_license.py",
            gate_block_start,
        )
        gate_prefix = gate_source[:gate_block_start]
        gate_block = gate_source[gate_block_start:gate_block_end]
        gate_suffix = gate_source[gate_block_end:]
        gate_mutations = (
            gate_source.replace(
                target_selector,
                "# " + target_selector,
                1,
            ),
            gate_source.replace(
                "run python3 script/check_docs_hygiene.py\n"
                "run python3 -B -m unittest \\",
                "run python3 script/check_docs_hygiene.py\n"
                "exit 0\n"
                "run python3 -B -m unittest \\",
                1,
            ),
            gate_source.replace(
                target_selector,
                "",
                1,
            )
            + "\n# "
            + target_selector
            + "\n",
            gate_prefix + "exit 0\n" + gate_block + gate_suffix,
            gate_prefix + ":; exit 0\n" + gate_block + gate_suffix,
            (
                gate_prefix
                + "inactive_build24_gate() {\n"
                + gate_block
                + "}\n"
                + gate_suffix
            ),
            (
                gate_prefix
                + ": <<'AETHERLINK_INACTIVE_BUILD24_GATE'\n"
                + gate_block
                + "AETHERLINK_INACTIVE_BUILD24_GATE\n"
                + gate_suffix
            ),
            (
                gate_prefix
                + "if false; then\n"
                + gate_block
                + "fi\n"
                + gate_suffix
            ),
            (
                gate_prefix
                + ": '\n"
                + gate_block
                + "'\n"
                + gate_suffix
            ),
            (
                gate_prefix
                + "false && {\n"
                + gate_block
                + "}\n"
                + gate_suffix
            ),
            (
                gate_prefix
                + "false && (\n"
                + gate_block
                + ")\n"
                + gate_suffix
            ),
            (
                gate_prefix
                + "false &&\n"
                + gate_block
                + gate_suffix
            ),
        )
        for mutation in gate_mutations:
            self.assertTrue(gate_validator(gate_text=mutation))

    def test_current_build24_local_dmg_uninstall_reinstall_validators_are_wired_into_main(
        self,
    ) -> None:
        checker_source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        for name in (
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "evidence_failures"
            ),
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "document_failures"
            ),
        ):
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            with self.subTest(validator=name):
                self.assertEqual(checker_source.count(wrapper), 1)

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        gate_validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_default_gate_failures
        )
        self.assertEqual(gate_validator(gate_text=gate_source), [])
        for selector_name in (
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "result_and_sources_are_bound"
            ),
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "documents_are_bound"
            ),
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "validators_are_wired_into_main"
            ),
        ):
            selector = (
                "script.test_documentation_handoff_guards."
                "DocumentationHandoffGuardTests."
                + selector_name
            )
            with self.subTest(selector=selector_name):
                self.assertEqual(gate_source.count(selector), 1)
        self.assertEqual(
            gate_source.count(
                "script/run_macos_local_dmg_uninstall_reinstall_smoke.py"
            ),
            1,
        )
        self.assertEqual(
            gate_source.count(
                "script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py"
            ),
            2,
        )
        syntax_start = gate_source.index(
            "run check_python_syntax \\\n"
        )
        syntax_end = gate_source.index(
            "run bash -n script/*.sh",
            syntax_start,
        )
        syntax_block = gate_source[syntax_start:syntax_end]
        unit_start = gate_source.index(
            "run python3 -m unittest \\\n"
            "  script/test_v1_g0_checkpoint.py \\"
        )
        unit_end = gate_source.index(
            "run git diff --check",
            unit_start,
        )
        unit_block = gate_source[unit_start:unit_end]
        runner_line = (
            "  script/run_macos_local_dmg_uninstall_reinstall_smoke.py \\\n"
        )
        test_line = (
            "  script/test_run_macos_local_dmg_uninstall_reinstall_smoke.py "
            "\\\n"
        )
        inventory_mutations = (
            (
                gate_source.replace(runner_line, "", 1)
                + "\n# "
                + runner_line
            ),
            (
                gate_source[:unit_start]
                + unit_block.replace(test_line, "", 1)
                + gate_source[unit_end:]
                + "\n# "
                + test_line
            ),
            (
                gate_source[:syntax_start]
                + "inactive_inventory() {\n"
                + syntax_block
                + "}\n"
                + gate_source[syntax_end:]
            ),
            (
                gate_source[:unit_start]
                + ": <<'AETHERLINK_INACTIVE_UNIT_INVENTORY'\n"
                + unit_block
                + "AETHERLINK_INACTIVE_UNIT_INVENTORY\n"
                + gate_source[unit_end:]
            ),
            (
                gate_source[:unit_start]
                + unit_block.replace(
                    test_line,
                    (
                        "  ; true "
                        "script/test_run_macos_local_dmg_"
                        "uninstall_reinstall_smoke.py \\\n"
                    ),
                    1,
                )
                + gate_source[unit_end:]
            ),
            (
                gate_source[:syntax_start]
                + "if false; then\n"
                + syntax_block
                + "fi\n"
                + gate_source[syntax_end:]
            ),
            (
                gate_source[:syntax_start]
                + "exit 0\n"
                + gate_source[syntax_start:]
            ),
            (
                gate_source[:syntax_start]
                + "false\n"
                + gate_source[syntax_start:]
            ),
            (
                gate_source[:syntax_start]
                + "exec true\n"
                + gate_source[syntax_start:]
            ),
            (
                gate_source[:syntax_start]
                + "run false\n"
                + gate_source[syntax_start:]
            ),
            (
                gate_source[:syntax_start]
                + "command false\n"
                + gate_source[syntax_start:]
            ),
        )
        for ordinal, mutation in enumerate(
            inventory_mutations,
            start=1,
        ):
            with self.subTest(inventory_mutation=ordinal):
                self.assertTrue(gate_validator(gate_text=mutation))

    def test_current_build24_local_dmg_uninstall_reinstall_state_recovery_result_and_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_evidence_failures
        )
        self.assertEqual(validator(), [])
        result_path = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RESULT
        )
        baseline = json.loads(result_path.read_text(encoding="utf-8"))
        mutations: list[dict[str, object]] = []

        for path, value in (
            (("schemaVersion",), True),
            (("installation", "installCount"), True),
            (("installation", "installCount"), 2.0),
            (("mount", "cycleCount"), True),
            (("stateRecovery", "databaseCount"), True),
            (("stateRecovery", "totalEventCount"), True),
            (
                ("stateRecovery", "legacyRemovedByHarnessBeforeReinstall"),
                False,
            ),
            (
                (
                    "stateRecovery",
                    "sqliteReadbackSQLite",
                    "totalEventCount",
                ),
                2,
            ),
            (
                (
                    "stateRecovery",
                    "migrationSQLite",
                    "eventJsonSha256",
                ),
                "0" * 64,
            ),
            (("installation", "origin"), "extracted-archive"),
        ):
            mutation = copy.deepcopy(baseline)
            target: object = mutation
            for key in path[:-1]:
                target = target[key]  # type: ignore[index]
            target[path[-1]] = value  # type: ignore[index]
            mutations.append(mutation)

        reversed_runs = copy.deepcopy(baseline)
        reversed_runs["launchServices"]["runs"].reverse()
        mutations.append(reversed_runs)
        missing_key = copy.deepcopy(baseline)
        missing_key["stateRecovery"].pop("legacyAbsentBeforeReinstallReadback")
        mutations.append(missing_key)
        extra_key = copy.deepcopy(baseline)
        extra_key["unexpected"] = True
        mutations.append(extra_key)

        antecedents = (
            patch.object(
                check_docs_hygiene,
                (
                    "current_build24_macos_local_dmg_uninstall_reinstall_"
                    "evidence_failures"
                ),
                return_value=[],
            ),
            patch.object(
                check_docs_hygiene,
                (
                    "current_build24_macos_clean_home_installed_state_"
                    "recovery_evidence_failures"
                ),
                return_value=[],
            ),
        )
        with (
            antecedents[0] as uninstall_predecessor,
            antecedents[1] as state_predecessor,
        ):
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    payload = (
                        json.dumps(
                            mutation,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("ascii")
                    failures = validator(result_bytes=payload)
                    self.assertTrue(
                        any("expected identity" in row for row in failures)
                    )
                    self.assertTrue(
                        any("exact closed" in row for row in failures)
                    )

            baseline_bytes = result_path.read_bytes()
            duplicate = baseline_bytes.replace(
                b'"schemaVersion":1',
                b'"schemaVersion":1,"schemaVersion":1',
                1,
            )
            for label, payload in (
                ("duplicate", duplicate),
                ("malformed", b"{"),
                ("noncanonical", b" " + baseline_bytes),
            ):
                with self.subTest(payload=label):
                    failures = validator(result_bytes=payload)
                    self.assertTrue(failures)
        self.assertGreater(uninstall_predecessor.call_count, 0)
        self.assertGreater(state_predecessor.call_count, 0)

        expected_sources = {
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RUNNER
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_TEST
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER
            ),
            (
                check_docs_hygiene
                .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER
            ),
            check_docs_hygiene.MACOS_PACKAGED_STATE_RECOVERY_RUNNER,
            check_docs_hygiene.CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER
            ),
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
        }
        source_bytes = {
            path: path.read_bytes()
            for path in expected_sources
        }
        with (
            patch.object(
                check_docs_hygiene,
                (
                    "current_build24_macos_local_dmg_uninstall_reinstall_"
                    "evidence_failures"
                ),
                return_value=[],
            ),
            patch.object(
                check_docs_hygiene,
                (
                    "current_build24_macos_clean_home_installed_state_"
                    "recovery_evidence_failures"
                ),
                return_value=[],
            ),
        ):
            for path in expected_sources:
                with self.subTest(source=path.name, mutation="bytes"):
                    mutated = dict(source_bytes)
                    mutated[path] += b"\n"
                    failures = validator(source_bytes_by_path=mutated)
                    self.assertTrue(
                        any(
                            str(path.relative_to(check_docs_hygiene.ROOT))
                            in row
                            and "source SHA-256" in row
                            for row in failures
                        )
                    )
                with self.subTest(source=path.name, mutation="missing"):
                    mutated = dict(source_bytes)
                    mutated.pop(path)
                    failures = validator(source_bytes_by_path=mutated)
                    self.assertTrue(
                        any(
                            "exactly the nine bound source files" in row
                            for row in failures
                        )
                    )
                    self.assertTrue(
                        any(
                            str(path.relative_to(check_docs_hygiene.ROOT))
                            in row
                            and "cannot read" in row
                            for row in failures
                        )
                    )

            non_bytes = dict(source_bytes)
            first_path = next(iter(expected_sources))
            non_bytes[first_path] = "not-bytes"  # type: ignore[assignment]
            self.assertTrue(
                validator(source_bytes_by_path=non_bytes)
            )

    def test_current_build24_local_dmg_uninstall_reinstall_state_recovery_documents_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_uninstall_reinstall_state_recovery_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_DOCUMENT_BODY
        )
        complete_block = (
            start_marker
            + "\n"
            + expected_body
            + "\n"
            + end_marker
        )
        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end].strip(), expected_body)
                self.assertEqual(text.count(complete_block), 1)

                mutated_body = expected_body.replace(
                    "same canonical 4,996-byte",
                    "a 4,996-byte",
                    1,
                )
                mutated = (
                    text[:start]
                    + "\n"
                    + mutated_body
                    + "\n"
                    + text[end:]
                )
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "canonical document location" in row
                        for row in failures
                    )
                )

        readme = check_docs_hygiene.README_PATH.read_text(
            encoding="utf-8"
        )
        for mutation in (
            readme.replace(start_marker, "", 1),
            readme.replace(end_marker, "", 1),
            readme + f"\n{complete_block}\n",
            readme.replace(
                complete_block,
                start_marker + "\n" + end_marker,
                1,
            ),
            readme.replace(
                complete_block,
                "<details>\n"
                + complete_block
                + "\n</details>",
                1,
            ),
        ):
            with self.subTest(marker_mutation=hash(mutation)):
                failures = validator(
                    document_text_by_relative={"README.md": mutation}
                )
                self.assertTrue(
                    any(
                        "README.md" in row
                        and "state-recovery lifecycle" in row
                        for row in failures
                    )
                )

        for label, old, new in (
            (
                "result path",
                (
                    "macos-packaged-app-build-24-local-dmg-"
                    "uninstall-reinstall-state-recovery-v1.json"
                ),
                (
                    "macos-packaged-app-build-24-local-dmg-"
                    "uninstall-reinstall-state-recovery-v2.json"
                ),
            ),
            ("size", "4,996-byte", "4,997-byte"),
            (
                "result sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RESULT_SHA256
                ),
                "0" * 64,
            ),
            (
                "runner sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
                ),
                "1" * 64,
            ),
            (
                "test sha",
                (
                    check_docs_hygiene
                    .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_EXPECTED_TEST_SHA256
                ),
                "2" * 64,
            ),
            (
                "boundary",
                "It proves only the fixed non-empty canary",
                "It proves arbitrary non-empty histories",
            ),
        ):
            with self.subTest(body_mutation=label):
                mutated = readme.replace(old, new, 1)
                failures = validator(
                    document_text_by_relative={"README.md": mutated}
                )
                self.assertTrue(
                    any(
                        "README.md" in row
                        and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

    def test_current_build24_local_dmg_uninstall_reinstall_state_recovery_validators_are_wired_into_main(
        self,
    ) -> None:
        required_calls = (
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "state_recovery_evidence_failures"
            ),
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "state_recovery_document_failures"
            ),
        )
        checker_source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            _reachable_main_extend_counts(checker_source, required_calls),
            {name: 1 for name in required_calls},
        )
        for name in required_calls:
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            with self.subTest(validator=name):
                self.assertEqual(checker_source.count(wrapper), 1)
                mutations = (
                    checker_source.replace(
                        wrapper,
                        f"    {name}()",
                        1,
                    ),
                    checker_source.replace(
                        wrapper,
                        (
                            "    if False:\n"
                            "        failures.extend(\n"
                            f"            {name}()\n"
                            "        )"
                        ),
                        1,
                    ),
                    checker_source.replace(
                        wrapper,
                        "    return 0\n" + wrapper,
                        1,
                    ),
                    checker_source.replace(
                        wrapper,
                        (
                            "    try:\n"
                            "        return 0\n"
                            "    finally:\n"
                            "        pass\n"
                            + wrapper
                        ),
                        1,
                    ),
                )
                for mutation in mutations:
                    self.assertEqual(
                        _reachable_main_extend_counts(
                            mutation,
                            required_calls,
                        )[name],
                        0,
                    )

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        gate_validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_default_gate_failures
        )
        self.assertEqual(gate_validator(gate_text=gate_source), [])
        selector_prefix = (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
        )
        for name in (
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "state_recovery_result_and_sources_are_bound"
            ),
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "state_recovery_documents_are_bound"
            ),
            (
                "test_current_build24_local_dmg_uninstall_reinstall_"
                "state_recovery_validators_are_wired_into_main"
            ),
        ):
            self.assertEqual(gate_source.count(selector_prefix + name), 1)

        runner_path = (
            "script/run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke.py"
        )
        test_path = (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "state_recovery_smoke.py"
        )
        self.assertEqual(gate_source.count(runner_path), 1)
        self.assertEqual(gate_source.count(test_path), 2)
        syntax_start = gate_source.index(
            "run check_python_syntax \\\n"
        )
        syntax_end = gate_source.index(
            "run bash -n script/*.sh",
            syntax_start,
        )
        unit_start = gate_source.index(
            "run python3 -m unittest \\\n"
            "  script/test_v1_g0_checkpoint.py \\"
        )
        unit_end = gate_source.index(
            "run git diff --check",
            unit_start,
        )
        syntax_block = gate_source[syntax_start:syntax_end]
        unit_block = gate_source[unit_start:unit_end]
        runner_line = f"  {runner_path} \\\n"
        test_line = f"  {test_path} \\\n"
        mutations = (
            gate_source.replace(runner_line, "", 1)
            + "\n# "
            + runner_line,
            (
                gate_source[:unit_start]
                + unit_block.replace(test_line, "", 1)
                + gate_source[unit_end:]
                + "\n# "
                + test_line
            ),
            (
                gate_source[:syntax_start]
                + "inactive_inventory() {\n"
                + syntax_block
                + "}\n"
                + gate_source[syntax_end:]
            ),
            (
                gate_source[:unit_start]
                + ": <<'AETHERLINK_INACTIVE_STATE_RECOVERY'\n"
                + unit_block
                + "AETHERLINK_INACTIVE_STATE_RECOVERY\n"
                + gate_source[unit_end:]
            ),
            (
                gate_source[:unit_start]
                + unit_block.replace(
                    test_line,
                    f"  ; true {test_path} \\\n",
                    1,
                )
                + gate_source[unit_end:]
            ),
            (
                gate_source[:syntax_start]
                + "if false; then\n"
                + syntax_block
                + "fi\n"
                + gate_source[syntax_end:]
            ),
            (
                gate_source[:syntax_start]
                + "exit 0\n"
                + gate_source[syntax_start:]
            ),
        )
        for ordinal, mutation in enumerate(mutations, start=1):
            with self.subTest(inventory_mutation=ordinal):
                self.assertTrue(gate_validator(gate_text=mutation))

    def test_current_build24_local_dmg_abrupt_process_state_recovery_result_receipt_and_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_abrupt_process_state_recovery_evidence_failures
        )
        self.assertEqual(validator(), [])
        result_path = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RESULT
        )
        receipt_path = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RECEIPT
        )

        def canonical_bytes(value: object) -> bytes:
            return (
                json.dumps(
                    value,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("ascii")

        result = json.loads(result_path.read_text(encoding="utf-8"))
        result_mutations: list[dict[str, object]] = []
        for path, value in (
            (("schemaVersion",), True),
            (("abruptTermination", "signalNumber"), True),
            (("abruptTermination", "inFlightWriteCheckpointObserved"), True),
            (("abruptTermination", "processReaped"), False),
            (("stateRecovery", "databaseCount"), True),
            (("stateRecovery", "totalEventCount"), 2),
            (
                (
                    "launches",
                    "runs",
                    1,
                    "exactExecutableIdentityMatchedImmediatelyBeforeSignal",
                ),
                False,
            ),
        ):
            mutation = copy.deepcopy(result)
            target: object = mutation
            for key in path[:-1]:
                target = target[key]  # type: ignore[index]
            target[path[-1]] = value  # type: ignore[index]
            result_mutations.append(mutation)
        missing_result_key = copy.deepcopy(result)
        missing_result_key["abruptTermination"].pop("signal")
        result_mutations.append(missing_result_key)
        extra_result_key = copy.deepcopy(result)
        extra_result_key["unexpected"] = True
        result_mutations.append(extra_result_key)

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_mutations: list[dict[str, object]] = []
        for path, value in (
            (("schemaVersion",), True),
            (("runCount",), True),
            (("resultBytesEqual",), False),
            (("canonicalResult", "size"), 7_201),
            (("runs", 1, "ordinal"), 1),
        ):
            mutation = copy.deepcopy(receipt)
            target = mutation
            for key in path[:-1]:
                target = target[key]  # type: ignore[index]
            target[path[-1]] = value  # type: ignore[index]
            receipt_mutations.append(mutation)
        extra_receipt_key = copy.deepcopy(receipt)
        extra_receipt_key["unexpected"] = True
        receipt_mutations.append(extra_receipt_key)

        with patch.object(
            check_docs_hygiene,
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "state_recovery_evidence_failures"
            ),
            return_value=[],
        ) as predecessor:
            for mutation in result_mutations:
                with self.subTest(result_mutation=mutation):
                    failures = validator(
                        result_bytes=canonical_bytes(mutation),
                    )
                    self.assertTrue(
                        any("expected identity" in row for row in failures)
                    )
                    self.assertTrue(
                        any("exact closed" in row for row in failures)
                    )
            for mutation in receipt_mutations:
                with self.subTest(receipt_mutation=mutation):
                    failures = validator(
                        receipt_bytes=canonical_bytes(mutation),
                    )
                    self.assertTrue(
                        any("expected identity" in row for row in failures)
                    )
                    self.assertTrue(
                        any("exact closed" in row for row in failures)
                    )
            for label, payload in (
                ("duplicate", result_path.read_bytes().replace(
                    b'"schemaVersion":1',
                    b'"schemaVersion":1,"schemaVersion":1',
                    1,
                )),
                ("malformed", b"{"),
                ("noncanonical", b" " + result_path.read_bytes()),
            ):
                with self.subTest(result_payload=label):
                    self.assertTrue(validator(result_bytes=payload))
        self.assertGreater(predecessor.call_count, 0)

        expected_sources = {
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_RUNNER
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_TEST
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_STATE_RECOVERY_RUNNER
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LOCAL_DMG_UNINSTALL_REINSTALL_RUNNER
            ),
            (
                check_docs_hygiene
                .MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER
            ),
            check_docs_hygiene.MACOS_PACKAGED_STATE_RECOVERY_RUNNER,
            check_docs_hygiene.CURRENT_BUILD24_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            check_docs_hygiene.CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UNINSTALL_REINSTALL_RUNNER
            ),
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER,
        }
        source_bytes = {
            path: path.read_bytes()
            for path in expected_sources
        }
        with patch.object(
            check_docs_hygiene,
            (
                "current_build24_macos_local_dmg_uninstall_reinstall_"
                "state_recovery_evidence_failures"
            ),
            return_value=[],
        ):
            for path in expected_sources:
                with self.subTest(source=path.name):
                    mutated = dict(source_bytes)
                    mutated[path] += b"\n"
                    failures = validator(source_bytes_by_path=mutated)
                    self.assertTrue(
                        any(
                            str(path.relative_to(check_docs_hygiene.ROOT))
                            in row
                            and "source SHA-256" in row
                            for row in failures
                        )
                    )
            missing = dict(source_bytes)
            missing.pop(next(iter(expected_sources)))
            self.assertTrue(
                any(
                    "exactly the ten bound source files" in row
                    for row in validator(source_bytes_by_path=missing)
                )
            )

    def test_current_build24_local_dmg_abrupt_process_state_recovery_documents_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_abrupt_process_state_recovery_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LOCAL_DMG_ABRUPT_PROCESS_STATE_RECOVERY_DOCUMENT_BODY
        )
        complete_block = (
            start_marker
            + "\n"
            + expected_body
            + "\n"
            + end_marker
        )
        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end].strip(), expected_body)
                self.assertEqual(text.count(complete_block), 1)

                mutated = text.replace(
                    "same canonical 7,200-byte",
                    "a 7,200-byte",
                    1,
                )
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "canonical document location" in row
                        for row in failures
                    )
                )

        readme = check_docs_hygiene.README_PATH.read_text(encoding="utf-8")
        for mutation in (
            readme.replace(start_marker, "", 1),
            readme.replace(end_marker, "", 1),
            readme + f"\n{complete_block}\n",
            readme.replace(
                complete_block,
                "<details>\n" + complete_block + "\n</details>",
                1,
            ),
        ):
            with self.subTest(marker_mutation=hash(mutation)):
                failures = validator(
                    document_text_by_relative={"README.md": mutation}
                )
                self.assertTrue(
                    any(
                        "README.md" in row
                        and "abrupt-process state-recovery" in row
                        for row in failures
                    )
                )

    def test_current_build24_local_dmg_abrupt_process_state_recovery_validators_are_wired_into_main(
        self,
    ) -> None:
        required_calls = (
            (
                "current_build24_macos_local_dmg_abrupt_process_"
                "state_recovery_evidence_failures"
            ),
            (
                "current_build24_macos_local_dmg_abrupt_process_"
                "state_recovery_document_failures"
            ),
        )
        checker_source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            _reachable_main_extend_counts(checker_source, required_calls),
            {name: 1 for name in required_calls},
        )
        for name in required_calls:
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            self.assertEqual(checker_source.count(wrapper), 1)

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        gate_validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_default_gate_failures
        )
        self.assertEqual(gate_validator(gate_text=gate_source), [])
        selector_prefix = (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
        )
        selector_names = (
            (
                "test_current_build24_local_dmg_abrupt_process_"
                "state_recovery_result_receipt_and_sources_are_bound"
            ),
            (
                "test_current_build24_local_dmg_abrupt_process_"
                "state_recovery_documents_are_bound"
            ),
            (
                "test_current_build24_local_dmg_abrupt_process_"
                "state_recovery_validators_are_wired_into_main"
            ),
        )
        for name in selector_names:
            self.assertEqual(gate_source.count(selector_prefix + name), 1)

        runner_path = (
            "script/run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        )
        test_path = (
            "script/test_run_macos_local_dmg_uninstall_reinstall_"
            "abrupt_process_state_recovery_smoke.py"
        )
        self.assertEqual(gate_source.count(runner_path), 1)
        self.assertEqual(gate_source.count(test_path), 2)
        for line in (
            f"  {runner_path} \\\n",
            f"  {test_path} \\\n",
            f"  {selector_prefix}{selector_names[0]} \\\n",
        ):
            with self.subTest(removed=line):
                self.assertTrue(
                    gate_validator(
                        gate_text=gate_source.replace(line, "", 1)
                    )
                )

    def test_current_build24_macos_lifecycle_aggregate_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_lifecycle_aggregate_evidence_failures
        )
        self.assertEqual(validator(), [])
        expected = {
            check_docs_hygiene.CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_CHECKER: (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_CHECKER_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_CHECKER_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_TEST: (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_TEST_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_EXPECTED_TEST_SHA256,
            ),
        }
        source_bytes = {path: path.read_bytes() for path in expected}
        for path, (expected_size, expected_sha256) in expected.items():
            with self.subTest(path=path.name):
                payload = source_bytes[path]
                self.assertEqual(len(payload), expected_size)
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(),
                    expected_sha256,
                )
                mutated = dict(source_bytes)
                mutated[path] += b"\n"
                failures = validator(source_bytes_by_path=mutated)
                self.assertTrue(
                    any(
                        str(path.relative_to(check_docs_hygiene.ROOT)) in row
                        and "expected current Build 24 lifecycle aggregate"
                        in row
                        for row in failures
                    )
                )

        missing = dict(source_bytes)
        missing.pop(next(iter(expected)))
        self.assertTrue(
            any(
                "exactly the checker and test files" in row
                for row in validator(source_bytes_by_path=missing)
            )
        )
        extra = dict(source_bytes)
        extra[check_docs_hygiene.ROOT / "unexpected.py"] = b""
        self.assertTrue(
            any(
                "exactly the checker and test files" in row
                for row in validator(source_bytes_by_path=extra)
            )
        )
        non_bytes = dict(source_bytes)
        first_path = next(iter(expected))
        non_bytes[first_path] = bytearray(non_bytes[first_path])  # type: ignore[assignment]
        self.assertTrue(
            any(
                "injected source payload must be bytes" in row
                for row in validator(source_bytes_by_path=non_bytes)
            )
        )

        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            target = temporary_root / "checker.py"
            link = temporary_root / "checker-link.py"
            target.write_bytes(source_bytes[
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_CHECKER
            ])
            link.symlink_to(target)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_CHECKER",
                link,
            ):
                failures = validator()
            self.assertTrue(
                any(
                    "non-symlink regular file" in row
                    for row in failures
                )
            )

    def test_current_build24_macos_lifecycle_aggregate_documents_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_lifecycle_aggregate_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_LIFECYCLE_AGGREGATE_DOCUMENT_BODY
        )
        complete_block = (
            start_marker + "\n" + expected_body + "\n" + end_marker
        )
        for relative in targets:
            with self.subTest(relative=relative):
                text = (
                    check_docs_hygiene.ROOT / relative
                ).read_text(encoding="utf-8")
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end].strip(), expected_body)
                self.assertEqual(text.count(complete_block), 1)

                mutated = text.replace(
                    "standalone\nread-only command",
                    "standalone local\nread-only command",
                    1,
                )
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "canonical document location" in row
                        for row in failures
                    )
                )

        readme = check_docs_hygiene.README_PATH.read_text(encoding="utf-8")
        for mutation in (
            readme.replace(start_marker, "", 1),
            readme.replace(end_marker, "", 1),
            readme + f"\n{complete_block}\n",
            readme.replace(
                complete_block,
                "<details>\n" + complete_block + "\n</details>",
                1,
            ),
        ):
            with self.subTest(marker_mutation=hash(mutation)):
                failures = validator(
                    document_text_by_relative={"README.md": mutation}
                )
                self.assertTrue(
                    any(
                        "README.md" in row
                        and "lifecycle aggregate readback" in row
                        for row in failures
                    )
                )

    def test_current_build24_macos_lifecycle_aggregate_validators_are_wired_into_main(
        self,
    ) -> None:
        required_calls = (
            "current_build24_macos_lifecycle_aggregate_evidence_failures",
            "current_build24_macos_lifecycle_aggregate_document_failures",
        )
        checker_source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            _reachable_main_extend_counts(checker_source, required_calls),
            {name: 1 for name in required_calls},
        )
        for name in required_calls:
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            self.assertEqual(checker_source.count(wrapper), 1)

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        gate_validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_default_gate_failures
        )
        self.assertEqual(gate_validator(gate_text=gate_source), [])
        checker_path = "script/check_macos_build24_lifecycle_evidence.py"
        test_path = "script/test_check_macos_build24_lifecycle_evidence.py"
        direct_invocation = (
            "run python3 -I -B -S "
            "script/check_macos_build24_lifecycle_evidence.py"
        )
        self.assertEqual(gate_source.count(checker_path), 2)
        self.assertEqual(gate_source.count(test_path), 2)
        self.assertEqual(gate_source.count(direct_invocation), 1)

        selector_prefix = (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
        )
        selector_names = (
            "test_current_build24_macos_lifecycle_aggregate_sources_are_bound",
            (
                "test_current_build24_macos_lifecycle_aggregate_"
                "documents_are_bound"
            ),
            (
                "test_current_build24_macos_lifecycle_aggregate_"
                "validators_are_wired_into_main"
            ),
        )
        for name in selector_names:
            self.assertEqual(gate_source.count(selector_prefix + name), 1)

        for line in (
            direct_invocation + "\n",
            f"  {checker_path} \\\n",
            f"  {test_path} \\\n",
            f"  {selector_prefix}{selector_names[0]} \\\n",
        ):
            with self.subTest(removed=line):
                self.assertTrue(
                    gate_validator(
                        gate_text=gate_source.replace(line, "", 1)
                    )
                )

    def test_current_build24_macos_current_unsealed_install_recovery_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_current_unsealed_install_recovery_source_failures
        )
        self.assertEqual(validator(), [])
        expected = {
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_RESULT: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RESULT_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RESULT_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_RECEIPT: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RECEIPT_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RECEIPT_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_RUNNER: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RUNNER_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RUNNER_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_RUNNER_TEST: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RUNNER_TEST_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_RUNNER_TEST_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_CHECKER: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_CHECKER_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_CHECKER_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_CHECKER_TEST: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_CHECKER_TEST_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_EXPECTED_CHECKER_TEST_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_CI_LIFECYCLE_CHECKER: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_CI_LIFECYCLE_EXPECTED_CHECKER_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_CI_LIFECYCLE_EXPECTED_CHECKER_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_CI_LIFECYCLE_CHECKER_TEST: (
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_CI_LIFECYCLE_EXPECTED_CHECKER_TEST_SIZE,
                check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_CI_LIFECYCLE_EXPECTED_CHECKER_TEST_SHA256,
            ),
        }
        source_bytes = {path: path.read_bytes() for path in expected}
        for path, (expected_size, expected_sha256) in expected.items():
            payload = source_bytes[path]
            relative = str(path.relative_to(check_docs_hygiene.ROOT))
            with self.subTest(path=relative):
                self.assertEqual(len(payload), expected_size)
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(), expected_sha256
                )
                mutated = dict(source_bytes)
                mutated[path] = payload + b"\n"
                failures = validator(source_bytes_by_path=mutated)
                self.assertTrue(
                    any(
                        relative in row
                        and "expected current Build 24 current-unsealed" in row
                        for row in failures
                    )
                )

                missing = dict(source_bytes)
                missing.pop(path)
                failures = validator(source_bytes_by_path=missing)
                self.assertTrue(
                    any(
                        "must contain exactly the result, repeatability "
                        "receipt, runner, runner test, checker, checker test, "
                        "CI lifecycle checker, and CI lifecycle checker test "
                        "files" in row
                        for row in failures
                    )
                )

        extra = dict(source_bytes)
        extra[check_docs_hygiene.ROOT / "unexpected.py"] = b""
        self.assertTrue(
            any(
                "must contain exactly the result, repeatability receipt" in row
                for row in validator(source_bytes_by_path=extra)
            )
        )
        non_bytes = dict(source_bytes)
        first_path = next(iter(expected))
        non_bytes[first_path] = bytearray(  # type: ignore[assignment]
            non_bytes[first_path]
        )
        self.assertTrue(
            any(
                "injected source payload must be bytes" in row
                for row in validator(source_bytes_by_path=non_bytes)
            )
        )

        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            target = temporary_root / "result.json"
            link = temporary_root / "result-link.json"
            target.write_bytes(
                source_bytes[
                    check_docs_hygiene.CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_RESULT
                ]
            )
            link.symlink_to(target)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_RESULT",
                link,
            ):
                failures = validator()
            self.assertTrue(
                any("non-symlink regular file" in row for row in failures)
            )

    def test_current_build24_macos_current_unsealed_install_recovery_documents_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_current_unsealed_install_recovery_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        heading_by_relative = {
            "docs/progress.md": (
                "## 2026-08-02 macOS Current-Source Unsealed Build 24 "
                "Clean-HOME Install And State Recovery"
            ),
            "docs/qa-evidence.md": (
                "## 2026-08-02 macOS Current-Source Unsealed Build 24 "
                "Clean-HOME Install And State Recovery Checklist"
            ),
            "docs/releases/1.0.0-build-24-local-v1.md": (
                "## Current-Source Unsealed Build 24 Clean-HOME Install "
                "And State-Recovery Evidence"
            ),
        }
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_CURRENT_UNSEALED_INSTALL_RECOVERY_DOCUMENT_BODY
        )
        complete_block = start_marker + "\n" + expected_body + "\n" + end_marker
        self.assertEqual(len(expected_body.encode("utf-8")), 8_598)
        self.assertEqual(
            hashlib.sha256(expected_body.encode("utf-8")).hexdigest(),
            "d88711bcdddd676cbb858026f30848db2c6233a1fc524c3e054ae2d98f9845ec",
        )

        for relative in targets:
            text = (check_docs_hygiene.ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end], "\n" + expected_body + "\n")
                self.assertEqual(text.count(complete_block), 1)

                mutated_block = complete_block.replace(
                    "for six\nlaunches total",
                    "for exactly six\nlaunches total",
                    1,
                )
                self.assertNotEqual(mutated_block, complete_block)
                mutated = text.replace(complete_block, mutated_block, 1)
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in row and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                self.assertTrue(
                    validator(document_text_by_relative={relative: relocated})
                )
                self.assertTrue(
                    chain_validator(document_text_by_relative={relative: relocated})
                )

                hidden = text.replace(
                    complete_block,
                    "<details>\n" + complete_block + "\n</details>",
                    1,
                )
                self.assertTrue(
                    any(
                        "hidden Markdown or HTML" in row
                        for row in validator(
                            document_text_by_relative={relative: hidden}
                        )
                    )
                )

                for marker in (start_marker, end_marker):
                    missing_marker = text.replace(marker, "", 1)
                    self.assertTrue(
                        any(
                            "exactly one start and end marker" in row
                            for row in validator(
                                document_text_by_relative={
                                    relative: missing_marker
                                }
                            )
                        )
                    )

                duplicated = text + "\n" + complete_block + "\n"
                self.assertTrue(
                    any(
                        "exactly one start and end marker" in row
                        for row in validator(
                            document_text_by_relative={relative: duplicated}
                        )
                    )
                )

                heading = heading_by_relative.get(relative)
                if heading is not None:
                    mutated_heading = text.replace(
                        heading, heading + " Changed", 1
                    )
                    self.assertTrue(
                        any(
                            "canonical document location" in row
                            for row in validator(
                                document_text_by_relative={
                                    relative: mutated_heading
                                }
                            )
                        )
                    )

    def test_current_build24_macos_current_unsealed_install_recovery_validators_are_wired_into_main(
        self,
    ) -> None:
        full_source = (
            "current_build24_macos_current_unsealed_install_"
            "recovery_source_failures"
        )
        tracked_source = (
            "current_build24_macos_current_unsealed_install_"
            "recovery_tracked_source_failures"
        )
        document = (
            "current_build24_macos_current_unsealed_install_"
            "recovery_document_failures"
        )
        checker_source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            _reachable_main_extend_counts(checker_source, (full_source, document)),
            {full_source: 1, document: 1},
        )
        self.assertEqual(checker_source.count(tracked_source + "()"), 1)
        self.assertEqual(
            check_docs_hygiene
            .current_build24_macos_current_unsealed_install_recovery_tracked_source_failures(),
            [],
        )

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        runner_path = "script/run_macos_current_unsealed_install_recovery_smoke.py"
        runner_test_path = (
            "script/test_run_macos_current_unsealed_install_recovery_smoke.py"
        )
        checker_path = (
            "script/check_macos_current_unsealed_install_recovery_evidence.py"
        )
        checker_test_path = (
            "script/test_check_macos_current_unsealed_install_recovery_evidence.py"
        )
        current_run_checker_path = (
            "script/check_macos_current_unsealed_ci_lifecycle.py"
        )
        current_run_checker_test_path = (
            "script/test_check_macos_current_unsealed_ci_lifecycle.py"
        )
        portable_checker_selector = (
            "script.test_check_macos_current_unsealed_install_recovery_"
            "evidence.CurrentUnsealedRecoveryEvidencePortableTests"
        )
        syntax_inventory = (
            gate_source.index("run check_python_syntax \\\n"),
            gate_source.index("\n\nrun bash -n script/*.sh"),
        )
        unit_inventory = (
            gate_source.index("run python3 -m unittest \\\n"),
            gate_source.index("\nrun git diff --check"),
        )
        self.assertEqual(gate_source.count(runner_path), 1)
        self.assertEqual(gate_source.count(runner_test_path), 2)
        self.assertEqual(gate_source.count(checker_path), 1)
        self.assertEqual(gate_source.count(checker_test_path), 1)
        self.assertEqual(gate_source.count(current_run_checker_path), 1)
        self.assertEqual(gate_source.count(current_run_checker_test_path), 2)
        self.assertEqual(gate_source.count(portable_checker_selector), 1)
        self.assertEqual(
            check_docs_hygiene.reachable_top_level_path_invocations(
                gate_source,
                (checker_path, current_run_checker_path, checker_test_path),
                module_prefixes=(
                    "script.check_macos_current_unsealed_install_recovery_"
                    "evidence",
                    "script.check_macos_current_unsealed_ci_lifecycle",
                    "script.test_check_macos_current_unsealed_install_"
                    "recovery_evidence",
                ),
                allowed_module_selectors=(portable_checker_selector,),
                allowed_command_prefixes=(("run", "check_python_syntax"),),
            ),
            [],
        )
        for path in (
            runner_path,
            runner_test_path,
            checker_path,
            checker_test_path,
            current_run_checker_path,
            current_run_checker_test_path,
        ):
            syntax_line = f"  {path} \\\n"
            positions = [
                match.start()
                for match in re.finditer(re.escape(syntax_line), gate_source)
            ]
            self.assertEqual(
                sum(
                    syntax_inventory[0] <= position < syntax_inventory[1]
                    for position in positions
                ),
                1,
            )
        for path in (runner_test_path, current_run_checker_test_path):
            unit_line = f"  {path} \\\n"
            positions = [
                match.start()
                for match in re.finditer(re.escape(unit_line), gate_source)
            ]
            self.assertEqual(len(positions), 2)
            self.assertEqual(
                sum(
                    unit_inventory[0] <= position < unit_inventory[1]
                    for position in positions
                ),
                1,
            )
        portable_position = gate_source.index(portable_checker_selector)
        self.assertGreaterEqual(portable_position, unit_inventory[0])
        self.assertLess(portable_position, unit_inventory[1])
        historical_comment = (
            "# The exact closure-five checker is historical: its ignored "
            "evidence names and\n"
            "# fixed dist/unsealed-package-only path belong to one "
            "superseded generation.\n"
        )
        self.assertEqual(gate_source.count(historical_comment), 1)
        forbidden_variants = (
            "run python3 ./" + checker_path,
            "run /usr/bin/python3 -B ./" + current_run_checker_path,
            "run python3 " + str(check_docs_hygiene.ROOT / checker_path),
            "run python3 script//check_macos_current_unsealed_install_"
            "recovery_evidence.py",
            (
                "run python3 -m unittest "
                "script.test_check_macos_current_unsealed_install_recovery_"
                "evidence"
            ),
            (
                "run python3 -m "
                "script.check_macos_current_unsealed_ci_lifecycle"
            ),
            "run python3 \\\n  " + checker_path,
            (
                "run python3 -m unittest \\\n  "
                "script.test_check_macos_current_unsealed_install_recovery_"
                "evidence"
            ),
            "run python3 ../project/" + checker_path,
            "run python3 -m unittest ./" + checker_test_path,
            "cd script && run python3 " + Path(checker_path).name,
            (
                "run check_python_syntax script//"
                + Path(checker_path).name
                + ";run python3 script//"
                + Path(checker_path).name
            ),
            (
                "run check_python_syntax script//"
                + Path(checker_path).name
                + " && run python3 script//"
                + Path(checker_path).name
            ),
            (
                "run check_python_syntax script//"
                + Path(checker_path).name
                + " || run python3 script//"
                + Path(checker_path).name
            ),
        )
        for command in forbidden_variants:
            with self.subTest(command=command):
                mutated = gate_source.rstrip() + "\n" + command + "\n"
                self.assertTrue(
                    check_docs_hygiene
                    .current_build24_macos_local_dmg_default_gate_failures(
                        gate_text=mutated
                    )
                )
                self.assertTrue(
                    check_docs_hygiene.reachable_top_level_path_invocations(
                        mutated,
                        (
                            checker_path,
                            current_run_checker_path,
                            checker_test_path,
                        ),
                        module_prefixes=(
                            "script.check_macos_current_unsealed_install_"
                            "recovery_evidence",
                            "script.check_macos_current_unsealed_ci_lifecycle",
                            "script.test_check_macos_current_unsealed_install_"
                            "recovery_evidence",
                        ),
                        allowed_module_selectors=(portable_checker_selector,),
                        allowed_command_prefixes=(
                            ("run", "check_python_syntax"),
                        ),
                    )
                )
        syntax_invocation_start = "run check_python_syntax \\\n"
        indirect_mutations = (
            (
                "check_python_syntax() {\n"
                "  run python3 script//"
                + Path(checker_path).name
                + "\n}\n\n"
            ),
            (
                "run() {\n"
                "  python3 script//"
                + Path(checker_path).name
                + "\n}\n\n"
            ),
            (
                "if true; then\n"
                "  run python3 script//"
                + Path(checker_path).name
                + "\nfi\n\n"
            ),
            (
                "historical_wrapper() {\n"
                "  run python3 script//"
                + Path(checker_path).name
                + "\n}\n"
                "historical_wrapper\n\n"
            ),
            (
                "run python3 -c 'import "
                "script.check_macos_current_unsealed_install_recovery_"
                "evidence'\n\n"
            ),
            (
                "historical_checker=script//"
                + Path(checker_path).name
                + "\nrun python3 \"$historical_checker\"\n\n"
            ),
            "run ()\n{\n  :\n}\n\n",
            "check_python_syntax ()\n{\n  :\n}\n\n",
        )
        for redefinition in indirect_mutations:
            with self.subTest(redefinition=redefinition.splitlines()[0]):
                mutated = gate_source.replace(
                    syntax_invocation_start,
                    redefinition + syntax_invocation_start,
                    1,
                )
                self.assertNotEqual(mutated, gate_source)
                self.assertTrue(
                    check_docs_hygiene
                    .current_build24_macos_local_dmg_default_gate_failures(
                        gate_text=mutated
                    )
                )
        selector_prefix = (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
        )
        for name in (
            "test_current_build24_macos_current_unsealed_install_recovery_sources_are_bound",
            "test_current_build24_macos_current_unsealed_install_recovery_documents_are_bound",
            "test_current_build24_macos_current_unsealed_install_recovery_validators_are_wired_into_main",
        ):
            self.assertEqual(gate_source.count(selector_prefix + name), 1)

    def test_current_build24_reverse_version_readback_result_receipt_and_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_reverse_version_readback_source_failures
        )
        self.assertEqual(validator(), [])
        expected = {
            check_docs_hygiene.CURRENT_BUILD24_REVERSE_VERSION_READBACK_RESULT: (
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RESULT_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RESULT_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_REVERSE_VERSION_READBACK_RECEIPT: (
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RECEIPT_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RECEIPT_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER: (
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_REVERSE_VERSION_READBACK_RUNNER_TEST: (
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_RUNNER_TEST_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER: (
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_SHA256,
            ),
            check_docs_hygiene.CURRENT_BUILD24_REVERSE_VERSION_READBACK_CHECKER_TEST: (
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_REVERSE_VERSION_READBACK_EXPECTED_CHECKER_TEST_SHA256,
            ),
        }
        source_bytes = {path: path.read_bytes() for path in expected}
        for path, (expected_size, expected_sha256) in expected.items():
            payload = source_bytes[path]
            relative = str(path.relative_to(check_docs_hygiene.ROOT))
            with self.subTest(path=relative):
                self.assertEqual(len(payload), expected_size)
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(),
                    expected_sha256,
                )
                mutated = dict(source_bytes)
                mutated[path] = payload + b"\n"
                failures = validator(source_bytes_by_path=mutated)
                self.assertTrue(
                    any(
                        relative in row
                        and "expected current Build 24-to-23-to-24" in row
                        for row in failures
                    )
                )

                missing = dict(source_bytes)
                missing.pop(path)
                failures = validator(source_bytes_by_path=missing)
                self.assertTrue(
                    any(
                        "must contain exactly the result, repeatability "
                        "receipt, runner, runner test, checker, and checker "
                        "test files" in row
                        for row in failures
                    )
                )

        extra = dict(source_bytes)
        extra[check_docs_hygiene.ROOT / "unexpected.py"] = b""
        self.assertTrue(
            any(
                "must contain exactly the result, repeatability receipt"
                in row
                for row in validator(source_bytes_by_path=extra)
            )
        )
        non_bytes = dict(source_bytes)
        first_path = next(iter(expected))
        non_bytes[first_path] = bytearray(  # type: ignore[assignment]
            non_bytes[first_path]
        )
        self.assertTrue(
            any(
                "injected source payload must be bytes" in row
                for row in validator(source_bytes_by_path=non_bytes)
            )
        )

        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            target = temporary_root / "result.json"
            link = temporary_root / "result-link.json"
            target.write_bytes(
                source_bytes[
                    check_docs_hygiene
                    .CURRENT_BUILD24_REVERSE_VERSION_READBACK_RESULT
                ]
            )
            link.symlink_to(target)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_BUILD24_REVERSE_VERSION_READBACK_RESULT",
                link,
            ):
                failures = validator()
            self.assertTrue(
                any(
                    "non-symlink regular file" in row
                    for row in failures
                )
            )

    def test_current_build24_reverse_version_readback_documents_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_reverse_version_readback_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        heading_by_relative = {
            "docs/progress.md": (
                "## 2026-08-02 macOS Build 24-to-23-to-24 Bounded "
                "Reverse-Version Readback"
            ),
            "docs/qa-evidence.md": (
                "## 2026-08-02 macOS Build 24-to-23-to-24 Bounded "
                "Reverse-Version Readback Checklist"
            ),
            "docs/releases/1.0.0-build-24-local-v1.md": (
                "## Post-Archive Build 24-to-23-to-24 Bounded "
                "Reverse-Version Readback Evidence"
            ),
        }
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_REVERSE_VERSION_READBACK_DOCUMENT_BODY
        )
        complete_block = (
            start_marker + "\n" + expected_body + "\n" + end_marker
        )
        self.assertEqual(len(expected_body.encode("utf-8")), 4_194)
        self.assertEqual(
            hashlib.sha256(expected_body.encode("utf-8")).hexdigest(),
            "9c7306ab38558b5672dfd3e310e8b4c82e47d03cc9abd7172949f7dca7d363d0",
        )

        for relative in targets:
            text = (
                check_docs_hygiene.ROOT / relative
            ).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(
                    text[start:end],
                    "\n" + expected_body + "\n",
                )
                self.assertEqual(text.count(complete_block), 1)

                mutated_block = complete_block.replace(
                    "fixed-canary compatibility observation",
                    "bounded fixed-canary compatibility observation",
                    1,
                )
                self.assertNotEqual(mutated_block, complete_block)
                mutated = text.replace(
                    complete_block,
                    mutated_block,
                    1,
                )
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

                extra_boundary_space = text.replace(
                    start_marker + "\n",
                    start_marker + "\n\n",
                    1,
                )
                failures = validator(
                    document_text_by_relative={
                        relative: extra_boundary_space
                    }
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "canonical document location" in row
                        for row in failures
                    )
                )
                self.assertTrue(
                    chain_validator(
                        document_text_by_relative={relative: relocated}
                    )
                )

                hidden = text.replace(
                    complete_block,
                    "<details>\n" + complete_block + "\n</details>",
                    1,
                )
                failures = validator(
                    document_text_by_relative={relative: hidden}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "hidden Markdown or HTML" in row
                        for row in failures
                    )
                )
                self.assertTrue(
                    chain_validator(
                        document_text_by_relative={relative: hidden}
                    )
                )

                for marker in (start_marker, end_marker):
                    missing_marker = text.replace(marker, "", 1)
                    failures = validator(
                        document_text_by_relative={
                            relative: missing_marker
                        }
                    )
                    self.assertTrue(
                        any(
                            relative in row
                            and "exactly one start and end marker" in row
                            for row in failures
                        )
                    )

                duplicated = text + "\n" + complete_block + "\n"
                failures = validator(
                    document_text_by_relative={relative: duplicated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "exactly one start and end marker" in row
                        for row in failures
                    )
                )

                if relative in heading_by_relative:
                    heading = heading_by_relative[relative]
                    mutated_heading = text.replace(
                        heading,
                        heading + " Changed",
                        1,
                    )
                    self.assertNotEqual(mutated_heading, text)
                    failures = validator(
                        document_text_by_relative={
                            relative: mutated_heading
                        }
                    )
                    self.assertTrue(
                        any(
                            relative in row
                            and "canonical document location" in row
                            for row in failures
                        )
                    )

    def test_current_build24_reverse_version_readback_validators_are_wired_into_main(
        self,
    ) -> None:
        required_calls = (
            "current_build24_reverse_version_readback_source_failures",
            "current_build24_reverse_version_readback_document_failures",
        )
        checker_source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            _reachable_main_extend_counts(checker_source, required_calls),
            {name: 1 for name in required_calls},
        )
        for name in required_calls:
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            self.assertEqual(checker_source.count(wrapper), 1)

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        runner_path = (
            "script/run_macos_isolated_reverse_version_readback_smoke.py"
        )
        runner_test_path = (
            "script/test_run_macos_isolated_reverse_version_readback_smoke.py"
        )
        checker_path = (
            "script/check_macos_isolated_reverse_version_readback_evidence.py"
        )
        checker_test_path = (
            "script/test_check_macos_isolated_reverse_version_readback_evidence.py"
        )
        direct_checker = (
            "run python3 -I -B -S "
            "script/check_macos_isolated_reverse_version_readback_evidence.py"
        )
        syntax_inventory = (
            gate_source.index("run check_python_syntax \\\n"),
            gate_source.index("\n\nrun bash -n script/*.sh"),
        )
        unit_inventory = (
            gate_source.index("run python3 -m unittest \\\n"),
            gate_source.index("\nrun git diff --check"),
        )

        self.assertEqual(gate_source.count(runner_path), 1)
        self.assertEqual(gate_source.count(runner_test_path), 2)
        self.assertEqual(gate_source.count(checker_path), 2)
        self.assertEqual(gate_source.count(checker_test_path), 2)
        self.assertEqual(gate_source.count(direct_checker), 1)
        for path in (
            runner_path,
            runner_test_path,
            checker_path,
            checker_test_path,
        ):
            syntax_line = f"  {path} \\\n"
            positions = [
                match.start()
                for match in re.finditer(re.escape(syntax_line), gate_source)
            ]
            self.assertEqual(
                sum(
                    syntax_inventory[0] <= position < syntax_inventory[1]
                    for position in positions
                ),
                1,
            )
        for path in (runner_test_path, checker_test_path):
            unit_line = f"  {path} \\\n"
            positions = [
                match.start()
                for match in re.finditer(re.escape(unit_line), gate_source)
            ]
            self.assertEqual(len(positions), 2)
            self.assertEqual(
                sum(
                    unit_inventory[0] <= position < unit_inventory[1]
                    for position in positions
                ),
                1,
            )
        checker_index = gate_source.index(direct_checker)
        self.assertGreater(checker_index, unit_inventory[1])
        self.assertLess(
            checker_index,
            gate_source.index("run python3 script/check_docs_hygiene.py"),
        )

    def test_current_build24_macos_idle_resource_stability_result_and_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_idle_resource_stability_evidence_failures
        )
        self.assertEqual(validator(), [])
        result_path = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RESULT
        )
        result_payload = result_path.read_bytes()
        self.assertEqual(
            len(result_payload),
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RESULT_SIZE,
        )
        self.assertEqual(
            hashlib.sha256(result_payload).hexdigest(),
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RESULT_SHA256,
        )
        expected_sources = {
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RUNNER
            ): (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_SHA256,
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RUNNER_TEST
            ): (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_TEST_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_RUNNER_TEST_SHA256,
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_CHECKER
            ): (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_SHA256,
            ),
            (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_CHECKER_TEST
            ): (
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_TEST_SIZE,
                check_docs_hygiene
                .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_EXPECTED_CHECKER_TEST_SHA256,
            ),
        }
        source_bytes = {
            path: path.read_bytes() for path in expected_sources
        }
        for path, (expected_size, expected_sha256) in (
            expected_sources.items()
        ):
            payload = source_bytes[path]
            with self.subTest(path=path.name):
                self.assertEqual(len(payload), expected_size)
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest(),
                    expected_sha256,
                )
                mutated = dict(source_bytes)
                mutated[path] = payload + b"\n"
                self.assertTrue(
                    validator(source_bytes_by_path=mutated)
                )

        missing = dict(source_bytes)
        missing.pop(next(iter(expected_sources)))
        self.assertTrue(
            any(
                "must contain exactly the runner, runner test, checker, "
                "and checker test files" in row
                for row in validator(source_bytes_by_path=missing)
            )
        )
        extra = dict(source_bytes)
        extra[check_docs_hygiene.ROOT / "unexpected.py"] = b""
        self.assertTrue(validator(source_bytes_by_path=extra))
        non_bytes = dict(source_bytes)
        first_source = next(iter(expected_sources))
        non_bytes[first_source] = bytearray(  # type: ignore[assignment]
            non_bytes[first_source]
        )
        self.assertTrue(
            any(
                "injected source payload must be bytes" in row
                for row in validator(source_bytes_by_path=non_bytes)
            )
        )

        result = json.loads(result_payload)
        result["measurement"]["run"]["summary"]["threads"][
            "finalDelta"
        ] = False
        type_mutation = (
            check_docs_hygiene.idle_resource_evidence
            .canonical_json_bytes(result)
        )
        failures = validator(
            result_bytes=type_mutation,
            source_bytes_by_path=source_bytes,
        )
        self.assertTrue(
            any(
                "invalid current Build 24 idle-resource result contract"
                in row
                for row in failures
            )
        )

        result = json.loads(result_payload)
        result["measurement"]["run"][
            "maximumObservedLatenessMilliseconds"
        ] = 78
        lateness_mutation = (
            check_docs_hygiene.idle_resource_evidence
            .canonical_json_bytes(result)
        )
        self.assertTrue(
            any(
                "maximum observed lateness differs from raw samples" in row
                for row in validator(result_bytes=lateness_mutation)
            )
        )

        with tempfile.TemporaryDirectory(
            dir=check_docs_hygiene.ROOT
        ) as temporary_directory:
            temporary_root = Path(temporary_directory)
            target = temporary_root / "result.json"
            link = temporary_root / "result-link.json"
            target.write_bytes(result_payload)
            link.symlink_to(target)
            with patch.object(
                check_docs_hygiene,
                "CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_RESULT",
                link,
            ):
                failures = validator()
            self.assertTrue(
                any(
                    "non-symlink regular file" in row
                    for row in failures
                )
            )

    def test_current_build24_macos_idle_resource_stability_documents_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_build24_macos_idle_resource_stability_document_failures
        )
        chain_validator = (
            check_docs_hygiene
            .current_build24_macos_clean_home_lifecycle_document_failures
        )
        self.assertEqual(validator(), [])
        self.assertEqual(chain_validator(), [])
        targets = (
            "README.md",
            "docs/roadmap.md",
            "docs/handoff.md",
            "docs/progress.md",
            "docs/qa-evidence.md",
            "docs/releases/1.0.0-build-24-local-v1.md",
        )
        start_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_START
        )
        end_marker = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_END
        )
        expected_body = (
            check_docs_hygiene
            .CURRENT_BUILD24_MACOS_IDLE_RESOURCE_STABILITY_DOCUMENT_BODY
        )
        complete_block = (
            start_marker + "\n" + expected_body + "\n" + end_marker
        )
        for relative in targets:
            text = (
                check_docs_hygiene.ROOT / relative
            ).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                start = text.index(start_marker) + len(start_marker)
                end = text.index(end_marker)
                self.assertEqual(text[start:end].strip(), expected_body)
                self.assertEqual(text.count(complete_block), 1)

                mutated = text.replace(
                    "maximum observed sample lateness was 79 ms",
                    "maximum observed sample lateness was 80 ms",
                    1,
                )
                failures = validator(
                    document_text_by_relative={relative: mutated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "exact canonical body SHA-256" in row
                        for row in failures
                    )
                )

                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                failures = validator(
                    document_text_by_relative={relative: relocated}
                )
                self.assertTrue(
                    any(
                        relative in row
                        and "canonical document location" in row
                        for row in failures
                    )
                )

        readme = check_docs_hygiene.README_PATH.read_text(encoding="utf-8")
        for mutation in (
            readme.replace(start_marker, "", 1),
            readme.replace(end_marker, "", 1),
            readme + f"\n{complete_block}\n",
            readme.replace(
                complete_block,
                "<details>\n" + complete_block + "\n</details>",
                1,
            ),
        ):
            with self.subTest(marker_mutation=hash(mutation)):
                failures = validator(
                    document_text_by_relative={"README.md": mutation}
                )
                self.assertTrue(
                    any(
                        "README.md" in row
                        and "idle-resource stability" in row
                        for row in failures
                    )
                )
                self.assertTrue(
                    chain_validator(
                        document_text_by_relative={"README.md": mutation}
                    )
                )

    def test_current_build24_macos_idle_resource_stability_validators_are_wired_into_main(
        self,
    ) -> None:
        required_calls = (
            (
                "current_build24_macos_idle_resource_"
                "stability_evidence_failures"
            ),
            (
                "current_build24_macos_idle_resource_"
                "stability_document_failures"
            ),
        )
        checker_source = (
            check_docs_hygiene.ROOT / "script/check_docs_hygiene.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            _reachable_main_extend_counts(checker_source, required_calls),
            {name: 1 for name in required_calls},
        )
        for name in required_calls:
            wrapper = (
                "    failures.extend(\n"
                f"        {name}()\n"
                "    )"
            )
            self.assertEqual(checker_source.count(wrapper), 1)

        gate_source = (
            check_docs_hygiene.ROOT / "script/check_no_device_quality.sh"
        ).read_text(encoding="utf-8")
        gate_validator = (
            check_docs_hygiene
            .current_build24_macos_local_dmg_default_gate_failures
        )
        self.assertEqual(gate_validator(gate_text=gate_source), [])
        runner_path = (
            "script/run_macos_build24_idle_resource_stability_smoke.py"
        )
        runner_test_path = (
            "script/test_run_macos_build24_idle_resource_stability_smoke.py"
        )
        evidence_checker_path = (
            "script/check_macos_build24_idle_resource_stability_evidence.py"
        )
        evidence_test_path = (
            "script/test_check_macos_build24_idle_resource_stability_evidence.py"
        )
        direct_checker = (
            "run python3 -I -B -S "
            "script/check_macos_build24_idle_resource_stability_evidence.py"
        )
        direct_runner = (
            "run python3 -B "
            "script/run_macos_build24_idle_resource_stability_smoke.py"
        )
        self.assertEqual(gate_source.count(runner_path), 1)
        self.assertEqual(gate_source.count(runner_test_path), 2)
        self.assertEqual(gate_source.count(evidence_checker_path), 2)
        self.assertEqual(gate_source.count(evidence_test_path), 2)
        self.assertEqual(gate_source.count(direct_checker), 1)
        self.assertEqual(gate_source.count(direct_runner), 0)
        self.assertTrue(
            any(
                "must not execute in the default gate" in row
                for row in gate_validator(
                    gate_text=gate_source + "\n" + direct_runner + "\n"
                )
            )
        )

        selector_prefix = (
            "script.test_documentation_handoff_guards."
            "DocumentationHandoffGuardTests."
        )
        selector_names = (
            (
                "test_current_build24_macos_idle_resource_stability_"
                "result_and_sources_are_bound"
            ),
            (
                "test_current_build24_macos_idle_resource_stability_"
                "documents_are_bound"
            ),
            (
                "test_current_build24_macos_idle_resource_stability_"
                "validators_are_wired_into_main"
            ),
        )
        for name in selector_names:
            self.assertEqual(gate_source.count(selector_prefix + name), 1)

        for line in (
            direct_checker + "\n",
            f"  {runner_path} \\\n",
            f"  {runner_test_path} \\\n",
            f"  {evidence_checker_path} \\\n",
            f"  {evidence_test_path} \\\n",
            f"  {selector_prefix}{selector_names[0]} \\\n",
        ):
            with self.subTest(removed=line):
                self.assertTrue(
                    gate_validator(
                        gate_text=gate_source.replace(line, "", 1)
                    )
                )

    def test_current_macos_isolated_upgrade_result_and_sources_are_bound(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_macos_isolated_upgrade_evidence_failures
        )
        self.assertEqual(validator(), [])

        result = json.loads(
            (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_RESULT
            ).read_text(encoding="utf-8")
        )
        result["stateUpgrade"]["currentRelaunchIdempotent"] = False
        mutated_result = (
            json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        result_failures = validator(result_bytes=mutated_result)
        self.assertTrue(
            any(
                "expected identity" in failure
                for failure in result_failures
            )
        )
        self.assertTrue(
            any(
                (
                    "stateUpgrade.currentRelaunchIdempotent=True"
                    in failure
                )
                for failure in result_failures
            )
        )

        runner = (
            check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_RUNNER
        )
        test = check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_TEST
        source_failures = validator(
            source_bytes_by_path={
                runner: runner.read_bytes() + b"\n",
                test: test.read_bytes(),
            }
        )
        self.assertTrue(
            any(
                "isolated upgrade source SHA-256" in failure
                for failure in source_failures
            )
        )

        receipt = json.loads(
            (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_RESULT
            ).read_text(encoding="utf-8")
        )
        receipt["runCount"] = True
        mutated_receipt = (
            json.dumps(
                receipt,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        receipt_failures = validator(
            repeatability_bytes=mutated_receipt,
        )
        self.assertTrue(
            any(
                "expected identity" in failure
                for failure in receipt_failures
            )
        )
        self.assertTrue(
            any(
                "exact two-run repeatability contract" in failure
                for failure in receipt_failures
            )
        )

        result = json.loads(
            (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_RESULT
            ).read_text(encoding="utf-8")
        )
        result["archiveReadback"]["current"]["unexpected"] = True
        mutated_schema = (
            json.dumps(
                result,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        schema_failures = validator(result_bytes=mutated_schema)
        self.assertTrue(
            any(
                "archiveReadback.current keys differ" in failure
                for failure in schema_failures
            )
        )

        for build_number, tree_name in (
            (23, "previousTree"),
            (24, "currentTree"),
        ):
            release_id = (
                f"aetherlink-1.0.0+{build_number}-local-v1"
            )
            manifest_path = (
                check_docs_hygiene.ROOT
                / "dist/releases"
                / release_id
                / f"{release_id}.manifest.json"
            )
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            executable_path = (
                "macos/AetherLink.app/Contents/MacOS/AetherLink"
            )
            executable = next(
                row
                for row in manifest["members"]
                if row["path"] == executable_path
            )
            executable["sha256"] = "0" * 64
            mutated_manifest = (
                json.dumps(
                    manifest,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            manifest_failures = validator(
                release_bytes_by_path={
                    manifest_path: mutated_manifest,
                }
            )
            self.assertTrue(
                any(
                    "executable identity does not match" in failure
                    for failure in manifest_failures
                )
            )
            self.assertTrue(
                any(
                    f"installation.{tree_name} does not derive" in failure
                    for failure in manifest_failures
                )
            )

        build23_release_id = "aetherlink-1.0.0+23-local-v1"
        build23_archive = (
            check_docs_hygiene.ROOT
            / "dist/releases"
            / build23_release_id
            / f"{build23_release_id}.zip"
        )
        archive_failures = validator(
            release_bytes_by_path={
                build23_archive: b"mutated-archive",
            }
        )
        self.assertTrue(
            any(
                "checksum sidecar differs from the actual ZIP identity"
                in failure
                for failure in archive_failures
            )
        )
        self.assertTrue(
            any(
                "snapshot identities do not match" in failure
                for failure in archive_failures
            )
        )

    def test_current_macos_isolated_upgrade_documentation_rejects_drift(
        self,
    ) -> None:
        validator = (
            check_docs_hygiene
            .current_macos_isolated_upgrade_document_failures
        )
        self.assertEqual(validator(), [])

        targets = (
            check_docs_hygiene.README_PATH,
            check_docs_hygiene.ROOT / "docs/roadmap.md",
            check_docs_hygiene.ROOT / "docs/handoff.md",
            check_docs_hygiene.ROOT / "docs/progress.md",
            check_docs_hygiene.ROOT / "docs/qa-evidence.md",
            check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC,
        )
        documents = {
            str(path.relative_to(check_docs_hygiene.ROOT)): (
                path.read_text(encoding="utf-8")
            )
            for path in targets
        }
        readme_relative = str(
            check_docs_hygiene.README_PATH.relative_to(
                check_docs_hygiene.ROOT
            )
        )
        identity = (
            check_docs_hygiene
            .CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SHA256
        )
        identity_documents = dict(documents)
        identity_documents[readme_relative] = documents[
            readme_relative
        ].replace(
            identity,
            "0" * 64,
            1,
        )
        failures = validator(
            document_text_by_relative=identity_documents,
        )
        self.assertTrue(
            any(
                readme_relative in failure
                and "canonical result identity" in failure
                for failure in failures
                )
            )

        readme_contract_mutations = (
            ("6,469-byte", "6,470-byte", "canonical result size"),
            (
                "isolated-upgrade-v2.json",
                "isolated-upgrade-v3.json",
                "canonical result path",
            ),
            ("898-byte", "899-byte", "repeatability receipt size"),
            (
                "isolated-upgrade-repeatability-v1.json",
                "isolated-upgrade-repeatability-v2.json",
                "repeatability receipt path",
            ),
            (
                (
                    check_docs_hygiene
                    .CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SHA256
                ),
                "1" * 64,
                "repeatability receipt identity",
            ),
        )
        for original, replacement, expected_label in (
            readme_contract_mutations
        ):
            mutated_documents = dict(documents)
            mutated_documents[readme_relative] = documents[
                readme_relative
            ].replace(original, replacement, 1)
            contract_failures = validator(
                document_text_by_relative=mutated_documents,
            )
            self.assertTrue(
                any(
                    readme_relative in failure
                    and expected_label in failure
                    for failure in contract_failures
                )
            )

        for path in targets:
            relative = str(path.relative_to(check_docs_hygiene.ROOT))
            text = documents[relative]
            start = text.index(
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
            )
            end = text.index(
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
            )
            block = text[start:end]
            self.assertIn("rollback", block)
            rollback_index = block.rfind("rollback")
            mutated_documents = dict(documents)
            mutated_documents[relative] = (
                text[:start]
                + block[:rollback_index]
                + "roll-back"
                + block[rollback_index + len("rollback"):]
                + text[end:]
            )
            boundary_failures = validator(
                document_text_by_relative=mutated_documents,
            )
            self.assertTrue(
                any(
                    relative in failure
                    and "canonical isolated upgrade boundary" in failure
                    for failure in boundary_failures
                )
            )

            start_marker = (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_START
            )
            end_marker = (
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
            )
            for marker in (start_marker, end_marker):
                marker_documents = dict(documents)
                marker_documents[relative] = text.replace(
                    marker,
                    "",
                    1,
                )
                marker_failures = validator(
                    document_text_by_relative=marker_documents,
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "markers must each appear exactly once" in failure
                        for failure in marker_failures
                    )
                )

            duplicate_documents = dict(documents)
            duplicate_documents[relative] = text.replace(
                start_marker,
                start_marker + "\n" + start_marker,
                1,
            )
            duplicate_failures = validator(
                document_text_by_relative=duplicate_documents,
            )
            self.assertTrue(
                any(
                    relative in failure
                    and "markers must each appear exactly once" in failure
                    for failure in duplicate_failures
                )
            )

            reversed_documents = dict(documents)
            placeholder = "<!-- isolated-upgrade-marker-placeholder -->"
            reversed_documents[relative] = (
                text.replace(start_marker, placeholder, 1)
                .replace(end_marker, start_marker, 1)
                .replace(placeholder, end_marker, 1)
            )
            reversed_failures = validator(
                document_text_by_relative=reversed_documents,
            )
            self.assertTrue(
                any(
                    relative in failure
                    and "markers are out of order" in failure
                    for failure in reversed_failures
                )
            )

            complete_end = end + len(end_marker)
            complete_block = text[start:complete_end]
            moved_documents = dict(documents)
            moved_documents[relative] = (
                text[:start]
                + text[complete_end:]
                + "\n\n"
                + complete_block
            )
            moved_failures = validator(
                document_text_by_relative=moved_documents,
            )
            self.assertTrue(
                any(
                    relative in failure
                    and "moved outside its canonical document location"
                    in failure
                    for failure in moved_failures
                )
            )

        contradictory_documents = dict(documents)
        readme_text = contradictory_documents[readme_relative]
        readme_end = readme_text.index(
            check_docs_hygiene
            .CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
        )
        contradictory_documents[readme_relative] = (
            readme_text[:readme_end]
            + (
                "Arbitrary N/N-1 versions and cross-host production "
                "qualification are complete.\n"
            )
            + readme_text[readme_end:]
        )
        contradictory_failures = validator(
            document_text_by_relative=contradictory_documents,
        )
        self.assertTrue(
            any(
                readme_relative in failure
                and "unnegated contradictory qualification claim" in failure
                for failure in contradictory_failures
            )
        )

        for contradictory_claim in (
            "This evidence supports rollback.",
            "UI behavior is qualified.",
            "Automatic Application Support cleanup is supported.",
            "Physical devices passed qualification.",
        ):
            claim_documents = dict(documents)
            readme_text = claim_documents[readme_relative]
            readme_end = readme_text.index(
                check_docs_hygiene
                .CURRENT_MACOS_ISOLATED_UPGRADE_DOCUMENT_END
            )
            claim_documents[readme_relative] = (
                readme_text[:readme_end]
                + contradictory_claim
                + "\n"
                + readme_text[readme_end:]
            )
            claim_failures = validator(
                document_text_by_relative=claim_documents,
            )
            self.assertTrue(
                any(
                    readme_relative in failure
                    and "exact bounded block SHA-256" in failure
                    for failure in claim_failures
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
            str(
                check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC.relative_to(
                    check_docs_hygiene.ROOT
                )
            ),
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
                    str(
                        check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC.relative_to(
                            check_docs_hygiene.ROOT
                        )
                    ),
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

                neutral_insertion = (
                    text[:end]
                    + "\nNeutral historical note.\n"
                    + text[end:]
                )
                neutral_failures = (
                    check_docs_hygiene
                    .current_macos_clean_home_lifecycle_document_failures(
                        document_text_by_relative={
                            relative: neutral_insertion,
                        }
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "retain exact SHA-256" in failure
                        for failure in neutral_failures
                    )
                )

                complete_block = (
                    start_marker + block + end_marker
                )
                relocated = (
                    text.replace(complete_block, "", 1).rstrip()
                    + "\n\n"
                    + complete_block
                    + "\n"
                )
                relocation_failures = (
                    check_docs_hygiene
                    .current_macos_clean_home_lifecycle_document_failures(
                        document_text_by_relative={relative: relocated}
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "canonical document location" in failure
                        for failure in relocation_failures
                    )
                )

                predecessor, successor = (
                    check_docs_hygiene
                    .CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_NEIGHBORS[
                        relative
                    ]
                )
                outer_start = text.index(predecessor)
                outer_end = text.index(successor) + len(successor)
                outer_span = text[outer_start:outer_end]
                relocated_outer_span = (
                    text[:outer_start] + text[outer_end:]
                ).rstrip() + "\n\n" + outer_span + "\n"
                outer_failures = (
                    check_docs_hygiene
                    .current_macos_clean_home_lifecycle_document_failures(
                        document_text_by_relative={
                            relative: relocated_outer_span,
                        }
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "outer document identity" in failure
                        for failure in outer_failures
                    )
                )

                hidden = text.replace(
                    complete_block,
                    "```\n" + complete_block + "\n```",
                    1,
                )
                hidden_failures = (
                    check_docs_hygiene
                    .current_macos_clean_home_lifecycle_document_failures(
                        document_text_by_relative={relative: hidden}
                    )
                )
                self.assertTrue(
                    any(
                        relative in failure
                        and "hidden Markdown or HTML" in failure
                        for failure in hidden_failures
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
            str(
                check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC.relative_to(
                    check_docs_hygiene.ROOT
                )
            ),
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
                (
                    r"not\s+an?\s+(?:retained\s+(?:Build\s+19\s+)?)?"
                    r"archive\s+member"
                ),
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
                .CURRENT_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS
            )
        )
        historical_sources = (
            check_docs_hygiene
            .LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS
        )
        current_sources = (
            check_docs_hygiene.CURRENT_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS
        )
        for relative in (
            "apps/macos/CompanionCore/Sources/"
            "SQLiteRuntimeChatEventStore.swift",
            "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
            "RuntimeChatSQLiteCrossProcessQA.swift",
        ):
            self.assertNotEqual(
                historical_sources[relative],
                current_sources[relative],
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
            str(
                check_docs_hygiene.LOCAL_RELEASE_CURRENT_DOC.relative_to(
                    check_docs_hygiene.ROOT
                )
            ),
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

    def test_build22_and_build23_historical_documents_are_byte_pinned(
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
            ).read_bytes()
            for entry in entries[:-1]
        }
        archive_sha256_by_build = {
            22: (
                "478bd4210c11f7e2204e80a333bc8053b0d01b8deff3d0a3d2dd6795df1366c3"
            ),
            23: (
                "b9a9c3c2ebeb01fc735fed3356f1f244178fb4521c1a806dc7a93d776f83ea2e"
            ),
        }
        for build_number, archive_sha256 in archive_sha256_by_build.items():
            mutations = {
                "identity": documents[build_number].replace(
                    archive_sha256.encode("ascii"),
                    b"0" * 64,
                    1,
                ),
                "line_endings": documents[build_number].replace(
                    b"\n",
                    b"\r\n",
                ),
            }
            for label, mutated_document in mutations.items():
                with self.subTest(
                    build_number=build_number,
                    mutation=label,
                ):
                    mutated_documents = dict(documents)
                    mutated_documents[build_number] = mutated_document
                    self.assertNotEqual(
                        mutated_documents[build_number],
                        documents[build_number],
                    )
                    failures = (
                        check_docs_hygiene
                        .historical_local_release_document_failures(
                            ledger_bytes=ledger_bytes,
                            document_bytes_by_build=mutated_documents,
                        )
                    )
                    self.assertTrue(
                        any(
                            (
                                f"build-{build_number}-local-v1.md" in failure
                                and "exact immutable document SHA-256" in failure
                            )
                            for failure in failures
                        ),
                        f"Build {build_number} {label} mutation was accepted: "
                        f"{failures!r}",
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
                "macos-packaged-app-build-23-to-24-isolated-upgrade-v2.json`"
            ),
            "6,469-byte canonical result",
            (
                f"`{check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RESULT_SHA256}`"
            ),
            (
                "`dist/lifecycle/macos-packaged-app-build-23-to-24-"
                "isolated-upgrade-repeatability-v1.json`"
            ),
            "898-byte repeatability receipt",
            (
                "`"
                f"{check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_REPEATABILITY_EXPECTED_SHA256}"
                "`"
            ),
            (
                f"`{check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_RUNNER_SHA256}`"
            ),
            (
                f"`{check_docs_hygiene.CURRENT_MACOS_ISOLATED_UPGRADE_EXPECTED_TEST_SHA256}`"
            ),
            (
                "`31209251804494f54a699c5c4e8101491f02fca881cf25fba379b88eb493d8a8`"
            ),
            (
                "`0c1882e653ec32a3bf5795c9369dbee818b6890157fbaaebd81c60b8c1a59fff`"
            ),
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
