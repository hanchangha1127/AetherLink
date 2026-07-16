import CryptoKit
import Foundation
@testable import CompanionCore
import XCTest

final class RuntimePermissionPolicyRegistryTests: XCTestCase {
    func testBundledRegistryPinsModelPullPolicyAndRevision() throws {
        let expectedRevision =
            "5969f34082e579a4e393bded6ce62706382e7376258b364c3afed0dbbcb163d3"
        let registry = RuntimePermissionPolicyRegistry.bundled
        XCTAssertEqual(registry.definitions.count, 1)

        let definition = try registry.definition(
            actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
            expectedRevision: RuntimePermissionPolicyRegistry.modelPullRevision
        )
        XCTAssertEqual(definition.actionID, "models_pull_ollama_v1")
        XCTAssertEqual(definition.effect, .providerArtifactInstall)
        XCTAssertEqual(definition.decision, .hostExplicitApproval)
        XCTAssertEqual(definition.audit, .durableRedactedRequired)
        XCTAssertEqual(definition.revision, expectedRevision)
        XCTAssertEqual(
            RuntimePermissionPolicyRegistry.computedRevision(
                actionID: definition.actionID,
                effect: definition.effect,
                decision: definition.decision,
                audit: definition.audit
            ),
            expectedRevision
        )
    }

    func testRegistrySortsDefinitionsAndRequiresExactRevision() throws {
        let second = manifest(actionID: "zeta_action_v1")
        let first = manifest(actionID: "alpha_action_v1")
        let registry = try RuntimePermissionPolicyRegistry(manifests: [second, first])

        XCTAssertEqual(
            registry.definitions.map(\.actionID),
            ["alpha_action_v1", "zeta_action_v1"]
        )
        XCTAssertEqual(
            try registry.definition(
                actionID: first.actionID,
                expectedRevision: first.revision
            ).actionID,
            first.actionID
        )
        XCTAssertThrowsError(
            try registry.definition(
                actionID: "missing_action_v1",
                expectedRevision: first.revision
            )
        ) { error in
            XCTAssertEqual(error as? RuntimePermissionPolicyRegistryError, .unknownAction)
        }
        XCTAssertThrowsError(
            try registry.definition(
                actionID: first.actionID,
                expectedRevision: String(repeating: "0", count: 64)
            )
        ) { error in
            XCTAssertEqual(error as? RuntimePermissionPolicyRegistryError, .unexpectedRevision)
        }
    }

    func testRegistryRejectsMalformedUnsupportedDuplicateAndTamperedDefinitions() {
        assertRegistryError([], equals: .emptyRegistry)
        assertRegistryError(
            Array(
                repeating: manifest(actionID: "overflow_action_v1"),
                count: RuntimePermissionPolicyRegistry.maximumDefinitionCount + 1
            ),
            equals: .tooManyDefinitions
        )
        for actionID in [
            "", "1action", "_action", "Action_v1", "action-v1", "re\u{301}sume_v1",
            "a" + String(
                repeating: "b",
                count: RuntimePermissionPolicyRegistry.maximumActionIDUTF8Bytes
            ),
        ] {
            assertRegistryError(
                [manifest(actionID: actionID)],
                equals: .invalidActionID,
                actionID
            )
        }

        let valid = manifest(actionID: "valid_action_v1")
        assertRegistryError([
            RuntimePermissionPolicyManifest(
                actionID: valid.actionID,
                revision: String(repeating: "A", count: 64),
                effect: valid.effect,
                decision: valid.decision,
                audit: valid.audit
            )
        ], equals: .invalidRevision)
        assertRegistryError([
            RuntimePermissionPolicyManifest(
                actionID: valid.actionID,
                revision: valid.revision,
                effect: "terminal_process",
                decision: valid.decision,
                audit: valid.audit
            )
        ], equals: .unsupportedEffect)
        assertRegistryError([
            RuntimePermissionPolicyManifest(
                actionID: valid.actionID,
                revision: valid.revision,
                effect: valid.effect,
                decision: "client_allow",
                audit: valid.audit
            )
        ], equals: .unsupportedDecision)
        assertRegistryError([
            RuntimePermissionPolicyManifest(
                actionID: valid.actionID,
                revision: valid.revision,
                effect: valid.effect,
                decision: valid.decision,
                audit: "best_effort"
            )
        ], equals: .unsupportedAuditRequirement)
        assertRegistryError([
            RuntimePermissionPolicyManifest(
                actionID: valid.actionID,
                revision: String(repeating: "0", count: 64),
                effect: valid.effect,
                decision: valid.decision,
                audit: valid.audit
            )
        ], equals: .revisionMismatch)
        assertRegistryError([valid, valid], equals: .duplicateActionID)
        assertRegistryError([
            valid,
            RuntimePermissionPolicyManifest(
                actionID: "other_action_v1",
                revision: valid.revision,
                effect: valid.effect,
                decision: valid.decision,
                audit: valid.audit
            )
        ], equals: .duplicateRevision)
    }

