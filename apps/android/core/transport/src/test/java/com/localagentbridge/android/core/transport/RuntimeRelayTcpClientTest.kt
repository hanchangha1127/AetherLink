package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.ProtocolCodec
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import java.io.ByteArrayInputStream

class RuntimeRelayTcpClientTest {
    @Test
    fun relayFrameCryptorRoundTripsProtocolFrameBodies() {
        val codec = ProtocolCodec()
        val clientCryptor = RelayFrameBodyCryptor("relay-secret-1")
        val runtimeCryptor = RelayFrameBodyCryptor("relay-secret-1")
        val clientBody = """{"type":"models.list","request_id":"request-1","payload":{}}""".encodeToByteArray()
        val encryptedClientBody = clientCryptor.encryptClientFrameBody(clientBody)
        val decryptedClientBody = runtimeCryptor.decryptClientFrameBodyForTest(encryptedClientBody)
        val runtimeBody = """{"type":"runtime.health","request_id":"request-2","payload":{}}""".encodeToByteArray()
        val encryptedRuntimeBody = runtimeCryptor.encryptRuntimeFrameBodyForTest(runtimeBody)
        val framedRuntimeBody = codec.readFrameBody(ByteArrayInputStream(codec.encodeFrameBody(encryptedRuntimeBody)))
        val decryptedRuntimeBody = clientCryptor.decryptRuntimeFrameBody(framedRuntimeBody)

        assertFalse(clientBody.contentEquals(encryptedClientBody))
        assertEquals("request-1", codec.decode(decryptedClientBody).requestId)
        assertFalse(runtimeBody.contentEquals(encryptedRuntimeBody))
        assertEquals("request-2", codec.decode(decryptedRuntimeBody).requestId)
    }

    @Test
    fun relayFrameCryptorMatchesSharedCiphertextVectors() {
        val clientCryptor = RelayFrameBodyCryptor("relay-secret-vector")
        val runtimeCryptor = RelayFrameBodyCryptor("relay-secret-vector")
        val clientBody = """{"type":"models.list","request_id":"vector-1","payload":{}}""".encodeToByteArray()
        val runtimeBody = """{"type":"runtime.health","request_id":"vector-2","payload":{}}""".encodeToByteArray()

        assertEquals(
            "445732376c183bb714bed5bb30570b16dd468e63392137eabc0259c1cc49f1c79c7babcf4ded6e05c91707bf1168823708c670b888a3319140063f1900d799afa5ad81bfa7df52c96f88c1",
            clientCryptor.encryptClientFrameBody(clientBody).toHex(),
        )
        assertEquals(
            "ec6f782db28fe4e5bc8a0bfd9c8944051dbaeceea6bd1d3ec34b1ef9cf265f728a76ef7f24dcad7daaa516cb1f756d24d686df0b05806e436524baf6f4d27f6fb86e25b5eae90f83ccf30718cf68",
            runtimeCryptor.encryptRuntimeFrameBodyForTest(runtimeBody).toHex(),
        )
    }
}

private fun ByteArray.toHex(): String = joinToString(separator = "") { "%02x".format(it) }
