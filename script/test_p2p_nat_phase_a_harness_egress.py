#!/usr/bin/env python3
"""Mutation tests for the Phase A static harness and egress validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from script import check_p2p_nat_phase_a_harness_egress as CHECKER


ROOT = Path(__file__).resolve().parents[1]


def replace_once(raw, old, new):
    before, separator, after = raw.partition(old)
    if not separator:
        raise AssertionError("replacement marker missing")
    return before + new + after


class PhaseAStaticHarnessEgressMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = CHECKER.load_json(CHECKER.ARTIFACT_JSON_PATH)

    def assert_rejected(self, mutation) -> None:
        candidate = copy.deepcopy(self.canonical)
        mutation(candidate)
        with self.assertRaises(CHECKER.HarnessEgressValidationError):
            CHECKER.validate_document(candidate)

    def test_canonical_artifacts_sources_and_ast_pass(self) -> None:
        CHECKER.validate_source_documents()
        CHECKER.validate_document(copy.deepcopy(self.canonical))
        CHECKER.validate_owned_python_ast()
        CHECKER.validate_artifact_hashes()

    def test_duplicate_keys_nonstandard_numbers_and_invalid_json_fail(self) -> None:
        raw = CHECKER.ARTIFACT_JSON_PATH.read_text(encoding="utf-8")
        duplicate_root = replace_once(
            raw,
            '  "artifactStatus": "static_design_complete",',
            '  "artifactStatus": "draft",\n  "artifactStatus": "static_design_complete",',
        )
        duplicate_nested = replace_once(
            raw,
            '    "sourceExecutionAllowed": false,',
            '    "sourceExecutionAllowed": true,\n    "sourceExecutionAllowed": false,',
        )
        for candidate in (duplicate_root, duplicate_nested, '{"value": NaN}', "{"):
            with self.subTest(candidate=candidate[:40]):
                with self.assertRaises(CHECKER.HarnessEgressValidationError):
                    CHECKER.parse_json(candidate, "mutation")

    def test_top_level_missing_unknown_and_scalar_drift_fail(self) -> None:
        self.assert_rejected(lambda value: value.pop("authorization"))
        self.assert_rejected(lambda value: value.update({"implementation": {}}))
        for key, mutation in (
            ("documentType", "other"),
            ("schemaVersion", 1.0),
            ("artifactId", "v2"),
            ("profileId", "other"),
            ("artifactStatus", "executed"),
            ("executionStatus", "passed"),
            ("measurementStatus", "measured"),
            ("scope", "runtime"),
        ):
            with self.subTest(key=key):
                self.assert_rejected(lambda value, key=key, mutation=mutation: value.update({key: mutation}))

    def test_exact_source_references_fail_on_any_drift(self) -> None:
        for parent, key, mutation in (
            ("sourceReview", "path", "review-v2.json"),
            ("sourceReview", "reviewId", "other"),
            ("sourceReview", "sha256", "0" * 64),
            ("sourceDecision", "path", "decision-v2.json"),
            ("sourceDecision", "decisionId", "other"),
            ("sourceDecision", "sha256", "1" * 64),
            ("sourceHandoff", "path", "handoff-v3.json"),
            ("sourceHandoff", "handoffId", "other"),
            ("sourceHandoff", "sha256", "f" * 64),
        ):
            with self.subTest(parent=parent, key=key):
                self.assert_rejected(
                    lambda value, parent=parent, key=key, mutation=mutation:
                    value[parent].update({key: mutation})
                )

    def test_static_harness_authorization_is_exact_true(self) -> None:
        for mutation in (False, 1, None, "true"):
            with self.subTest(mutation=mutation):
                self.assert_rejected(
                    lambda value, mutation=mutation:
                    value["authorization"].update({"staticHarnessImplementationAuthorized": mutation})
                )

    def test_every_execution_authorization_gate_is_exact_false(self) -> None:
        false_gates = {
            key for key, expected in CHECKER.EXPECTED_AUTHORIZATION.items() if expected is False
        }
        self.assertEqual(13, len(false_gates))
        for key in false_gates:
            for mutation in (True, 0, None, "false"):
                with self.subTest(key=key, mutation=mutation):
                    self.assert_rejected(
                        lambda value, key=key, mutation=mutation:
                        value["authorization"].update({key: mutation})
                    )
        self.assert_rejected(lambda value: value["authorization"].pop("socketCreationAllowed"))
        self.assert_rejected(lambda value: value["authorization"].update({"networkAllowed": False}))

    def test_three_namespace_topology_is_closed_and_exact(self) -> None:
        self.assert_rejected(lambda value: value["topology"]["namespaces"].pop())
        self.assert_rejected(lambda value: value["topology"]["namespaces"].reverse())
        self.assert_rejected(lambda value: value["topology"].update({"namespaceCount": 3.0}))
        self.assert_rejected(lambda value: value["topology"].update({"hostNetworkAttached": 0}))
        self.assert_rejected(lambda value: value["topology"].update({"defaultRoutePresent": True}))
        self.assert_rejected(lambda value: value["topology"].update({"internetReachable": True}))
        self.assert_rejected(
            lambda value: value["topology"]["namespaces"][0]["interfaces"][0].update({
                "ipv4Interface": "10.0.0.2/24"
            })
        )
        self.assert_rejected(
            lambda value: value["topology"]["namespaces"][0]["interfaces"][0].update({
                "peerNamespaceId": "agent-b"
            })
        )
        self.assert_rejected(
            lambda value: value["topology"]["namespaces"][2]["interfaces"].pop()
        )
        for namespace_index, process_index in ((0, 0), (1, 0), (2, 0), (2, 1)):
            with self.subTest(namespace_index=namespace_index, process_index=process_index):
                self.assert_rejected(
                    lambda value, namespace_index=namespace_index, process_index=process_index:
                    value["topology"]["namespaces"][namespace_index]["processIds"].pop(process_index)
                )
        self.assert_rejected(
            lambda value: value["topology"]["namespaces"][0]["processIds"].__setitem__(
                0, "agent-a"
            )
        )

    def test_ipaddress_validation_rejects_invalid_family_and_non_numeric_values(self) -> None:
        candidate = copy.deepcopy(self.canonical)
        candidate["topology"]["namespaces"][0]["interfaces"][0]["ipv4Interface"] = "999.0.0.1/30"
        with self.assertRaises(CHECKER.HarnessEgressValidationError):
            CHECKER.validate_ip_model(candidate)

        candidate = copy.deepcopy(self.canonical)
        candidate["tuplePolicy"]["flows"][0]["destinationAddress"] = "2001:db8:1::1"
        with self.assertRaises(CHECKER.HarnessEgressValidationError):
            CHECKER.validate_ip_model(candidate)

        candidate = copy.deepcopy(self.canonical)
        candidate["tuplePolicy"]["flows"][0]["destinationAddress"] = "service.invalid"
        with self.assertRaises(CHECKER.HarnessEgressValidationError):
            CHECKER.validate_ip_model(candidate)

        candidate = copy.deepcopy(self.canonical)
        candidate["tuplePolicy"]["flows"][3]["destinationAddress"] = "::ffff:192.0.2.1"
        with self.assertRaises(CHECKER.HarnessEgressValidationError):
            CHECKER.validate_ip_model(candidate)

    def test_exact_tuple_set_rejects_protocol_address_port_and_shape_drift(self) -> None:
        self.assertEqual(8, len(self.canonical["tuplePolicy"]["flows"]))
        self.assertEqual(
            {"udp"}, {item["protocol"] for item in self.canonical["tuplePolicy"]["flows"]}
        )
        self.assertEqual(
            {3478}, {item["destinationPort"] for item in self.canonical["tuplePolicy"]["flows"]}
        )
        self.assert_rejected(lambda value: value["tuplePolicy"]["flows"].pop())
        self.assert_rejected(lambda value: value["tuplePolicy"]["flows"].reverse())
        self.assert_rejected(
            lambda value: value["tuplePolicy"]["flows"][0].update({"protocol": "tcp"})
        )
        self.assert_rejected(
            lambda value: value["tuplePolicy"]["flows"][0].update({"sourcePort": 41000.0})
        )
        self.assert_rejected(
            lambda value: value["tuplePolicy"]["flows"][0].update({"destinationPort": True})
        )
        self.assert_rejected(
            lambda value: value["tuplePolicy"]["flows"][1].update({
                "protocol": "tcp", "destinationPort": 5349
            })
        )
        self.assert_rejected(
            lambda value: value["tuplePolicy"]["flows"][0].update({"destinationAddress": "192.0.2.9"})
        )
        self.assert_rejected(
            lambda value: value["tuplePolicy"]["flows"][0].update({"portRange": "3478-5349"})
        )
        for key in (
            "allowlistMutability", "implicitTuplesAllowed", "dnsResolutionAllowed",
            "proxyUseAllowed", "redirectFollowingAllowed", "requiredIceBehavior", "responseRule",
            "packetAssertion", "futurePhaseBRunManifest",
        ):
            with self.subTest(key=key):
                self.assert_rejected(lambda value, key=key: value["tuplePolicy"].pop(key))

    def test_future_phase_b_manifest_and_signature_remain_required_but_absent(self) -> None:
        expected = CHECKER.EXPECTED_TUPLE_POLICY["futurePhaseBRunManifest"]
        self.assertIsNone(expected["manifest"])
        self.assertIsNone(expected["signature"])
        for key, canonical in expected.items():
            if canonical is True:
                mutation = False
            elif canonical is False:
                mutation = True
            else:
                mutation = {"unexpected": "material"}
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation:
                    value["tuplePolicy"]["futurePhaseBRunManifest"].update({key: mutation})
                )
        self.assert_rejected(
            lambda value: value["tuplePolicy"]["futurePhaseBRunManifest"].update({
                "manifestSha256": "0" * 64
            })
        )

    def test_deny_all_intent_and_packet_vectors_are_exact(self) -> None:
        self.assert_rejected(lambda value: value["denyAllWitness"]["intentVectors"].pop())
        self.assert_rejected(lambda value: value["denyAllWitness"]["packetVectors"].pop())
        self.assert_rejected(
            lambda value: value["denyAllWitness"].update({"defaultPolicy": "allow_local"})
        )
        self.assert_rejected(
            lambda value: value["denyAllWitness"]["intentVectors"][0].update({
                "expectedReasonCode": "ALLOW"
            })
        )
        self.assert_rejected(
            lambda value: value["denyAllWitness"]["packetVectors"][0].update({
                "destinationAddress": "192.0.2.1",
                "destinationPort": 3478,
            })
        )
        self.assert_rejected(
            lambda value: value["denyAllWitness"]["packetVectors"][2].update({
                "sourcePort": False
            })
        )
        self.assert_rejected(
            lambda value: value["denyAllWitness"].pop("witnessIndependenceRule")
        )

    def test_every_required_deny_vector_is_mutation_guarded(self) -> None:
        required_intent_classes = {
            "dns", "mdns", "doh", "dot", "url_fetch", "http_proxy", "socks_proxy", "pac",
            "environment_proxy", "redirect", "wildcard", "port_range", "malformed_numeric",
            "route_mutation", "allowlist_mutation",
        }
        actual_intent_classes = {
            item["attemptClass"] for item in self.canonical["denyAllWitness"]["intentVectors"]
        }
        self.assertEqual(required_intent_classes, actual_intent_classes)
        for index, item in enumerate(CHECKER.EXPECTED_INTENT_VECTORS):
            with self.subTest(intent=item["vectorId"]):
                self.assert_rejected(
                    lambda value, index=index:
                    value["denyAllWitness"]["intentVectors"][index].update({
                        "expectedReasonCode": "ALLOW"
                    })
                )

        required_packet_ids = {
            "external-ipv4", "external-ipv6", "external-udp-ipv4", "external-udp-ipv6",
            "metadata-ipv4", "dns-ipv4", "agent-to-agent", "service-wrong-port",
            "ipv4-multicast", "ipv6-multicast", "ipv4-mapped-ipv6", "loopback-ipv4",
            "loopback-ipv6", "link-local-ipv4", "link-local-ipv6", "broadcast-ipv4",
            "unlisted-private-ipv4", "unspecified-ipv4", "unspecified-ipv6",
        }
        actual_packet_ids = {
            item["vectorId"] for item in self.canonical["denyAllWitness"]["packetVectors"]
        }
        self.assertEqual(required_packet_ids, actual_packet_ids)
        for index, item in enumerate(CHECKER.EXPECTED_PACKET_VECTORS):
            with self.subTest(packet=item["vectorId"]):
                self.assert_rejected(
                    lambda value, index=index:
                    value["denyAllWitness"]["packetVectors"][index].update({
                        "expectedReasonCode": "ALLOW"
                    })
                )

    def test_external_udp_deny_vectors_reject_omission_order_and_tuple_drift(self) -> None:
        packet_vectors = self.canonical["denyAllWitness"]["packetVectors"]
        self.assertEqual(
            ["external-ipv4", "external-ipv6", "external-udp-ipv4", "external-udp-ipv6"],
            [item["vectorId"] for item in packet_vectors[:4]],
        )
        self.assert_rejected(
            lambda value: value["denyAllWitness"]["packetVectors"].__setitem__(
                slice(2, 4), reversed(value["denyAllWitness"]["packetVectors"][2:4])
            )
        )
        drift_cases = {
            "external-udp-ipv4": (2, "203.0.113.253"),
            "external-udp-ipv6": (3, "2001:db8:ffff::253"),
        }
        for vector_id, (index, drifted_address) in drift_cases.items():
            with self.subTest(vector=vector_id, drift="missing"):
                self.assert_rejected(
                    lambda value, index=index:
                    value["denyAllWitness"]["packetVectors"].pop(index)
                )
            for key, mutation in (
                ("protocol", "tcp"),
                ("destinationAddress", drifted_address),
                ("destinationPort", 3479),
            ):
                with self.subTest(vector=vector_id, drift=key):
                    self.assert_rejected(
                        lambda value, index=index, key=key, mutation=mutation:
                        value["denyAllWitness"]["packetVectors"][index].update({key: mutation})
                    )

    def test_all_twelve_resource_ceilings_reject_value_type_and_key_drift(self) -> None:
        self.assertEqual(12, len(CHECKER.EXPECTED_RESOURCE_CEILINGS))
        for key, expected in CHECKER.EXPECTED_RESOURCE_CEILINGS.items():
            with self.subTest(key=key, case="value"):
                self.assert_rejected(
                    lambda value, key=key, expected=expected:
                    value["resourceCeilings"].update({key: expected + 1})
                )
            with self.subTest(key=key, case="float"):
                self.assert_rejected(
                    lambda value, key=key, expected=expected:
                    value["resourceCeilings"].update({key: float(expected)})
                )
            with self.subTest(key=key, case="bool"):
                self.assert_rejected(
                    lambda value, key=key: value["resourceCeilings"].update({key: True})
                )
        self.assert_rejected(lambda value: value["resourceCeilings"].pop("maximumRunSeconds"))
        self.assert_rejected(lambda value: value["resourceCeilings"].update({"maximumThreads": 4}))

    def test_content_free_evidence_contract_rejects_retention_or_schema_drift(self) -> None:
        self.assert_rejected(
            lambda value: value["evidencePolicy"].update({"packetPayloadRetentionBytes": 1})
        )
        self.assert_rejected(
            lambda value: value["evidencePolicy"].update({"applicationPayloadAdmissionBytes": False})
        )
        for key in ("rawPacketRetentionAllowed", "rawCandidateRetentionAllowed", "secretRetentionAllowed"):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key: value["evidencePolicy"].update({key: True})
                )
        self.assert_rejected(
            lambda value: value["evidencePolicy"]["allowedRecordKeys"].append("packetPayload")
        )
        self.assert_rejected(
            lambda value: value["evidencePolicy"]["prohibitedContentClasses"].remove("token")
        )
        self.assert_rejected(lambda value: value["evidencePolicy"].update({"rawLogsAllowed": True}))

    def test_evidence_regex_bounds_counters_and_empty_runtime_events_are_exact(self) -> None:
        for key in (
            "reasonCodeRegex", "counterNameRegex", "numericEndpointLabelRegex",
            "redactedDigestRegex",
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key: value["evidencePolicy"].update({key: ".*"})
                )
        self.assert_rejected(
            lambda value: value["evidencePolicy"].update({"maximumDurationMillis": 600001})
        )
        self.assert_rejected(
            lambda value: value["evidencePolicy"].update({"maximumCounterValue": 16777216.0})
        )
        self.assert_rejected(
            lambda value: value["evidencePolicy"]["retainedRuntimeEvents"].append({
                "reasonCode": "EXECUTED"
            })
        )
        candidate = copy.deepcopy(self.canonical)
        candidate["evidencePolicy"]["maximumDurationMillis"] = 1
        with self.assertRaises(CHECKER.HarnessEgressValidationError):
            CHECKER.validate_evidence_bounds(candidate)

    def test_kill_on_drift_is_fail_closed_for_every_trigger(self) -> None:
        for index, trigger in enumerate(CHECKER.EXPECTED_DRIFT_POLICY["triggers"]):
            with self.subTest(trigger=trigger):
                self.assert_rejected(
                    lambda value, index=index: value["driftPolicy"]["triggers"].pop(index)
                )
        for index, process_id in enumerate(CHECKER.EXPECTED_DRIFT_POLICY["terminationProcessIds"]):
            with self.subTest(process_id=process_id):
                self.assert_rejected(
                    lambda value, index=index:
                    value["driftPolicy"]["terminationProcessIds"].pop(index)
                )
        for index, action in enumerate(CHECKER.EXPECTED_DRIFT_POLICY["actions"]):
            with self.subTest(action=action):
                self.assert_rejected(
                    lambda value, index=index: value["driftPolicy"]["actions"].pop(index)
                )
        self.assert_rejected(
            lambda value: value["driftPolicy"].update({"measurementDisposition": "retain_partial"})
        )
        self.assert_rejected(
            lambda value: value["driftPolicy"].update({"continuationAllowedAfterDrift": True})
        )
        self.assert_rejected(
            lambda value: value["driftPolicy"].update({"validMeasurementAllowedAfterDrift": 0})
        )

    def test_phase_b_remains_unproven_blocked_and_unexecuted(self) -> None:
        for key, mutation in (
            ("status", "approved"),
            ("proofStatus", "proven"),
            ("executionStatus", "passed"),
            ("measurementStatus", "complete"),
            ("executionAuthorized", True),
            ("networkIOAllowed", True),
            ("socketExecutionAuthorized", True),
            ("externalEgressAllowed", True),
            ("requiredDecision", None),
        ):
            with self.subTest(key=key):
                self.assert_rejected(
                    lambda value, key=key, mutation=mutation: value["phaseB"].update({key: mutation})
                )

    def test_immutability_contract_and_byte_hashes_reject_drift(self) -> None:
        self.assert_rejected(lambda value: value["immutability"].update({"recordState": "open"}))
        self.assert_rejected(
            lambda value: value["immutability"]["coveredArtifacts"].pop()
        )
        for path, expected in CHECKER.ARTIFACT_SHA256.items():
            raw = path.read_bytes()
            self.assertEqual(expected, CHECKER.hash_bytes(raw))
            with self.assertRaises(CHECKER.HarnessEgressValidationError):
                CHECKER.validate_bytes_hash(raw + b"\n", expected, path.name)

    def test_ast_scanner_rejects_network_and_process_launch_constructs(self) -> None:
        forbidden_sources = (
            "import socket\nsocket.socket()\n",
            "socket.socket()\n",
            "import http.client\nhttp.client.HTTPConnection('example.invalid')\n",
            "from urllib import request\nrequest.urlopen('https://example.invalid')\n",
            "import requests\nrequests.get('https://example.invalid')\n",
            "import subprocess\nsubprocess.run(['true'])\n",
            "import multiprocessing\nmultiprocessing.Process()\n",
            "import os\nos.system('true')\n",
            "import os\nos.execv('/bin/true', ['true'])\n",
            "import asyncio\nasyncio.create_subprocess_shell('true')\n",
            "import ctypes\nctypes.CDLL('libc.so.6')\n",
            "import importlib\nimportlib.import_module('socket')\n",
            "from importlib import import_module\nimport_module('socket')\n",
            "import builtins\nbuiltins.__import__('socket')\n",
            "__import__('socket')\n",
            "eval('1 + 1')\n",
            "exec('value = 1')\n",
            "compile('value = 1', '<dynamic>', 'exec')\n",
            "getattr(__builtins__, '__import__')('socket')\n",
            "getattr(socket, 'socket')()\n",
            "sys.modules['socket'].socket()\n",
        )
        for index, raw in enumerate(forbidden_sources):
            with self.subTest(index=index):
                with self.assertRaises(CHECKER.HarnessEgressValidationError):
                    CHECKER.validate_ast_source(raw, f"mutation-{index}.py")
        CHECKER.validate_ast_source(
            "import ast\nimport hashlib\nfrom pathlib import Path\nvalue = hashlib.sha256(b'x').hexdigest()\n",
            "static-only.py",
        )

    def test_recursive_exact_rejects_false_zero_and_integer_float_confusion(self) -> None:
        for actual, expected in ((False, 0), (0, False), (26.0, 26), (1, True), (True, 1)):
            with self.subTest(actual=actual, expected=expected):
                with self.assertRaises(CHECKER.HarnessEgressValidationError):
                    CHECKER.recursive_exact(actual, expected, "type-confusion")

    def test_json_round_trip_has_no_unchecked_type_coercion(self) -> None:
        canonical_round_trip = json.loads(json.dumps(self.canonical))
        CHECKER.validate_document(canonical_round_trip)


if __name__ == "__main__":
    unittest.main()
