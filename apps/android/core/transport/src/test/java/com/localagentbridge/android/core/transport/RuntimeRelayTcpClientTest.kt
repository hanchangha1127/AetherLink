package com.localagentbridge.android.core.transport

import com.localagentbridge.android.core.protocol.MessageType
import com.localagentbridge.android.core.protocol.PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationAuthorization
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationChallenge
import com.localagentbridge.android.core.protocol.PairedClientRelayRegistrationProof
import com.localagentbridge.android.core.protocol.ProtocolCodec
import com.localagentbridge.android.core.protocol.ProtocolEnvelope
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigInteger
import java.net.ServerSocket
import java.net.Socket
import java.security.AlgorithmParameters
import java.security.KeyFactory
import java.security.Signature
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECParameterSpec
import java.security.spec.ECPrivateKeySpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread
import kotlin.system.measureTimeMillis

class RuntimeRelayTcpClientTest {
    @Test
    fun relaySessionCryptoMatchesP256ScalarOneAndTwoVectors() {
        val clientKeyPair = fixedClientKeyPair()
        val runtimeKeyPair = fixedRuntimeKeyPair()
        val clientSession = vectorSession(clientKeyPair)
        val runtimeSession = vectorSession(runtimeKeyPair)

        assertEquals(
            "44ed84bb0519061c52e320518660a2d0fbc0a29fdc3b7a62a14e151a2c4e6219",
            clientSession.bindingId,
        )
        assertEquals(clientSession.bindingId, runtimeSession.bindingId)
        assertEquals(
            "dc22099339654d46ec3a06d23183311c7d9e503200bdbeeb969179b02a5e498a",
            clientSession.proof("client"),
        )
        assertEquals(
            "b5742c284b726d42f692e2cbc2bbb0ceb7c7f2183d2c24aebedb48fd102d346c",
            clientSession.proof("runtime"),
        )
        assertEquals(clientSession.proof("client"), runtimeSession.proof("client"))
        assertEquals(clientSession.proof("runtime"), runtimeSession.proof("runtime"))
    }

    @Test
    fun relaySessionCryptoBindsRouteNonceIntoBindingAndTrafficKeys() {
        val baseSession = vectorSession(fixedClientKeyPair())
        val changedNonceSession = vectorSession(
            localKeyPair = fixedClientKeyPair(),
            routeNonce = "different-relay-nonce",
        )
        val ciphertext = baseSession.frameCryptor()
            .encryptRuntimeFrameBodyForTest("route-bound".encodeToByteArray())

        assertFalse(baseSession.bindingId == changedNonceSession.bindingId)
        assertThrows(Exception::class.java) {
            changedNonceSession.frameCryptor().decryptRuntimeFrameBody(ciphertext)
        }
    }

    @Test
    fun relayFrameV2MatchesEpochBoundaryVectors() {
        val session = vectorSession(fixedClientKeyPair())
        val plaintext = "vector-frame".encodeToByteArray()

        assertEquals(
            "d0b1c8cd2796958751e7a24521ef37b52b91f896c5b109696e1c8b8f",
            session.frameCryptor().encryptClientFrameBody(plaintext).toHex(),
        )
        assertEquals(
            "331d623bf4807dfe9187a5a4d77bb36ce2aa0535ce7131096652e7af",
            session.frameCryptor(clientFrameIndex = 65_535).encryptClientFrameBody(plaintext).toHex(),
        )
        assertEquals(
            "b3d81a0ea9c7ad997f764b8e838b6f8e0394cea9d9b0a3837adcdc1f",
            session.frameCryptor(clientFrameIndex = 65_536).encryptClientFrameBody(plaintext).toHex(),
        )
        assertEquals(
            "58ff0974730739e74b58e1b68f32b0ec78e7eb8da70c358c22f0b762",
            session.frameCryptor().encryptRuntimeFrameBodyForTest(plaintext).toHex(),
        )
        assertFalse(
            session.frameCryptor().encryptClientFrameBody(plaintext)
                .contentEquals(session.frameCryptor().encryptRuntimeFrameBodyForTest(plaintext)),
        )
    }

    @Test
    fun relayFrameV2RejectsReplayWithoutAdvancingAfterFailedAuthentication() {
        val session = vectorSession(fixedClientKeyPair())
        val sender = session.frameCryptor()
        val receiver = session.frameCryptor()
        val first = sender.encryptRuntimeFrameBodyForTest("first".encodeToByteArray())
        val tampered = first.copyOf().also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }

        assertThrows(Exception::class.java) {
            receiver.decryptRuntimeFrameBody(tampered)
        }
        assertEquals("first", receiver.decryptRuntimeFrameBody(first).decodeToString())
        assertThrows(Exception::class.java) {
            receiver.decryptRuntimeFrameBody(first)
        }
    }

    @Test
    fun relayFrameV2RejectsExhaustedCounterBeforeCrypt() {
        val cryptor = vectorSession(fixedClientKeyPair()).frameCryptor(
            clientFrameIndex = Long.MAX_VALUE - 1L,
        )

        cryptor.encryptClientFrameBody("last-frame".encodeToByteArray())
        val error = assertThrows(IllegalArgumentException::class.java) {
            cryptor.encryptClientFrameBody("must-not-encrypt".encodeToByteArray())
        }

        assertEquals("Relay frame index is exhausted", error.message)
    }

    @Test
    fun relayEphemeralKeyRequiresCanonicalOnCurveP256Point() {
        assertEquals(P256_GENERATOR, P256_GENERATOR.requireEphemeralKey())
        listOf(
            P256_GENERATOR.uppercase(),
            "03" + P256_GENERATOR.drop(2),
            "04" + "00".repeat(64),
            P256_GENERATOR.dropLast(2),
        ).forEach { invalidKey ->
            assertThrows(IllegalArgumentException::class.java) {
                invalidKey.requireEphemeralKey()
            }
        }
    }

    @Test
    fun plaintextRelayPreservesLegacyRegistrationAndFrames() = runBlocking {
        val codec = ProtocolCodec()
        val server = ServerSocket(0)
        val receivedHandshake = CompletableFuture<String>()
        val receivedRequest = CompletableFuture<ProtocolEnvelope>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    receivedHandshake.complete(socket.getInputStream().readAsciiLine())
                    socket.getOutputStream().write("AETHERLINK_RELAY ready\n".encodeToByteArray())
                    socket.getOutputStream().flush()
                    receivedRequest.complete(codec.readFrame(socket.getInputStream()))
                }
            }.onFailure(receivedRequest::completeExceptionally)
        }
        val channel = RuntimeRelayTcpClient().connect(legacyRoute(server.localPort), timeoutMillis = 1_000)

        try {
            channel.send(ProtocolEnvelope(type = MessageType.ModelsList, requestId = "legacy-request"))
            assertEquals("AETHERLINK_RELAY client relay-legacy", receivedHandshake.get(2, TimeUnit.SECONDS))
            assertEquals("legacy-request", receivedRequest.get(2, TimeUnit.SECONDS).requestId)
            assertNull(channel.transportSecurityContext)
        } finally {
            channel.close()
            server.close()
            serverThread.join(1_500)
        }
    }

    @Test
    fun initialStrictRelayWithNullGenerationUsesExactV2HandshakeAndEncryptedFrames() = runBlocking {
        val codec = ProtocolCodec()
        val relaySecret = "relay-channel-secret"
        val routeNonce = "relay-channel-nonce"
        val server = ServerSocket(0)
        val binding = CompletableFuture<String>()
        val encryptedRequest = CompletableFuture<ByteArray>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val session = completeStrictServerHandshake(
                        socket = socket,
                        relayId = "relay-channel",
                        relaySecret = relaySecret,
                        routeNonce = routeNonce,
                    )
                    binding.complete(session.bindingId)
                    val cryptor = session.frameCryptor()
                    val requestCiphertext = codec.readFrameBody(socket.getInputStream())
                    encryptedRequest.complete(requestCiphertext)
                    val request = codec.decode(cryptor.decryptClientFrameBodyForTest(requestCiphertext))
                    assertEquals("client-request", request.requestId)

                    val response = ProtocolEnvelope(
                        type = MessageType.RuntimeHealth,
                        requestId = "runtime-response",
                    )
                    val responseCiphertext = cryptor.encryptRuntimeFrameBodyForTest(codec.encodeBody(response))
                    socket.getOutputStream().write(codec.encodeFrameBody(responseCiphertext))
                    socket.getOutputStream().flush()
                }
            }.onFailure { failure ->
                binding.completeExceptionally(failure)
                encryptedRequest.completeExceptionally(failure)
            }
        }
        val route = strictRoute(server.localPort, "relay-channel", relaySecret, routeNonce)
        assertNull(route.ticketGeneration)
        val channel = RuntimeRelayTcpClient().connect(
            route,
            timeoutMillis = 1_000,
        )

        try {
            channel.send(ProtocolEnvelope(type = MessageType.ModelsList, requestId = "client-request"))
            val response = channel.receive()
            assertEquals(binding.get(2, TimeUnit.SECONDS), channel.transportSecurityContext?.bindingId)
            assertEquals("runtime-response", response.requestId)
            assertFalse(encryptedRequest.get(2, TimeUnit.SECONDS).containsBytes("client-request".encodeToByteArray()))
        } finally {
            channel.close()
            server.close()
            serverThread.join(1_500)
        }
    }

    @Test
    fun pairedRelayAuthorizesMatchingChallengeThenCompletesStrictCrypto() = runBlocking {
        val routeNonce = "paired-route-nonce"
        val server = ServerSocket(0)
        val sentChallenge = CompletableFuture<PairedClientRelayRegistrationChallenge>()
        val expectedProofLine = CompletableFuture<String>()
        val receivedProofLine = CompletableFuture<String>()
        val authorizerCalls = AtomicInteger()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val registration = assertStrictRegistration(
                        socket.getInputStream().readAsciiLine(),
                        PAIRED_RELAY_ID,
                    )
                    val challenge = matchingPairedChallenge(registration, routeNonce)
                    sentChallenge.complete(challenge)
                    socket.getOutputStream().write(challengeControlLine(challenge).encodeToByteArray())
                    socket.getOutputStream().flush()
                    receivedProofLine.complete(socket.getInputStream().readAsciiLine())
                    completeStrictServerHandshakeAfterRegistration(
                        socket = socket,
                        registration = registration,
                        relayId = PAIRED_RELAY_ID,
                        relaySecret = PAIRED_RELAY_SECRET,
                        routeNonce = routeNonce,
                    )
                }
            }.onFailure { failure ->
                receivedProofLine.completeExceptionally(failure)
            }
        }
        val authorizer = RelayClientRegistrationAuthorizer { challenge ->
            authorizerCalls.incrementAndGet()
            assertEquals(sentChallenge.get(2, TimeUnit.SECONDS), challenge)
            signPairedChallenge(challenge).also { proof ->
                assertTrue(verifyPairedChallenge(challenge, proof))
                expectedProofLine.complete(
                    "AETHERLINK_RELAY client_registration_proof crypto=2 " +
                        "challenge=${challenge.challenge} " +
                        "client_public_key=${proof.clientPublicKeyBase64} " +
                        "client_signature=${proof.clientSignatureBase64}",
                )
            }
        }
        val route = pairedRoute(server.localPort, routeNonce = routeNonce)
        val channel = RuntimeRelayTcpClient(clientRegistrationAuthorizer = authorizer)
            .connect(route, timeoutMillis = 1_000)

        try {
            assertEquals(1, authorizerCalls.get())
            assertEquals(
                expectedProofLine.get(2, TimeUnit.SECONDS),
                receivedProofLine.get(2, TimeUnit.SECONDS),
            )
            assertTrue(channel.transportSecurityContext?.bindingId?.matches(LOWERCASE_DIGEST) == true)
        } finally {
            channel.close()
            server.close()
            serverThread.join(1_500)
        }
    }

    @Test
    fun pairedRouteRejectsMissingChallengeAsDowngradeBeforeAuthorizer() {
        val authorizerCalls = AtomicInteger()
        val server = ServerSocket(0)
        val observedClose = CompletableFuture<Boolean>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    assertStrictRegistration(socket.getInputStream().readAsciiLine(), PAIRED_RELAY_ID)
                    socket.getOutputStream().write(strictReadyLine(P256_TWO_G).encodeToByteArray())
                    socket.getOutputStream().flush()
                    observedClose.complete(socket.getInputStream().read() == -1)
                }
            }.onFailure(observedClose::completeExceptionally)
        }

        assertThrows(Exception::class.java) {
            runBlocking {
                RuntimeRelayTcpClient(
                    clientRegistrationAuthorizer = RelayClientRegistrationAuthorizer {
                        authorizerCalls.incrementAndGet()
                        signPairedChallenge(it)
                    },
                ).connect(pairedRoute(server.localPort), timeoutMillis = 1_000)
            }
        }
        assertEquals(0, authorizerCalls.get())
        assertTrue(observedClose.get(2, TimeUnit.SECONDS))
        server.close()
        serverThread.join(1_500)
    }

    @Test
    fun pairedRouteRejectsChallengeMismatchesBeforeAuthorizer() {
        val mismatches = listOf<Pair<String, (PairedClientRelayRegistrationChallenge) -> PairedClientRelayRegistrationChallenge>>(
            "generation" to { it.copy(ticketGeneration = it.ticketGeneration + 1) },
            "relay nonce" to { it.copy(relayNonce = "different-route-nonce") },
            "runtime fingerprint" to { it.copy(runtimeKeyFingerprint = "a".repeat(64)) },
            "session nonce" to { it.copy(sessionNonce = RUNTIME_SESSION_NONCE) },
            "ephemeral key" to { it.copy(ephemeralKey = P256_TWO_G) },
            "relay expiry" to { it.copy(relayExpiresAtEpochMillis = Long.MAX_VALUE - 1) },
            "challenge expiry" to { it.copy(challengeExpiresAtEpochMillis = 1) },
        )

        mismatches.forEach { (name, mutate) ->
            assertPairedChallengeRejectedBeforeAuthorizer(name, mutate)
        }
    }

    @Test
    fun pairedRouteRejectsMatchingChallengeWhenAuthorizerIsMissing() {
        val server = ServerSocket(0)
        val observedClose = CompletableFuture<Boolean>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val registration = assertStrictRegistration(
                        socket.getInputStream().readAsciiLine(),
                        PAIRED_RELAY_ID,
                    )
                    socket.getOutputStream().write(
                        challengeControlLine(matchingPairedChallenge(registration)).encodeToByteArray(),
                    )
                    socket.getOutputStream().flush()
                    observedClose.complete(socket.getInputStream().read() == -1)
                }
            }.onFailure(observedClose::completeExceptionally)
        }

        assertThrows(Exception::class.java) {
            runBlocking {
                RuntimeRelayTcpClient().connect(pairedRoute(server.localPort), timeoutMillis = 1_000)
            }
        }
        assertTrue(observedClose.get(2, TimeUnit.SECONDS))
        server.close()
        serverThread.join(1_500)
    }

    @Test
    fun strictRelayRejectsLegacyAndNonCanonicalReadyWithoutV1Fallback() {
        val invalidReadyLines = listOf(
            "AETHERLINK_RELAY ready",
            "AETHERLINK_RELAY ready peer_session_nonce=$RUNTIME_SESSION_NONCE",
            "AETHERLINK_RELAY ready crypto=1 peer_session_nonce=$RUNTIME_SESSION_NONCE " +
                "peer_ephemeral_key=$P256_TWO_G",
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=${RUNTIME_SESSION_NONCE.uppercase()} " +
                "peer_ephemeral_key=$P256_TWO_G",
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=$RUNTIME_SESSION_NONCE " +
                "peer_ephemeral_key=${P256_TWO_G.uppercase()}",
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=$RUNTIME_SESSION_NONCE " +
                "peer_ephemeral_key=${"04" + "00".repeat(64)}",
            "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=$RUNTIME_SESSION_NONCE " +
                "peer_ephemeral_key=$P256_TWO_G\r",
        )

        invalidReadyLines.forEachIndexed { index, readyLine ->
            val server = ServerSocket(0)
            val registration = CompletableFuture<String>()
            val serverThread = thread(start = true, isDaemon = true) {
                runCatching {
                    server.accept().use { socket ->
                        registration.complete(socket.getInputStream().readAsciiLine())
                        socket.getOutputStream().write("$readyLine\n".encodeToByteArray())
                        socket.getOutputStream().flush()
                    }
                }.onFailure(registration::completeExceptionally)
            }

            assertThrows(Exception::class.java) {
                runBlocking {
                    RuntimeRelayTcpClient().connect(
                        strictRoute(
                            server.localPort,
                            relayId = "relay-invalid-$index",
                            relaySecret = "relay-secret",
                            routeNonce = "route-$index",
                        ),
                        timeoutMillis = 1_000,
                    )
                }
            }
            assertStrictRegistration(registration.get(2, TimeUnit.SECONDS), "relay-invalid-$index")
            server.close()
            serverThread.join(1_500)
        }
    }

    @Test
    fun strictRelayRejectsInvalidRuntimeConfirmationAndClosesSocket() {
        val relaySecret = "relay-confirmation-secret"
        val routeNonce = "relay-confirmation-route"
        val server = ServerSocket(0)
        val observedClientClose = CompletableFuture<Boolean>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val registration = assertStrictRegistration(
                        socket.getInputStream().readAsciiLine(),
                        "relay-confirmation",
                    )
                    val runtimeKeyPair = fixedRuntimeKeyPair()
                    socket.getOutputStream().write(strictReadyLine(runtimeKeyPair.publicKeyHex).encodeToByteArray())
                    socket.getOutputStream().flush()
                    val session = RelaySessionCrypto.establish(
                        relaySecret = relaySecret,
                        relayId = "relay-confirmation",
                        routeNonce = routeNonce,
                        clientSessionNonce = registration.sessionNonce,
                        runtimeSessionNonce = RUNTIME_SESSION_NONCE,
                        clientEphemeralKey = registration.ephemeralKey,
                        runtimeEphemeralKey = runtimeKeyPair.publicKeyHex,
                        localEphemeralKeyPair = runtimeKeyPair,
                    )
                    assertEquals(session.controlLine("client"), socket.getInputStream().readAsciiLine())
                    val validRuntimeConfirmation = session.controlLine("runtime")
                    val replacement = if (validRuntimeConfirmation.last() == '0') '1' else '0'
                    socket.getOutputStream().write(
                        (validRuntimeConfirmation.dropLast(1) + replacement + "\n").encodeToByteArray(),
                    )
                    socket.getOutputStream().flush()
                    observedClientClose.complete(socket.getInputStream().read() == -1)
                }
            }.onFailure(observedClientClose::completeExceptionally)
        }

        assertThrows(Exception::class.java) {
            runBlocking {
                RuntimeRelayTcpClient().connect(
                    strictRoute(server.localPort, "relay-confirmation", relaySecret, routeNonce),
                    timeoutMillis = 1_000,
                )
            }
        }
        assertTrue(observedClientClose.get(2, TimeUnit.SECONDS))
        server.close()
        serverThread.join(1_500)
    }

    @Test
    fun strictRelayAuthenticationFailureClosesTransport() = runBlocking {
        val server = ServerSocket(0)
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val session = completeStrictServerHandshake(
                        socket = socket,
                        relayId = "relay-auth-failure",
                        relaySecret = "relay-secret",
                        routeNonce = "route-auth-failure",
                    )
                    val ciphertext = session.frameCryptor()
                        .encryptRuntimeFrameBodyForTest(envelopeBody("runtime.health", "response"))
                        .also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }
                    socket.getOutputStream().write(ProtocolCodec().encodeFrameBody(ciphertext))
                    socket.getOutputStream().flush()
                    Thread.sleep(250)
                }
            }
        }
        val channel = RuntimeRelayTcpClient().connect(
            strictRoute(server.localPort, "relay-auth-failure", "relay-secret", "route-auth-failure"),
            timeoutMillis = 1_000,
        )

        assertThrows(Exception::class.java) { runBlocking { channel.receive() } }
        assertFalse(channel.isConnected)
        server.close()
        serverThread.join(1_500)
    }

    @Test
    fun relayClientSerializesStrictEncryptionWithConcurrentSends() = runBlocking {
        val frameCount = 48
        val codec = ProtocolCodec()
        val server = ServerSocket(0)
        val receivedRequestIds = CompletableFuture<List<String>>()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val session = completeStrictServerHandshake(
                        socket = socket,
                        relayId = "relay-concurrent",
                        relaySecret = "relay-concurrent-secret",
                        routeNonce = "relay-concurrent-route",
                    )
                    val cryptor = session.frameCryptor()
                    receivedRequestIds.complete(
                        (0 until frameCount).map {
                            codec.decode(
                                cryptor.decryptClientFrameBodyForTest(
                                    codec.readFrameBody(socket.getInputStream()),
                                ),
                            ).requestId
                        },
                    )
                }
            }.onFailure(receivedRequestIds::completeExceptionally)
        }
        val channel = RuntimeRelayTcpClient().connect(
            strictRoute(
                server.localPort,
                "relay-concurrent",
                "relay-concurrent-secret",
                "relay-concurrent-route",
            ),
            timeoutMillis = 1_000,
        )

        coroutineScope {
            (0 until frameCount).map { index ->
                async {
                    channel.send(ProtocolEnvelope(type = MessageType.ModelsList, requestId = "request-$index"))
                }
            }.awaitAll()
        }
        channel.close()

        val requestIds = receivedRequestIds.get(2, TimeUnit.SECONDS)
        assertEquals(frameCount, requestIds.size)
        assertEquals((0 until frameCount).map { "request-$it" }.toSet(), requestIds.toSet())
        server.close()
        serverThread.join(1_500)
    }

    @Test
    fun relayConnectTimesOutWhenReadyLineNeverArrives() {
        val server = ServerSocket(0)
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    socket.getInputStream().read()
                    Thread.sleep(1_000)
                }
            }
        }

        val elapsedMillis = measureTimeMillis {
            assertThrows(Exception::class.java) {
                runBlocking {
                    RuntimeRelayTcpClient().connect(legacyRoute(server.localPort), timeoutMillis = 150)
                }
            }
        }

        server.close()
        serverThread.join(1_500)
        assertTrue("Relay connect should not wait forever", elapsedMillis < 1_500)
    }

    private fun completeStrictServerHandshake(
        socket: Socket,
        relayId: String,
        relaySecret: String,
        routeNonce: String,
    ): RelaySessionCrypto {
        val registration = assertStrictRegistration(socket.getInputStream().readAsciiLine(), relayId)
        return completeStrictServerHandshakeAfterRegistration(
            socket = socket,
            registration = registration,
            relayId = relayId,
            relaySecret = relaySecret,
            routeNonce = routeNonce,
        )
    }

    private fun completeStrictServerHandshakeAfterRegistration(
        socket: Socket,
        registration: StrictRegistration,
        relayId: String,
        relaySecret: String,
        routeNonce: String,
    ): RelaySessionCrypto {
        val runtimeKeyPair = fixedRuntimeKeyPair()
        socket.getOutputStream().write(strictReadyLine(runtimeKeyPair.publicKeyHex).encodeToByteArray())
        socket.getOutputStream().flush()
        val session = RelaySessionCrypto.establish(
            relaySecret = relaySecret,
            relayId = relayId,
            routeNonce = routeNonce,
            clientSessionNonce = registration.sessionNonce,
            runtimeSessionNonce = RUNTIME_SESSION_NONCE,
            clientEphemeralKey = registration.ephemeralKey,
            runtimeEphemeralKey = runtimeKeyPair.publicKeyHex,
            localEphemeralKeyPair = runtimeKeyPair,
        )
        assertEquals(session.controlLine("client"), socket.getInputStream().readAsciiLine())
        socket.getOutputStream().write((session.controlLine("runtime") + "\n").encodeToByteArray())
        socket.getOutputStream().flush()
        return session
    }

    private fun assertPairedChallengeRejectedBeforeAuthorizer(
        name: String,
        mutate: (PairedClientRelayRegistrationChallenge) -> PairedClientRelayRegistrationChallenge,
    ) {
        val server = ServerSocket(0)
        val observedClose = CompletableFuture<Boolean>()
        val authorizerCalls = AtomicInteger()
        val serverThread = thread(start = true, isDaemon = true) {
            runCatching {
                server.accept().use { socket ->
                    val registration = assertStrictRegistration(
                        socket.getInputStream().readAsciiLine(),
                        PAIRED_RELAY_ID,
                    )
                    val challenge = mutate(matchingPairedChallenge(registration))
                    socket.getOutputStream().write(challengeControlLine(challenge).encodeToByteArray())
                    socket.getOutputStream().flush()
                    observedClose.complete(socket.getInputStream().read() == -1)
                }
            }.onFailure(observedClose::completeExceptionally)
        }

        assertThrows(name, Exception::class.java) {
            runBlocking {
                RuntimeRelayTcpClient(
                    clientRegistrationAuthorizer = RelayClientRegistrationAuthorizer {
                        authorizerCalls.incrementAndGet()
                        signPairedChallenge(it)
                    },
                ).connect(pairedRoute(server.localPort), timeoutMillis = 1_000)
            }
        }
        assertEquals("$name must fail before authorizer", 0, authorizerCalls.get())
        assertTrue("$name must close the relay socket", observedClose.get(2, TimeUnit.SECONDS))
        server.close()
        serverThread.join(1_500)
    }

    private fun matchingPairedChallenge(
        registration: StrictRegistration,
        routeNonce: String = PAIRED_ROUTE_NONCE,
    ) = PairedClientRelayRegistrationChallenge(
        relayId = PAIRED_RELAY_ID,
        relayExpiresAtEpochMillis = Long.MAX_VALUE,
        relayNonce = routeNonce,
        runtimeKeyFingerprint = RUNTIME_KEY_FINGERPRINT,
        clientKeyFingerprint = PairedClientRelayRegistrationAuthorization
            .clientKeyFingerprint(CLIENT_IDENTITY_PUBLIC_KEY),
        ticketGeneration = PAIRED_TICKET_GENERATION,
        sessionNonce = registration.sessionNonce,
        ephemeralKey = registration.ephemeralKey,
        challenge = PAIRED_CHALLENGE,
        challengeExpiresAtEpochMillis = Long.MAX_VALUE,
    )

    private fun challengeControlLine(challenge: PairedClientRelayRegistrationChallenge): String =
        PAIRED_CLIENT_RELAY_REGISTRATION_CHALLENGE_PREFIX +
            "{\"scheme\":\"${challenge.scheme}\"," +
            "\"protocol_version\":${challenge.protocolVersion}," +
            "\"role\":\"${challenge.role}\"," +
            "\"relay_id\":\"${challenge.relayId}\"," +
            "\"relay_expires_at\":${challenge.relayExpiresAtEpochMillis}," +
            "\"relay_nonce\":\"${challenge.relayNonce}\"," +
            "\"runtime_key_fingerprint\":\"${challenge.runtimeKeyFingerprint}\"," +
            "\"client_key_fingerprint\":\"${challenge.clientKeyFingerprint}\"," +
            "\"ticket_generation\":${challenge.ticketGeneration}," +
            "\"session_nonce\":\"${challenge.sessionNonce}\"," +
            "\"ephemeral_key\":\"${challenge.ephemeralKey}\"," +
            "\"challenge\":\"${challenge.challenge}\"," +
            "\"challenge_expires_at\":${challenge.challengeExpiresAtEpochMillis}}\n"

    private fun signPairedChallenge(
        challenge: PairedClientRelayRegistrationChallenge,
    ): PairedClientRelayRegistrationProof {
        val signer = Signature.getInstance("SHA256withECDSA")
        signer.initSign(fixedClientIdentityPrivateKey())
        signer.update(challenge.transcript())
        return PairedClientRelayRegistrationProof(
            clientPublicKeyBase64 = CLIENT_IDENTITY_PUBLIC_KEY,
            clientSignatureBase64 = Base64.getEncoder().encodeToString(signer.sign()),
        )
    }

    private fun verifyPairedChallenge(
        challenge: PairedClientRelayRegistrationChallenge,
        proof: PairedClientRelayRegistrationProof,
    ): Boolean {
        val verifier = Signature.getInstance("SHA256withECDSA")
        verifier.initVerify(
            KeyFactory.getInstance("EC").generatePublic(
                X509EncodedKeySpec(Base64.getDecoder().decode(proof.clientPublicKeyBase64)),
            ),
        )
        verifier.update(challenge.transcript())
        return verifier.verify(Base64.getDecoder().decode(proof.clientSignatureBase64))
    }

    private fun fixedClientIdentityPrivateKey() = KeyFactory.getInstance("EC").generatePrivate(
        ECPrivateKeySpec(BigInteger.valueOf(2L), p256Parameters()),
    )

    private fun p256Parameters(): ECParameterSpec = AlgorithmParameters.getInstance("EC").run {
        init(ECGenParameterSpec("secp256r1"))
        getParameterSpec(ECParameterSpec::class.java)
    }

    private fun assertStrictRegistration(line: String, relayId: String): StrictRegistration {
        val match = Regex(
            "AETHERLINK_RELAY client ${Regex.escape(relayId)} crypto=2 " +
                "session_nonce=([0-9a-f]{32}) ephemeral_key=([0-9a-f]{130})",
        ).matchEntire(line)
        assertTrue("Registration must be canonical strict-v2", match != null)
        return requireNotNull(match).let {
            StrictRegistration(
                sessionNonce = it.groupValues[1],
                ephemeralKey = it.groupValues[2].requireEphemeralKey(),
            )
        }
    }

    private fun vectorSession(
        localKeyPair: RelayEphemeralKeyPair,
        routeNonce: String = "relay-nonce-vector",
    ): RelaySessionCrypto {
        return RelaySessionCrypto.establish(
            relaySecret = "relay-secret-vector",
            relayId = "relay-vector",
            routeNonce = routeNonce,
            clientSessionNonce = CLIENT_SESSION_NONCE,
            runtimeSessionNonce = RUNTIME_SESSION_NONCE,
            clientEphemeralKey = P256_GENERATOR,
            runtimeEphemeralKey = P256_TWO_G,
            localEphemeralKeyPair = localKeyPair,
        )
    }

    private fun fixedClientKeyPair() = RelayEphemeralKeyPair.fromPrivateScalarForTest(
        privateScalar = BigInteger.ONE,
        publicKeyHex = P256_GENERATOR,
    )

    private fun fixedRuntimeKeyPair() = RelayEphemeralKeyPair.fromPrivateScalarForTest(
        privateScalar = BigInteger.valueOf(2L),
        publicKeyHex = P256_TWO_G,
    )

    private fun strictReadyLine(runtimeEphemeralKey: String): String =
        "AETHERLINK_RELAY ready crypto=2 peer_session_nonce=$RUNTIME_SESSION_NONCE " +
            "peer_ephemeral_key=$runtimeEphemeralKey\n"

    private fun legacyRoute(port: Int) = PreparedRemoteRuntimeRoute.Relay(
        identity = PairedRuntimeIdentity("runtime-1", "AetherLink", "fingerprint"),
        relayId = "relay-legacy",
        host = "127.0.0.1",
        port = port,
        security = RemoteRouteSecurityContext(
            rendezvousToken = "relay-legacy",
            expiresAtEpochMillis = Long.MAX_VALUE,
            antiReplayNonce = "relay-legacy",
        ),
    )

    private fun strictRoute(
        port: Int,
        relayId: String,
        relaySecret: String,
        routeNonce: String,
    ) = PreparedRemoteRuntimeRoute.Relay(
        identity = PairedRuntimeIdentity("runtime-1", "AetherLink", "fingerprint"),
        relayId = relayId,
        host = "127.0.0.1",
        port = port,
        relayFrameSecret = relaySecret,
        security = RemoteRouteSecurityContext(
            rendezvousToken = relayId,
            expiresAtEpochMillis = Long.MAX_VALUE,
            antiReplayNonce = routeNonce,
        ),
    )

    private fun pairedRoute(
        port: Int,
        routeNonce: String = PAIRED_ROUTE_NONCE,
    ) = PreparedRemoteRuntimeRoute.Relay(
        identity = PairedRuntimeIdentity("runtime-paired", "AetherLink", RUNTIME_KEY_FINGERPRINT),
        relayId = PAIRED_RELAY_ID,
        host = "127.0.0.1",
        port = port,
        relayFrameSecret = PAIRED_RELAY_SECRET,
        ticketGeneration = PAIRED_TICKET_GENERATION,
        security = RemoteRouteSecurityContext(
            rendezvousToken = PAIRED_RELAY_ID,
            expiresAtEpochMillis = Long.MAX_VALUE,
            antiReplayNonce = routeNonce,
        ),
    )

    private fun envelopeBody(type: String, requestId: String): ByteArray =
        """{"version":1,"type":"$type","request_id":"$requestId","timestamp":"2026-07-10T00:00:00Z","payload":{}}"""
            .encodeToByteArray()

    private data class StrictRegistration(
        val sessionNonce: String,
        val ephemeralKey: String,
    )

    private companion object {
        const val CLIENT_SESSION_NONCE = "00112233445566778899aabbccddeeff"
        const val RUNTIME_SESSION_NONCE = "ffeeddccbbaa99887766554433221100"
        const val PAIRED_RELAY_ID =
            "rt2-bab80c6a36ca54015900f1b37def33f2c15892836cb6b2907faacc3522a78361"
        const val PAIRED_RELAY_SECRET = "paired-relay-frame-secret"
        const val PAIRED_ROUTE_NONCE = "paired-route-nonce"
        const val PAIRED_TICKET_GENERATION = 8L
        const val PAIRED_CHALLENGE =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        const val RUNTIME_KEY_FINGERPRINT =
            "5cd252fb0ce8932436faf8ccd1040981b89ee4ad6b9fe9e2a2b7e71aacb27cd3"
        const val CLIENT_IDENTITY_PUBLIC_KEY =
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfPJ7GI0DT36KUjgDBLUaw8CJaeJ38hs1pgtI/" +
                "EdmmXgHd1UQ247QQCk9msafdDDbun2t5jzpgimeBLedInhz0Q=="
        const val P256_GENERATOR =
            "046b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296" +
                "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5"
        const val P256_TWO_G =
            "047cf27b188d034f7e8a52380304b51ac3c08969e277f21b35a60b48fc47669978" +
                "07775510db8ed040293d9ac69f7430dbba7dade63ce982299e04b79d227873d1"
        val LOWERCASE_DIGEST = Regex("^[0-9a-f]{64}$")
    }
}

private fun ByteArray.toHex(): String = joinToString(separator = "") { "%02x".format(it) }

private fun ByteArray.containsBytes(needle: ByteArray): Boolean {
    if (needle.isEmpty()) return true
    return indices.any { start ->
        start + needle.size <= size && needle.indices.all { offset -> this[start + offset] == needle[offset] }
    }
}

private fun java.io.InputStream.readAsciiLine(maxBytes: Int = 512): String {
    val buffer = StringBuilder()
    while (buffer.length < maxBytes) {
        val next = read()
        if (next == -1) break
        if (next == '\n'.code) return buffer.toString().trimEnd('\r')
        buffer.append(next.toChar())
    }
    error("ASCII line was not complete")
}
