package com.localagentbridge.android.core.transport

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import java.nio.charset.StandardCharsets

class BonjourDiscoveryTest {
    @Test
    fun bonjourTxtRouteTokenRejectsWhitespaceMutationsInsteadOfTrimming() {
        listOf(
            " route-token-1",
            "route-token-1 ",
            "route token 1",
            "route-token-1\n",
        ).forEach { routeToken ->
            assertNull(
                "Expected whitespace-mutated route_token to be rejected: $routeToken",
                mapOf("route_token" to routeToken.txtBytes()).toBonjourTxtMetadataOrNull(),
            )
        }
    }

    @Test
    fun bonjourTxtRouteTokenRejectsOversizedAndMalformedValues() {
        assertNull(
            mapOf("route_token" to "r".repeat(161).txtBytes()).toBonjourTxtMetadataOrNull(),
        )
        assertNull(
            mapOf("route_token" to byteArrayOf(0xC3.toByte(), 0x28)).toBonjourTxtMetadataOrNull(),
        )
    }

    @Test
    fun bonjourTxtMetadataRejectsForbiddenDiscoveryMaterial() {
        listOf(
            mapOf("backend_url" to "redacted".txtBytes()),
            mapOf("app" to "https://provider.example.test/v1/models".txtBytes()),
            mapOf("version" to "provider=ollama".txtBytes()),
            mapOf("route_token" to "relay_secret=secret-1".txtBytes()),
            mapOf("fingerprint" to "chat.send".txtBytes()),
        ).forEach { attributes ->
            assertNull(
                "Expected forbidden discovery TXT material to reject metadata: $attributes",
                attributes.toBonjourTxtMetadataOrNull(),
            )
        }
    }

    @Test
    fun bonjourTxtMetadataKeepsSafeDisplayAppAndVersionOnly() {
        val metadata = mapOf(
            "route_token" to "route-token-1".txtBytes(),
            "app" to " AetherLink Runtime ".txtBytes(),
            "version" to " 1 ".txtBytes(),
        ).toBonjourTxtMetadataOrNull()

        assertNotNull(metadata)
        requireNotNull(metadata)
        assertEquals("route-token-1", metadata.routeToken)
        assertEquals("AetherLink Runtime", metadata.app)
        assertEquals("1", metadata.version)
    }

    @Test
    fun bonjourTxtMetadataSanitizesLegacyIdentityHints() {
        val metadata = mapOf(
            "device_id" to "runtime-1".txtBytes(),
            "fingerprint" to "fingerprint-1".txtBytes(),
        ).toBonjourTxtMetadataOrNull()

        assertNotNull(metadata)
        requireNotNull(metadata)
        assertEquals("runtime-1", metadata.deviceId)
        assertEquals("fingerprint-1", metadata.fingerprint)
        assertNull(
            mapOf("device_id" to " runtime-1".txtBytes()).toBonjourTxtMetadataOrNull(),
        )
        assertNull(
            mapOf("fingerprint" to "fingerprint 1".txtBytes()).toBonjourTxtMetadataOrNull(),
        )
    }

    private fun String.txtBytes(): ByteArray = toByteArray(StandardCharsets.UTF_8)
}
