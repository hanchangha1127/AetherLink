package com.localagentbridge.android.core.pairing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

class RuntimePairingPayloadParserTest {
    @Test
    fun parsesAetherLinkQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&route_token=route-1" +
                "&service_type=_aetherlink._tcp.local."
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("fp-1", payload.fingerprint)
        assertEquals("route-1", payload.routeToken)
        assertNull(payload.host)
        assertNull(payload.port)
        assertEquals("_aetherlink._tcp.local.", payload.serviceType)
    }

    @Test
    fun parsesAllowedDiscoveryServiceTypeHints() {
        listOf(
            "_aetherlink._tcp.",
            "_aetherlink._tcp.local.",
            "_localagentbridge._tcp.",
            "_localagentbridge._tcp.local.",
        ).forEach { serviceType ->
            val payload = RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                    "&runtime_key_fingerprint=fp-1&service_type=$serviceType"
            )

            assertEquals(serviceType, payload.serviceType)
        }
    }

    @Test
    fun rejectsBackendProviderOrUrlShapedServiceTypeHints() {
        listOf(
            "https%3A%2F%2Fprovider.example.test%2Fv1%2Fmodels",
            "_ollama._tcp.local.",
            "_lmstudio._tcp.local.",
            "provider%3Dollama",
            "backend_url%3Dhttp%3A%2F%2F127.0.0.1%3A11434",
            "model%3Dgemma4%3Ae4b-mlx",
            "_aetherlink._tcp.local.%20",
            "_aetherlink%20._tcp.local.",
        ).forEach { serviceType ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&service_type=$serviceType"
                )
                fail("Expected invalid service_type $serviceType to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals("Invalid service type", error.message)
            }
        }
    }

    @Test
    fun rejectsDuplicateQueryKeysBeforeFieldSelection() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        listOf(
            "$identity&pairing_code=654321",
            "$identity&route_token=route-1&route%5Ftoken=route-2",
            identity +
                "&service_type=_aetherlink._tcp.local." +
                "&service_type=_localagentbridge._tcp.local.",
            identity +
                "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                "&relay_secret=secret-1&relay_expires_at=4102444800000" +
                "&relay_nonce=nonce-route-1&relay_id=relay-2",
            identity +
                "&p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=4102444800000" +
                "&p2p_anti_replay_nonce=nonce-p2p-1&p2p_protocol_version=1" +
                "&p2p_record_id=p2p-record-2",
        ).forEach { payload ->
            try {
                RuntimePairingPayloadParser.parse(payload)
                fail("Expected duplicate QR query key to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals("Duplicate pairing QR query key", error.message)
            }
        }
    }

    @Test
    fun rejectsUnknownQueryKeysBeforeFieldSelection() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        listOf(
            "backend_url=http%3A%2F%2F127.0.0.1%3A11434",
            "model=gemma4%3Ae4b-mlx",
            "route_secret2=secret-1",
            "p2p_session_key=session-key-1",
            "backend%5Furl=http%3A%2F%2Fprovider.example.test%2Fv1%2Fmodels",
        ).forEach { unknownField ->
            try {
                RuntimePairingPayloadParser.parse("$identity&$unknownField")
                fail("Expected unknown QR query field $unknownField to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals("Unknown pairing QR query key", error.message)
            }
        }
    }

    @Test
    fun rejectsMixedSemanticAliasesBeforeFieldSelection() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        val relayRoute = "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
            "&relay_secret=secret-1&relay_expires_at=4102444800000" +
            "&relay_nonce=nonce-route-1"
        listOf(
            "$identity&v=1",
            "$identity&n=nonce-2",
            "$identity&code=654321",
            "$identity&rid=runtime-2",
            "$identity&rn=Other+Runtime",
            "$identity&rf=fp-2",
            "$identity&runtime_public_key=public-key-1&rk=public-key-2",
            "$identity&route_token=route-1&rt=route-2",
            "$identity&host=192.168.1.10&runtime_host=192.168.1.11",
            "$identity&port=43170&p=43171",
            "$identity$relayRoute&network_id=relay-2",
            "$identity$relayRoute&relay_scope=remote&rsc=private_overlay",
        ).forEach { payload ->
            try {
                RuntimePairingPayloadParser.parse(payload)
                fail("Expected mixed semantic QR aliases to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals("Mixed pairing QR semantic alias fields", error.message)
            }
        }
    }

    @Test
    fun parsesPairActionCaseInsensitively() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://PAIR?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1"
        )

        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("fp-1", payload.fingerprint)
    }

    @Test
    fun rejectsPathOnlyPairingUriForms() {
        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink:/pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                    "&runtime_key_fingerprint=fp-1"
            )
            fail("Expected path-only pairing URI to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun rejectsMissingOrUnsupportedPairingQrVersion() {
        val unversionedPayload = "aetherlink://pair?pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        try {
            RuntimePairingPayloadParser.parse(unversionedPayload)
            fail("Expected unversioned pairing URI to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse("$unversionedPayload&version=2")
            fail("Expected unsupported pairing URI version to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun parsesIdentityOnlyQrPayloadWithoutEndpointHint() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1"
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("fp-1", payload.fingerprint)
        assertNull(payload.routeToken)
        assertNull(payload.host)
        assertNull(payload.port)
        assertNull(payload.serviceType)
    }

    @Test
    fun rejectsRouteTokenWithWhitespaceForIdentityOnlyQrPayload() {
        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                    "&runtime_key_fingerprint=fp-1&route_token=route%201"
            )
            fail("Expected identity-only route token with whitespace to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun rejectsWhitespaceMutatedTrustAndRouteIdentityQrValues() {
        val base = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_public_key=public-key-1&runtime_key_fingerprint=fp-1&route_token=route-1" +
            "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
            "&relay_secret=secret-1&relay_expires_at=4102444800000&relay_nonce=nonce-route-1" +
            "&relay_scope=remote"
        val mutatedFields = listOf(
            "pairing_nonce" to "nonce%201",
            "runtime_device_id" to "%20runtime-1",
            "runtime_key_fingerprint" to "fp-1%0A",
            "runtime_public_key" to "public%20key-1",
            "route_token" to "route%091",
            "relay_id" to "relay%201",
            "relay_secret" to "secret%201",
            "relay_nonce" to "%20nonce-route-1",
            "relay_scope" to "remote%20",
        )

        mutatedFields.forEach { (field, value) ->
            try {
                RuntimePairingPayloadParser.parse(base.replace("$field=${fieldValue(field)}", "$field=$value"))
                fail("Expected QR with whitespace-mutated $field to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun rejectsUnknownOrCaseMutatedRemoteRelayScope() {
        listOf("public", "REMOTE", "privateOverlay").forEach { relayScope ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&relay_host=relay.example.test" +
                        "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                        "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1" +
                        "&relay_scope=$relayScope"
                )
                fail("Expected QR with unsupported relay scope $relayScope to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun normalizesBlankRuntimeNameToDefaultRuntimeName() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=%20%20%20" +
                "&runtime_key_fingerprint=fp-1"
        )

        assertEquals("AetherLink Runtime", payload.runtimeName)
    }

    @Test
    fun capsOversizedRuntimeNameBeforeUiOrStorage() {
        val oversizedName = "Runtime%20" + "x".repeat(120)
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=$oversizedName" +
                "&runtime_key_fingerprint=fp-1"
        )

        assertEquals(80, payload.runtimeName.length)
        assertTrue(payload.runtimeName.startsWith("Runtime x"))
    }

    @Test
    fun parsesRuntimeIdentityAliases() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_public_key=public-key&runtime_key_fingerprint=fp-1"
        )

        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("public-key", payload.runtimePublicKeyBase64)
        assertEquals("fp-1", payload.fingerprint)
    }

    @Test
    fun preservesLiteralPlusInOpaqueQrValues() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink%20Runtime" +
                "&runtime_public_key=abc+def/ghi%3D&runtime_key_fingerprint=fp-1" +
                "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                "&relay_secret=secret+with/symbols%3D" +
                "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
        )

        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("abc+def/ghi=", payload.runtimePublicKeyBase64)
        assertEquals("secret+with/symbols=", payload.relaySecret)
    }

    @Test
    fun rejectsWhitespaceMutatedRelaySecretAliasesInQrPayload() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        listOf(
            "relay_secret" to
                "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                "&relay_secret=secret-1&relay_expires_at=4102444800000&relay_nonce=nonce-route-1",
            "remote_secret" to
                "&remote_host=relay.example.test&remote_port=443&remote_id=relay-1" +
                "&remote_secret=secret-1&remote_expires_at=4102444800000&remote_nonce=nonce-route-1",
            "route_secret" to
                "&route_host=relay.example.test&route_port=443&route_id=relay-1" +
                "&route_secret=secret-1&route_expires_at=4102444800000&route_nonce=nonce-route-1",
            "rendezvous_secret" to
                "&rendezvous_host=relay.example.test&rendezvous_port=443&rendezvous_id=relay-1" +
                "&rendezvous_secret=secret-1&rendezvous_expires_at=4102444800000" +
                "&rendezvous_nonce=nonce-route-1",
            "rs" to
                "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1",
        ).forEach { (field, routeFields) ->
            try {
                RuntimePairingPayloadParser.parse(
                    identity + routeFields.replace("$field=secret-1", "$field=secret%201")
                )
                fail("Expected whitespace-mutated relay secret alias $field to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun parsesLegacyDiscoveryTokenAlias() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&mac_device_id=legacy-1&mac_name=AetherLink+Runtime&fingerprint=fp-1" +
                "&discovery_token=legacy-route"
        )

        assertEquals("legacy-1", payload.runtimeDeviceId)
        assertEquals("legacy-route", payload.routeToken)
    }

    @Test
    fun parsesLegacyEndpointAliases() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&nonce=nonce-1&code=123456" +
                "&device_id=mac-1&name=AetherLink+Mac&cert_fingerprint=fp-1" +
                "&runtime_host=10.0.2.2&runtime_port=43170&route_scope=local_diagnostic",
            allowDiagnosticLocalDirectEndpoint = true,
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("mac-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Mac", payload.runtimeName)
        assertEquals("fp-1", payload.fingerprint)
        assertEquals("10.0.2.2", payload.host)
        assertEquals(43170, payload.port)
    }

    @Test
    fun rejectsLocalDirectEndpointQrByDefault() {
        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                    "&runtime_key_fingerprint=fp-1&host=192.168.1.10&port=43170"
            )
            fail("Expected product parser policy to reject local direct endpoint QR")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun allowsLocalDirectEndpointOnlyForExplicitDiagnosticParse() {
        val rawPayload = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1&host=192.168.1.10&port=43170" +
            "&route_scope=local_diagnostic"

        try {
            RuntimePairingPayloadParser.parse(rawPayload)
            fail("Expected default parser policy to reject diagnostic local endpoint QR")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        val payload = RuntimePairingPayloadParser.parse(
            rawValue = rawPayload,
            allowDiagnosticLocalDirectEndpoint = true,
        )

        assertEquals("192.168.1.10", payload.host)
        assertEquals(43170, payload.port)
        assertEquals("local_diagnostic", payload.relayScope)

        try {
            RuntimePairingPayloadParser.parse(
                rawPayload.replace("local_diagnostic", "LOCAL_DIAGNOSTIC"),
                allowDiagnosticLocalDirectEndpoint = true,
            )
            fail("Expected case-mutated diagnostic scope to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun diagnosticParseAcceptsLegacyLocalDirectQrWithoutVersionOrRouteScope() {
        val rawPayload = "aetherlink://pair?pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1&host=192.168.1.10&port=43170"

        try {
            RuntimePairingPayloadParser.parse(rawPayload)
            fail("Expected default parser policy to reject legacy diagnostic local endpoint QR")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        val payload = RuntimePairingPayloadParser.parse(
            rawValue = rawPayload,
            allowDiagnosticLocalDirectEndpoint = true,
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("192.168.1.10", payload.host)
        assertEquals(43170, payload.port)
        assertNull(payload.relayScope)
    }

    @Test
    fun parsesRelaySecretFromQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&relay_host=relay.example.test" +
                "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
        )

        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(443, payload.relayPort)
        assertEquals("relay-1", payload.relayId)
        assertEquals("secret-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", payload.relayNonce)
    }

    @Test
    fun parsesCompactRemoteRouteQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=fp-1&rk=public-key-1&rt=route-token-1" +
                "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1"
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("fp-1", payload.fingerprint)
        assertEquals("public-key-1", payload.runtimePublicKeyBase64)
        assertEquals("route-token-1", payload.routeToken)
        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(443, payload.relayPort)
        assertEquals("relay-1", payload.relayId)
        assertEquals("secret-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", payload.relayNonce)
    }

    @Test
    fun parsesSharedMacosCompactRelayQrFixture() {
        val payload = RuntimePairingPayloadParser.parse(
            sharedProtocolFixture("macos-compact-relay-pairing-uri.txt"),
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("runtime-fingerprint", payload.fingerprint)
        assertEquals("runtime+public/key=", payload.runtimePublicKeyBase64)
        assertEquals("route-token-1", payload.routeToken)
        assertNull(payload.host)
        assertNull(payload.port)
        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(43171, payload.relayPort)
        assertEquals("relay-bootstrap-1", payload.relayId)
        assertEquals("secret-bootstrap-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("allocated-nonce-1", payload.relayNonce)
        assertEquals("remote", payload.relayScope)
    }

    @Test
    fun parsesSharedMacosCompactPrivateOverlayRelayQrFixture() {
        val payload = RuntimePairingPayloadParser.parse(
            sharedProtocolFixture("macos-compact-private-overlay-pairing-uri.txt"),
        )

        assertEquals("nonce-private-1", payload.pairingNonce)
        assertEquals("654321", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("runtime-fingerprint", payload.fingerprint)
        assertEquals("runtime+public/key=", payload.runtimePublicKeyBase64)
        assertEquals("route-token-1", payload.routeToken)
        assertNull(payload.host)
        assertNull(payload.port)
        assertEquals("100.64.1.10", payload.relayHost)
        assertEquals(43171, payload.relayPort)
        assertEquals("relay-private-overlay-1", payload.relayId)
        assertEquals("secret-private-overlay-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("private-overlay-nonce-1", payload.relayNonce)
        assertEquals("private_overlay", payload.relayScope)
    }

    @Test
    fun compactRemoteRouteQrStripsDiagnosticDirectEndpointWhenRelayIsPresent() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=fp-1&rk=public-key-1" +
                "&h=192.168.1.10&p=43170" +
                "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1"
        )

        assertNull(payload.host)
        assertNull(payload.port)
        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(443, payload.relayPort)
        assertEquals("relay-1", payload.relayId)
        assertEquals("secret-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", payload.relayNonce)
    }

    @Test
    fun completeRemoteRouteQrIgnoresInvalidDirectEndpointWhenRelayIsPresent() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?v=1&n=nonce-1&c=123456" +
                "&rid=runtime-1&rn=AetherLink%20Runtime&rf=fp-1&rk=public-key-1" +
                "&h=192.168.1.10&p=70000" +
                "&rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1"
        )

        assertNull(payload.host)
        assertNull(payload.port)
        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(443, payload.relayPort)
        assertEquals("relay-1", payload.relayId)
        assertEquals("secret-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", payload.relayNonce)
    }

    @Test
    fun parsesRelayExpirationEpochSecondsFromQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&relay_host=relay.example.test" +
                "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                "&relay_expires_at=4102444800&relay_nonce=nonce-route-1"
        )

        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
    }

    @Test
    fun parsesRemoteRouteAliasesFromQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&remote_host=relay.example.test" +
                "&remote_port=443&remote_id=relay-1&remote_secret=secret-1" +
                "&remote_expires_at=4102444800000&remote_nonce=nonce-route-1"
        )

        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(443, payload.relayPort)
        assertEquals("relay-1", payload.relayId)
        assertEquals("secret-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", payload.relayNonce)
    }

    @Test
    fun parsesRouteAliasPrivateOverlayScopeFromQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&route_host=100.64.1.10" +
                "&route_port=443&route_id=relay-1&route_secret=secret-1" +
                "&route_expires_at=4102444800000&route_nonce=nonce-route-1" +
                "&route_scope=private_overlay"
        )

        assertEquals("100.64.1.10", payload.relayHost)
        assertEquals(443, payload.relayPort)
        assertEquals("relay-1", payload.relayId)
        assertEquals("secret-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", payload.relayNonce)
        assertEquals("private_overlay", payload.relayScope)
    }

    @Test
    fun parsesRendezvousRouteAliasesFromQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&rendezvous_host=relay.example.test" +
                "&rendezvous_port=443&rendezvous_id=relay-1&rendezvous_secret=secret-1" +
                "&rendezvous_expires_at=4102444800000&rendezvous_nonce=nonce-route-1"
        )

        assertEquals("relay.example.test", payload.relayHost)
        assertEquals(443, payload.relayPort)
        assertEquals("relay-1", payload.relayId)
        assertEquals("secret-1", payload.relaySecret)
        assertEquals(4102444800000L, payload.relayExpiresAtEpochMillis)
        assertEquals("nonce-route-1", payload.relayNonce)
        assertNull(payload.p2pRecordId)
    }

    @Test
    fun parsesP2pRendezvousRouteQrPayloadWithoutRelayAliasCollision() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&p2p_class=p2p_rendezvous" +
                "&p2p_record_id=p2p-record-1&p2p_encrypted_body=opaque-candidate-1" +
                "&p2p_expires_at=4102444800000&p2p_anti_replay_nonce=nonce-p2p-1" +
                "&p2p_protocol_version=1"
        )

        assertNull(payload.host)
        assertNull(payload.port)
        assertNull(payload.relayHost)
        assertNull(payload.relayPort)
        assertNull(payload.relayId)
        assertNull(payload.relaySecret)
        assertNull(payload.relayExpiresAtEpochMillis)
        assertNull(payload.relayNonce)
        assertEquals("p2p_rendezvous", payload.p2pRouteClass)
        assertEquals("p2p-record-1", payload.p2pRecordId)
        assertEquals("opaque-candidate-1", payload.p2pEncryptedBody)
        assertEquals(4102444800000L, payload.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-1", payload.p2pAntiReplayNonce)
        assertEquals(1, payload.p2pProtocolVersion)
    }

    @Test
    fun parsesP2pRendezvousExpirationEpochSecondsFromQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&p2p_class=p2p_rendezvous" +
                "&p2p_record_id=p2p-record-1&p2p_encrypted_body=opaque-candidate-1" +
                "&p2p_expires_at=4102444800&p2p_anti_replay_nonce=nonce-p2p-1" +
                "&p2p_protocol_version=1"
        )

        assertEquals(4102444800000L, payload.p2pExpiresAtEpochMillis)
    }

    @Test
    fun p2pRendezvousQrStripsDiagnosticDirectEndpointWhenP2pRouteIsPresent() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&host=192.168.1.10&port=43170" +
                "&p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=4102444800000" +
                "&p2p_anti_replay_nonce=nonce-p2p-1&p2p_protocol_version=1"
        )

        assertNull(payload.host)
        assertNull(payload.port)
        assertEquals("p2p-record-1", payload.p2pRecordId)
    }

    @Test
    fun parsesSharedCompactP2pRendezvousQrFixture() {
        val payload = RuntimePairingPayloadParser.parse(
            sharedProtocolFixture("macos-compact-p2p-rendezvous-pairing-uri.txt"),
        )

        assertEquals("nonce-p2p-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("runtime-fingerprint", payload.fingerprint)
        assertEquals("runtime+public/key=", payload.runtimePublicKeyBase64)
        assertEquals("route-token-1", payload.routeToken)
        assertNull(payload.relayHost)
        assertNull(payload.relayPort)
        assertEquals("p2p_rendezvous", payload.p2pRouteClass)
        assertEquals("p2p-record-1", payload.p2pRecordId)
        assertEquals("opaque-candidate-1", payload.p2pEncryptedBody)
        assertEquals(4102444800000L, payload.p2pExpiresAtEpochMillis)
        assertEquals("nonce-p2p-route-1", payload.p2pAntiReplayNonce)
        assertEquals(1, payload.p2pProtocolVersion)
    }

    @Test
    fun rejectsIncompleteP2pRendezvousRouteQrPayload() {
        listOf(
            "p2p_record_id=p2p-record-1&p2p_encrypted_body=opaque-candidate-1" +
                "&p2p_expires_at=4102444800000&p2p_anti_replay_nonce=nonce-p2p-1" +
                "&p2p_protocol_version=1",
            "p2p_class=p2p_rendezvous&p2p_encrypted_body=opaque-candidate-1" +
                "&p2p_expires_at=4102444800000&p2p_anti_replay_nonce=nonce-p2p-1" +
                "&p2p_protocol_version=1",
            "p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_expires_at=4102444800000&p2p_anti_replay_nonce=nonce-p2p-1" +
                "&p2p_protocol_version=1",
            "p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_anti_replay_nonce=nonce-p2p-1" +
                "&p2p_protocol_version=1",
            "p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=4102444800000" +
                "&p2p_protocol_version=1",
            "p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=4102444800000" +
                "&p2p_anti_replay_nonce=nonce-p2p-1",
        ).forEach { routeFields ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&$routeFields"
                )
                fail("Expected incomplete P2P rendezvous route to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun rejectsInvalidP2pRendezvousRouteQrPayload() {
        val base = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1&p2p_class=p2p_rendezvous" +
            "&p2p_record_id=p2p-record-1&p2p_encrypted_body=opaque-candidate-1" +
            "&p2p_expires_at=4102444800000&p2p_anti_replay_nonce=nonce-p2p-1" +
            "&p2p_protocol_version=1"
        listOf(
            "p2p_class=p2p_signal",
            "p2p_record_id=p2p%20record-1",
            "p2p_encrypted_body=opaque%20candidate-1",
            "p2p_expires_at=not-a-number",
            "p2p_anti_replay_nonce=nonce%20p2p-1",
            "p2p_protocol_version=2",
        ).forEach { mutation ->
            val field = mutation.substringBefore("=")
            try {
                RuntimePairingPayloadParser.parse(base.replace("$field=${fieldValue(field)}", mutation))
                fail("Expected invalid P2P rendezvous route field $field to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun rejectsNonCanonicalRouteExpirationAliasesInQrPayload() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        listOf(
            "relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                "&relay_secret=secret-1&relay_expires_at=04102444800000" +
                "&relay_nonce=nonce-route-1" to "Invalid relay expiration",
            "relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                "&relay_secret=secret-1&relay_expires_at=%2B4102444800000" +
                "&relay_nonce=nonce-route-1" to "Invalid relay expiration",
            "rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1&rx=04102444800000" +
                "&rrn=nonce-route-1" to "Invalid relay expiration",
            "rh=relay.example.test&rp=443&ri=relay-1&rs=secret-1&rx=%2B4102444800000" +
                "&rrn=nonce-route-1" to "Invalid relay expiration",
            "p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=04102444800000" +
                "&p2p_anti_replay_nonce=nonce-p2p-1&p2p_protocol_version=1" to "Invalid P2P expiration",
            "p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=%2B4102444800000" +
                "&p2p_anti_replay_nonce=nonce-p2p-1&p2p_protocol_version=1" to "Invalid P2P expiration",
            "pc=p2p_rendezvous&prid=p2p-record-1&peb=opaque-candidate-1" +
                "&px=04102444800000&pn=nonce-p2p-1&pv=1" to "Invalid P2P expiration",
            "pc=p2p_rendezvous&prid=p2p-record-1&peb=opaque-candidate-1" +
                "&px=%2B4102444800000&pn=nonce-p2p-1&pv=1" to "Invalid P2P expiration",
        ).forEach { (routeFields, expectedMessage) ->
            try {
                RuntimePairingPayloadParser.parse("$identity&$routeFields")
                fail("Expected non-canonical route expiration to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals(expectedMessage, error.message)
            }
        }
    }

    @Test
    fun rejectsNonCanonicalRelayPortAliasesInQrPayload() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        listOf(
            "relay_host=relay.example.test&relay_port=0443&relay_id=relay-1" +
                "&relay_secret=secret-1&relay_expires_at=4102444800000" +
                "&relay_nonce=nonce-route-1",
            "relay_host=relay.example.test&relay_port=%2B443&relay_id=relay-1" +
                "&relay_secret=secret-1&relay_expires_at=4102444800000" +
                "&relay_nonce=nonce-route-1",
            "remote_host=relay.example.test&remote_port=%2B443&remote_id=relay-1" +
                "&remote_secret=secret-1&remote_expires_at=4102444800000" +
                "&remote_nonce=nonce-route-1",
            "route_host=relay.example.test&route_port=0443&route_id=relay-1" +
                "&route_secret=secret-1&route_expires_at=4102444800000" +
                "&route_nonce=nonce-route-1",
            "rendezvous_host=relay.example.test&rendezvous_port=%2B443&rendezvous_id=relay-1" +
                "&rendezvous_secret=secret-1&rendezvous_expires_at=4102444800000" +
                "&rendezvous_nonce=nonce-route-1",
            "rh=relay.example.test&rp=0443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1",
            "rh=relay.example.test&rp=%2B443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1",
        ).forEach { routeFields ->
            try {
                RuntimePairingPayloadParser.parse("$identity&$routeFields")
                fail("Expected non-canonical relay port to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals("Invalid relay port", error.message)
            }
        }
    }

    @Test
    fun rejectsNonCanonicalP2pProtocolVersionAliasesInQrPayload() {
        val canonicalBase = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1&p2p_class=p2p_rendezvous" +
            "&p2p_record_id=p2p-record-1&p2p_encrypted_body=opaque-candidate-1" +
            "&p2p_expires_at=4102444800000&p2p_anti_replay_nonce=nonce-p2p-1" +
            "&p2p_protocol_version=1"
        listOf("p2p_protocol_version=01", "p2p_protocol_version=%2B1").forEach { mutation ->
            try {
                RuntimePairingPayloadParser.parse(
                    canonicalBase.replace("p2p_protocol_version=1", mutation)
                )
                fail("Expected non-canonical P2P protocol version $mutation to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                    "&runtime_key_fingerprint=fp-1&pc=p2p_rendezvous&prid=p2p-record-1" +
                    "&peb=opaque-candidate-1&px=4102444800000&pn=nonce-p2p-1&pv=01"
            )
            fail("Expected non-canonical compact P2P protocol version to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun rejectsMixedP2pAliasFamiliesFromQrPayload() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        listOf(
            "p2p_class=p2p_rendezvous&prid=p2p-record-1&peb=opaque-candidate-1" +
                "&px=4102444800000&pn=nonce-p2p-1&pv=1",
            "pc=p2p_rendezvous&p2p_record_id=p2p-record-1&p2p_encrypted_body=opaque-candidate-1" +
                "&p2p_expires_at=4102444800000&p2p_anti_replay_nonce=nonce-p2p-1" +
                "&p2p_protocol_version=1",
            "p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=4102444800000" +
                "&p2p_anti_replay_nonce=nonce-p2p-1&p2p_protocol_version=1" +
                "&pc=p2p_rendezvous&prid=p2p-record-2&peb=opaque-candidate-2" +
                "&px=4102444800000&pn=nonce-p2p-2&pv=1",
        ).forEach { routeFields ->
            try {
                RuntimePairingPayloadParser.parse("$identity&$routeFields")
                fail("Expected mixed P2P alias families to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun rejectsOversizedOpaqueRouteQrValues() {
        val oversizedValue = "r".repeat(OPAQUE_ROUTE_VALUE_MAX_CHARS + 1)
        val oversizedBody = "b".repeat(OPAQUE_ROUTE_BODY_MAX_CHARS + 1)
        val identityBase = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1&route_token=route-1"
        val relayBase = identityBase +
            "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
            "&relay_secret=secret-1&relay_expires_at=4102444800000" +
            "&relay_nonce=nonce-route-1"
        val p2pBase = identityBase +
            "&p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
            "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=4102444800000" +
            "&p2p_anti_replay_nonce=nonce-p2p-1&p2p_protocol_version=1"

        listOf(
            identityBase.replace("route_token=route-1", "route_token=$oversizedValue"),
            relayBase.replace("relay_id=relay-1", "relay_id=$oversizedValue"),
            relayBase.replace("relay_secret=secret-1", "relay_secret=$oversizedValue"),
            relayBase.replace("relay_nonce=nonce-route-1", "relay_nonce=$oversizedValue"),
            p2pBase.replace("p2p_record_id=p2p-record-1", "p2p_record_id=$oversizedValue"),
            p2pBase.replace("p2p_encrypted_body=opaque-candidate-1", "p2p_encrypted_body=$oversizedBody"),
            p2pBase.replace("p2p_anti_replay_nonce=nonce-p2p-1", "p2p_anti_replay_nonce=$oversizedValue"),
        ).forEach { payload ->
            try {
                RuntimePairingPayloadParser.parse(payload)
                fail("Expected oversized opaque route QR value to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun rejectsIncompleteRelayAliasFamiliesFromQrPayload() {
        listOf(
            "remote_host=relay.example.test&remote_port=443&remote_id=relay-1" +
                "&remote_expires_at=4102444800000&remote_nonce=nonce-route-1",
            "route_host=relay.example.test&route_port=443&route_id=relay-1" +
                "&route_secret=secret-1&route_nonce=nonce-route-1",
            "rendezvous_host=relay.example.test&rendezvous_port=443&rendezvous_id=relay-1" +
                "&rendezvous_secret=secret-1&rendezvous_expires_at=4102444800000",
        ).forEach { routeFields ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&$routeFields"
                )
                fail("Expected incomplete relay alias family to throw")
            } catch (error: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun rejectsMixedRelayAliasFamiliesFromQrPayload() {
        val identity = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1"
        listOf(
            "remote_host=relay.example.test&remote_port=443&route_id=relay-1" +
                "&route_secret=secret-1&remote_expires_at=4102444800000" +
                "&remote_nonce=nonce-route-1",
            "relay_host=relay.example.test&rp=443&ri=relay-1&rs=secret-1" +
                "&rx=4102444800000&rrn=nonce-route-1",
            "rh=relay.example.test&rp=443&rendezvous_id=relay-1" +
                "&rendezvous_secret=secret-1&rendezvous_expires_at=4102444800000" +
                "&rendezvous_nonce=nonce-route-1",
            "remote_host=relay.example.test&remote_port=443&remote_id=relay-1" +
                "&remote_secret=secret-1&remote_expires_at=4102444800000" +
                "&remote_nonce=nonce-route-1&route_host=relay.example.test" +
                "&route_port=443&route_id=relay-2&route_secret=secret-2" +
                "&route_expires_at=4102444800000&route_nonce=nonce-route-2",
        ).forEach { routeFields ->
            try {
                RuntimePairingPayloadParser.parse("$identity&$routeFields")
                fail("Expected mixed relay alias families to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals("Mixed relay alias families", error.message)
            }
        }
    }

    @Test
    fun rejectsRelayHostsThatCannotWorkAcrossNetworks() {
        listOf(
            "127.0.0.1",
            "localhost",
            "0.0.0.0",
            "10.0.0.5",
            "100.64.1.5",
            "169.254.10.20",
            "172.20.1.5",
            "192.168.50.10",
            "%5B::1%5D",
            "%5Bfe80::1%5D",
            "%5Bfd00::1%5D",
            "aetherlink.local",
        ).forEach { relayHost ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&relay_host=$relayHost" +
                        "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                        "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
                )
                fail("Expected relay host $relayHost to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun rejectsNonCanonicalRelayHostsBeforeRouteMaterialAcceptance() {
        listOf(
            "%20relay.example.test",
            "relay.example.test%20",
            "relay%20example.test",
            "https%3A%2F%2Frelay.example.test",
            "relay.example.test%2Fpath",
            "relay.example.test%3Froute%3D1",
            "relay.example.test%23fragment",
            "user%40relay.example.test",
        ).forEach { relayHost ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&relay_host=$relayHost" +
                        "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                        "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
                )
                fail("Expected non-canonical relay host $relayHost to throw")
            } catch (error: IllegalArgumentException) {
                assertEquals("Invalid relay host", error.message)
            }
        }
    }

    @Test
    fun rejectsPrivateOverlayRelayHostsWithoutExplicitScopeWithFocusedError() {
        listOf(
            "10.0.0.5",
            "100.64.1.5",
            "100.64.1.5.",
            "172.20.1.5",
            "192.168.50.10",
            "%5Bfd00::1%5D",
        ).forEach { relayHost ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&relay_host=$relayHost" +
                        "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                        "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
                )
                fail("Expected private relay host $relayHost to require private_overlay scope")
            } catch (error: IllegalArgumentException) {
                assertEquals(
                    "Private relay hosts require relay_scope=private_overlay",
                    error.message,
                )
            }
        }
    }

    @Test
    fun allowsPrivateOverlayRelayHostsOnlyWithExplicitScope() {
        listOf(
            "10.0.0.5",
            "100.64.1.5",
            "100.64.1.5.",
            "172.20.1.5",
            "192.168.50.10",
            "%5Bfd00::1%5D",
        ).forEach { relayHost ->
            val payload = RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                    "&runtime_key_fingerprint=fp-1&relay_host=$relayHost" +
                    "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                    "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1" +
                    "&relay_scope=private_overlay"
            )

            assertEquals("private_overlay", payload.relayScope)
        }
    }

    @Test
    fun rejectsLinkLocalRelayHostsEvenWithPrivateOverlayScope() {
        listOf(
            "169.254.10.20",
            "%5Bfe80::1%5D",
        ).forEach { relayHost ->
            try {
                RuntimePairingPayloadParser.parse(
                    "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                        "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                        "&runtime_key_fingerprint=fp-1&relay_host=$relayHost" +
                        "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
                        "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1" +
                        "&relay_scope=private_overlay"
                )
                fail("Expected link-local relay host $relayHost to throw")
            } catch (_: IllegalArgumentException) {
                // Expected.
            }
        }
    }

    @Test
    fun allowsLoopbackRelayOnlyForExplicitDebugUsbReverseQr() {
        val rawPayload = "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
            "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
            "&runtime_key_fingerprint=fp-1&relay_host=127.0.0.1" +
            "&relay_port=443&relay_id=relay-1&relay_secret=secret-1" +
            "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1" +
            "&relay_scope=usb_reverse"

        try {
            RuntimePairingPayloadParser.parse(rawPayload)
            fail("Expected release/default parser policy to reject loopback relay")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        val payload = RuntimePairingPayloadParser.parse(
            rawValue = rawPayload,
            allowDebugLoopbackRelay = true,
        )

        assertEquals("127.0.0.1", payload.relayHost)
        assertEquals("usb_reverse", payload.relayScope)
    }

    @Test
    fun rejectsInvalidEndpointHintWhenProvided() {
        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1&host=192.168.1.10&port=70000"
            )
            fail("Expected invalid port to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1&host=192.168.1.10"
            )
            fail("Expected incomplete endpoint hint to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun rejectsIncompleteRelayRouteWhenProvided() {
        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1" +
                    "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                    "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
            )
            fail("Expected missing relay secret to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1" +
                    "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                    "&relay_secret=secret-1&relay_nonce=nonce-route-1"
            )
            fail("Expected missing relay expiration to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1" +
                    "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                    "&relay_secret=secret-1&relay_expires_at=4102444800000"
            )
            fail("Expected missing relay nonce to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1" +
                    "&relay_host=relay.example.test&relay_port=443"
            )
            fail("Expected missing relay id to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1&route_token=route-1" +
                    "&relay_secret=secret-1"
            )
            fail("Expected relay secret without relay host/port to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1&relay_id=relay-1"
            )
            fail("Expected relay id without relay host/port to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1" +
                    "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                    "&relay_expires_at=not-a-number"
            )
            fail("Expected invalid relay expiration to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1" +
                    "&relay_host=relay.example.test&relay_port=443&relay_id=relay-1" +
                    "&relay_nonce="
            )
            fail("Expected blank relay nonce to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1" +
                    "&relay_host=relay.example.test&relay_port=443&relay_id=relay%201"
            )
            fail("Expected relay id with whitespace to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }

        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&mac_device_id=mac-1&fingerprint=fp-1&route_token=route-1" +
                    "&relay_host=relay.example.test&relay_port=443&relay_secret=secret-1" +
                    "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
            )
            fail("Expected route token not to be accepted as relay id")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    @Test
    fun rejectsRelayScopeWithoutRelayRouteMaterial() {
        try {
            RuntimePairingPayloadParser.parse(
                "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                    "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                    "&runtime_key_fingerprint=fp-1&runtime_public_key=public-key-1&route_token=route-1" +
                    "&p2p_class=p2p_rendezvous&p2p_record_id=p2p-record-1" +
                    "&p2p_encrypted_body=opaque-candidate-1&p2p_expires_at=4102444800000" +
                    "&p2p_anti_replay_nonce=nonce-p2p-1&p2p_protocol_version=1" +
                    "&relay_scope=remote"
            )
            fail("Expected stray relay scope on P2P QR to throw")
        } catch (error: IllegalArgumentException) {
            assertEquals("Relay scope requires relay route material", error.message)
        }

        val diagnostic = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&host=192.168.1.10&port=43170" +
                "&route_scope=local_diagnostic",
            allowDiagnosticLocalDirectEndpoint = true,
        )

        assertEquals("192.168.1.10", diagnostic.host)
        assertEquals(43170, diagnostic.port)
        assertEquals("local_diagnostic", diagnostic.relayScope)
    }

    @Test
    fun rejectsUnsupportedQrPayload() {
        try {
            RuntimePairingPayloadParser.parse("https://example.com/pair?code=123456")
            fail("Expected invalid QR payload to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }

    private fun sharedProtocolFixture(name: String): String {
        val fixture = generateSequence(File(System.getProperty("user.dir") ?: ".")) { it.parentFile }
            .map { File(it, "shared/protocol/fixtures/$name") }
            .firstOrNull { it.isFile }
            ?: error("Missing shared protocol fixture: $name")
        return fixture.readText().trim()
    }

    private fun fieldValue(field: String): String {
        return when (field) {
            "pairing_nonce" -> "nonce-1"
            "runtime_device_id" -> "runtime-1"
            "runtime_key_fingerprint" -> "fp-1"
            "runtime_public_key" -> "public-key-1"
            "route_token" -> "route-1"
            "relay_id" -> "relay-1"
            "relay_secret" -> "secret-1"
            "relay_nonce" -> "nonce-route-1"
            "relay_scope" -> "remote"
            "p2p_class" -> "p2p_rendezvous"
            "p2p_record_id" -> "p2p-record-1"
            "p2p_encrypted_body" -> "opaque-candidate-1"
            "p2p_expires_at" -> "4102444800000"
            "p2p_anti_replay_nonce" -> "nonce-p2p-1"
            "p2p_protocol_version" -> "1"
            else -> error("Unexpected test field: $field")
        }
    }
}