    func testClaimDigestIsLengthFramedAndBindsPolicyAuthorityAndResource() throws {
        let registry = RuntimePermissionPolicyRegistry.bundled
        let authority = RuntimePermissionAuthorityBinding(
            connectionID: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            requestID: "permission-binding-request",
            authenticationGeneration: 7,
            deviceID: "device-1",
            publicKeyBase64: "cHVibGljLWtleQ==",
            transportBinding: String(repeating: "a", count: 64)
        )
        let claim = try registry.claim(
            actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
            expectedRevision: RuntimePermissionPolicyRegistry.modelPullRevision,
            authority: authority,
            resourceKind: "ollama_model",
            resourceValue: "private-model"
        )

        let expectedFields = [
            "runtime-permission-request-binding-v1",
            "models_pull_ollama_v1",
            "5969f34082e579a4e393bded6ce62706382e7376258b364c3afed0dbbcb163d3",
            "provider_artifact_install",
            "host_explicit_approval",
            "durable_redacted_required",
            "00000000-0000-0000-0000-000000000001",
            "permission-binding-request",
            "7",
            "device-1",
            "cHVibGljLWtleQ==",
            "transport_present",
            String(repeating: "a", count: 64),
            "ollama_model",
            "private-model",
        ]
        var material = Data()
        for field in expectedFields {
            var length = UInt64(field.utf8.count).bigEndian
            withUnsafeBytes(of: &length) { material.append(contentsOf: $0) }
            material.append(contentsOf: field.utf8)
        }
        let expectedDigest = SHA256.hash(data: material)
            .map { String(format: "%02x", $0) }
            .joined()
        XCTAssertEqual(
            claim.requestBindingDigest,
            RuntimePermissionPolicyRegistry.requestBindingDigestPrefix + expectedDigest
        )
        XCTAssertEqual(claim.authorityKeyFingerprint, "43:A4:6F:1D:08:1D")
        XCTAssertTrue(registry.validatesModelPullClaim(claim))
        for secret in [authority.deviceID, authority.publicKeyBase64, "private-model"] {
            XCTAssertFalse(claim.requestBindingDigest.contains(secret))
        }
    }

    func testClaimDigestChangesForEveryAuthorityAndResourceField() throws {
        let registry = RuntimePermissionPolicyRegistry.bundled
        let baseAuthority = authority()
        let base = try claim(registry: registry, authority: baseAuthority)
        let variants = [
            RuntimePermissionAuthorityBinding(
                connectionID: UUID(),
                requestID: baseAuthority.requestID,
                authenticationGeneration: baseAuthority.authenticationGeneration,
                deviceID: baseAuthority.deviceID,
                publicKeyBase64: baseAuthority.publicKeyBase64,
                transportBinding: baseAuthority.transportBinding
            ),
            authority(requestID: "other-request"),
            authority(authenticationGeneration: 2),
            authority(deviceID: "other-device"),
            authority(publicKeyBase64: "b3RoZXIta2V5"),
            authority(transportBinding: String(repeating: "b", count: 64)),
            authority(transportBinding: nil),
        ]
        for variant in variants {
            XCTAssertNotEqual(
                try claim(registry: registry, authority: variant).requestBindingDigest,
                base.requestBindingDigest
            )
        }
        XCTAssertNotEqual(
            try claim(
                registry: registry,
                authority: baseAuthority,
                resourceValue: "other-model"
            ).requestBindingDigest,
            base.requestBindingDigest
        )
    }

    func testModelPullClaimValidationRequiresExactAuthorityAndResourceParity() throws {
        let registry = RuntimePermissionPolicyRegistry.bundled
        let exactAuthority = authority()
        let exactClaim = try claim(
            registry: registry,
            authority: exactAuthority,
            resourceValue: "private-model"
        )

        XCTAssertTrue(registry.validatesModelPullClaim(
            exactClaim,
            authority: exactAuthority,
            model: "private-model"
        ))
        XCTAssertTrue(registry.validatesModelPullClaim(
            exactClaim,
            connectionID: exactAuthority.connectionID,
            model: "private-model"
        ))
        XCTAssertFalse(registry.validatesModelPullClaim(
            exactClaim,
            authority: authority(requestID: "different-request"),
            model: "private-model"
        ))
        XCTAssertFalse(registry.validatesModelPullClaim(
            exactClaim,
            connectionID: UUID(),
            model: "private-model"
        ))
        XCTAssertFalse(registry.validatesModelPullClaim(
            exactClaim,
            authority: exactAuthority,
            model: "different-model"
        ))

        let wrongResourceKind = try registry.claim(
            actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
            expectedRevision: RuntimePermissionPolicyRegistry.modelPullRevision,
            authority: exactAuthority,
            resourceKind: "other_resource",
            resourceValue: "private-model"
        )
        XCTAssertTrue(registry.validates(wrongResourceKind))
        XCTAssertFalse(registry.validatesModelPullClaim(wrongResourceKind))
    }

