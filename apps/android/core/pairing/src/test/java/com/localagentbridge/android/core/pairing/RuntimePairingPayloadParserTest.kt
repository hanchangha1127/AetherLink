package com.localagentbridge.android.core.pairing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.fail
import org.junit.Test

class RuntimePairingPayloadParserTest {
    @Test
    fun parsesAetherLinkQrPayload() {
        val payload = RuntimePairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&runtime_device_id=runtime-1&runtime_name=AetherLink+Runtime" +
                "&runtime_key_fingerprint=fp-1&route_token=route-1" +
                "&runtime_host=192.168.1.10&runtime_port=43170&service_type=_aetherlink._tcp.local."
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("runtime-1", payload.runtimeDeviceId)
        assertEquals("AetherLink Runtime", payload.runtimeName)
        assertEquals("fp-1", payload.fingerprint)
        assertEquals("route-1", payload.routeToken)
        assertEquals("192.168.1.10", payload.host)
        assertEquals(43170, payload.port)
        assertEquals("_aetherlink._tcp.local.", payload.serviceType)
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
            "aetherlink://pair?nonce=nonce-1&code=123456" +
                "&device_id=mac-1&name=AetherLink+Mac&cert_fingerprint=fp-1" +
                "&runtime_host=10.0.2.2&runtime_port=43170"
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
    fun rejectsUnsupportedQrPayload() {
        try {
            RuntimePairingPayloadParser.parse("https://example.com/pair?code=123456")
            fail("Expected invalid QR payload to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }
}
