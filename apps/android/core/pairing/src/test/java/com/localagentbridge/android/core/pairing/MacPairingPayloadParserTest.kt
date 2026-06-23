package com.localagentbridge.android.core.pairing

import org.junit.Assert.assertEquals
import org.junit.Assert.fail
import org.junit.Test

class MacPairingPayloadParserTest {
    @Test
    fun parsesAetherLinkQrPayload() {
        val payload = MacPairingPayloadParser.parse(
            "aetherlink://pair?version=1&pairing_nonce=nonce-1&pairing_code=123456" +
                "&mac_device_id=mac-1&mac_name=AetherLink+Mac&fingerprint=fp-1" +
                "&host=192.168.1.10&port=43170&service_type=_aetherlink._tcp.local."
        )

        assertEquals("nonce-1", payload.pairingNonce)
        assertEquals("123456", payload.pairingCode)
        assertEquals("mac-1", payload.macDeviceId)
        assertEquals("AetherLink Mac", payload.macName)
        assertEquals("fp-1", payload.fingerprint)
        assertEquals("192.168.1.10", payload.host)
        assertEquals(43170, payload.port)
        assertEquals("_aetherlink._tcp.local.", payload.serviceType)
    }

    @Test
    fun rejectsUnsupportedQrPayload() {
        try {
            MacPairingPayloadParser.parse("https://example.com/pair?code=123456")
            fail("Expected invalid QR payload to throw")
        } catch (_: IllegalArgumentException) {
            // Expected.
        }
    }
}