    func testGenericValidationAcceptsExactSyntheticClaimWithoutBroadeningModelPull() throws {
        let synthetic = manifest(actionID: "test_host_action_v1")
        let registry = try RuntimePermissionPolicyRegistry(manifests: [synthetic])
        let claim = try registry.claim(
            actionID: synthetic.actionID,
            expectedRevision: synthetic.revision,
            authority: authority(),
            resourceKind: "test_resource",
            resourceValue: "ephemeral-test-value"
        )

        XCTAssertTrue(registry.validates(claim))
        XCTAssertFalse(registry.validatesModelPullClaim(claim))
        XCTAssertFalse(RuntimePermissionPolicyRegistry.bundled.validates(claim))
        XCTAssertEqual(RuntimePermissionPolicyRegistry.bundled.definitions.count, 1)
    }

    func testClaimRejectsInvalidAuthorityAndResource() throws {
        let registry = RuntimePermissionPolicyRegistry.bundled
        for invalidAuthority in [
            authority(requestID: " request"),
            authority(authenticationGeneration: .max),
            authority(deviceID: "device\nname"),
            authority(publicKeyBase64: ""),
            authority(transportBinding: " binding"),
        ] {
            XCTAssertThrowsError(
                try claim(registry: registry, authority: invalidAuthority)
            ) { error in
                XCTAssertEqual(
                    error as? RuntimePermissionPolicyRegistryError,
                    .invalidAuthorityBinding
                )
            }
        }
        for (kind, value) in [
            ("ollama.model", "private-model"),
            ("ollama_model", " private-model"),
            ("ollama_model", String(
                repeating: "m",
                count: RuntimePermissionPolicyRegistry.maximumResourceUTF8Bytes + 1
            )),
        ] {
            XCTAssertThrowsError(
                try registry.claim(
                    actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
                    expectedRevision: RuntimePermissionPolicyRegistry.modelPullRevision,
                    authority: authority(),
                    resourceKind: kind,
                    resourceValue: value
                )
            ) { error in
                XCTAssertEqual(error as? RuntimePermissionPolicyRegistryError, .invalidResource)
            }
        }
    }

    private func manifest(actionID: String) -> RuntimePermissionPolicyManifest {
        RuntimePermissionPolicyManifest(
            actionID: actionID,
            revision: RuntimePermissionPolicyRegistry.computedRevision(
                actionID: actionID,
                effect: .providerArtifactInstall,
                decision: .hostExplicitApproval,
                audit: .durableRedactedRequired
            ),
            effect: RuntimePermissionEffect.providerArtifactInstall.rawValue,
            decision: RuntimePermissionDecision.hostExplicitApproval.rawValue,
            audit: RuntimePermissionAuditRequirement.durableRedactedRequired.rawValue
        )
    }

    private func authority(
        requestID: String = "request-1",
        authenticationGeneration: UInt64 = 1,
        deviceID: String = "device-1",
        publicKeyBase64: String = "cHVibGljLWtleQ==",
        transportBinding: String? = String(repeating: "a", count: 64)
    ) -> RuntimePermissionAuthorityBinding {
        RuntimePermissionAuthorityBinding(
            connectionID: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
            requestID: requestID,
            authenticationGeneration: authenticationGeneration,
            deviceID: deviceID,
            publicKeyBase64: publicKeyBase64,
            transportBinding: transportBinding
        )
    }

    private func claim(
        registry: RuntimePermissionPolicyRegistry,
        authority: RuntimePermissionAuthorityBinding,
        resourceValue: String = "private-model"
    ) throws -> RuntimePermissionPolicyClaim {
        try registry.claim(
            actionID: RuntimePermissionPolicyRegistry.modelPullActionID,
            expectedRevision: RuntimePermissionPolicyRegistry.modelPullRevision,
            authority: authority,
            resourceKind: "ollama_model",
            resourceValue: resourceValue
        )
    }

    private func assertRegistryError(
        _ manifests: [RuntimePermissionPolicyManifest],
        equals expected: RuntimePermissionPolicyRegistryError,
        _ context: String = "",
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertThrowsError(
            try RuntimePermissionPolicyRegistry(manifests: manifests),
            context,
            file: file,
            line: line
        ) { error in
            XCTAssertEqual(
                error as? RuntimePermissionPolicyRegistryError,
                expected,
                context,
                file: file,
                line: line
            )
        }
    }
}
