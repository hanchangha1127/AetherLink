package com.localagentbridge.android

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PairingQrScanResultTest {
    @Test
    fun validCompactRemoteRouteQrReturnsValid() {
        val rawUri = sharedProtocolFixture("macos-compact-relay-pairing-uri.txt")

        assertEquals(
            PairingQrScanResult.Valid(rawUri),
            listOf(rawUri).aetherLinkPairingScanResultOrNull(),
        )
    }

    @Test
    fun validCompactPrivateOverlayRouteQrReturnsValid() {
        val rawUri = sharedProtocolFixture("macos-compact-private-overlay-pairing-uri.txt")

        assertEquals(
            PairingQrScanResult.Valid(rawUri),
            listOf(rawUri).aetherLinkPairingScanResultOrNull(),
        )
    }

    @Test
    fun identityOnlyPairQrIsInvalidWhenRemoteRouteIsRequired() {
        val identityOnlyPairQr = "aetherlink://pair?v=1&n=nonce-identity&c=123456" +
            "&rid=runtime-identity&rn=AetherLink%20Runtime&rf=fp-identity" +
            "&rk=runtime-public-key&rt=route-token-identity"

        assertEquals(
            PairingQrScanResult.InvalidPairingQr,
            listOf(identityOnlyPairQr).aetherLinkPairingScanResultOrNull(requireRemoteRoute = true),
        )
    }

    @Test
    fun compactLocalDiagnosticQrIsValidOnlyWhenRemoteRouteIsNotRequired() {
        val rawUri = "aetherlink://pair?v=1&n=nonce-local&c=123456" +
            "&rid=runtime-local&rn=AetherLink%20Runtime&rf=fp-local" +
            "&rk=runtime-public-key&rt=route-token-local" +
            "&h=192.168.1.44&p=43170&rsc=local_diagnostic"

        assertEquals(
            PairingQrScanResult.InvalidPairingQr,
            listOf(rawUri).aetherLinkPairingScanResultOrNull(requireRemoteRoute = true),
        )
        assertEquals(
            PairingQrScanResult.Valid(rawUri),
            listOf(rawUri).aetherLinkPairingScanResultOrNull(requireRemoteRoute = false),
        )
    }

    @Test
    fun nonAetherLinkQrReturnsUnsupported() {
        assertEquals(
            PairingQrScanResult.UnsupportedQr,
            listOf("https://example.test/pair?code=123456").aetherLinkPairingScanResultOrNull(),
        )
    }

    @Test
    fun blankAndNullFrameValuesAreIgnored() {
        assertNull(
            listOf(null, "", " \n\t ").aetherLinkPairingScanResultOrNull(),
        )
    }

    @Test
    fun mixedFrameBatchPrioritizesValidPairingQr() {
        val validQr = sharedProtocolFixture("macos-compact-relay-pairing-uri.txt")
        val invalidPairQr = "aetherlink://pair?pairing_code=123456"

        assertEquals(
            PairingQrScanResult.Valid(validQr),
            listOf(
                "https://example.test/pair?code=123456",
                invalidPairQr,
                validQr,
            ).aetherLinkPairingScanResultOrNull(),
        )
    }

    @Test
    fun invalidPairingQrBeatsUnsupportedQrWhenNoValidQrExists() {
        val invalidPairQr = "aetherlink://pair?pairing_code=123456"

        assertEquals(
            PairingQrScanResult.InvalidPairingQr,
            listOf(
                "https://example.test/pair?code=123456",
                invalidPairQr,
            ).aetherLinkPairingScanResultOrNull(),
        )
    }

    private fun sharedProtocolFixture(name: String): String {
        val fixture = generateSequence(File(System.getProperty("user.dir") ?: ".")) { it.parentFile }
            .map { File(it, "shared/protocol/fixtures/$name") }
            .firstOrNull { it.isFile }
            ?: error("Missing shared protocol fixture: $name")
        return fixture.readText().trim()
    }
}
