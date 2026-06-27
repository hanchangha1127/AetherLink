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
                "&relay_secret=secret%20with%20symbols%20+%20/%20%3D" +
                "&relay_expires_at=4102444800000&relay_nonce=nonce-route-1"
        )

        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("abc+def/ghi=", payload.runtimePublicKeyBase64)
        assertEquals("secret with symbols + / =", payload.relaySecret)
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
    fun allowsPrivateOverlayRelayHostsOnlyWithExplicitScope() {
        listOf(
            "10.0.0.5",
            "100.64.1.5",
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
                    "&mac_device_id=mac-1&fingerprint=fp-1&route_token=relay%201" +
                    "&relay_host=relay.example.test&relay_port=443"
            )
            fail("Expected route-token fallback relay id with whitespace to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
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
}
