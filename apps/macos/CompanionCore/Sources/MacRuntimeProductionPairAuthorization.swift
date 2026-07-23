#if DEBUG
import P2PNATContracts
import TrustedDevices

struct MacRuntimeProductionPairConnectorAttempt: Equatable, Sendable {
    let deviceID: String
    let expectedPublicKeyBase64: String
    let transcript: ProductionSecureSessionTranscript
    let routeAuthorization: ProductionRouteAuthorization

    init(
        deviceID: String,
        expectedPublicKeyBase64: String,
        transcript: ProductionSecureSessionTranscript,
        routeAuthorization: ProductionRouteAuthorization
    ) {
        self.deviceID = deviceID
        self.expectedPublicKeyBase64 = expectedPublicKeyBase64
        self.transcript = transcript
        self.routeAuthorization = routeAuthorization
    }

    var clientKeyFingerprint: String {
        transcript.clientIdentityFingerprint
    }
}

protocol MacRuntimeProductionPairAuthorizing: Sendable {
    /// Returns only after the attempt has been durably admitted. Any thrown error denies start.
    func authorizeProductionPairConnector(
        _ attempt: MacRuntimeProductionPairConnectorAttempt
    ) async throws -> ProductionPairAdmissionPermit
}
#endif
