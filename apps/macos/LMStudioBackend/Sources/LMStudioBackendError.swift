import Foundation
import OllamaBackend

public enum LMStudioBackendError: Error, Equatable, LocalizedError, Sendable {
    case unavailable(endpoint: String, reason: String)
    case noModels
    case httpStatus(endpoint: String, statusCode: Int, body: String?)
    case requestEncoding(endpoint: String, reason: String)
    case badResponse(endpoint: String, reason: String)
    case streamDecoding(line: String, reason: String)
    case generationCancelled(generationID: String)
    case generationNotFound(generationID: String)
    case transport(endpoint: String, reason: String)

    public var errorDescription: String? {
        message
    }

    public var code: String {
        switch self {
        case .unavailable:
            return "lm_studio_unavailable"
        case .noModels:
            return "lm_studio_no_models"
        case .httpStatus:
            return "lm_studio_http_status"
        case .requestEncoding:
            return "lm_studio_request_encoding"
        case .badResponse:
            return "lm_studio_bad_response"
        case .streamDecoding:
            return "lm_studio_stream_decoding"
        case .generationCancelled:
            return "lm_studio_generation_cancelled"
        case .generationNotFound:
            return "lm_studio_generation_not_found"
        case .transport:
            return "lm_studio_transport_error"
        }
    }

    public var message: String {
        switch self {
        case .unavailable(let endpoint, let reason):
            return "LM Studio is not reachable from the Mac runtime for \(endpoint): \(reason)"
        case .noModels:
            return "LM Studio did not report any local chat models."
        case .httpStatus(let endpoint, let statusCode, let body):
            let suffix = body.map { " Body: \($0)" } ?? ""
            return "LM Studio returned HTTP \(statusCode) for \(endpoint).\(suffix)"
        case .requestEncoding(let endpoint, let reason):
            return "Could not encode LM Studio request for \(endpoint): \(reason)"
        case .badResponse(let endpoint, let reason):
            return "Could not decode LM Studio response from \(endpoint): \(reason)"
        case .streamDecoding(let line, let reason):
            return "Could not decode LM Studio stream line '\(line)': \(reason)"
        case .generationCancelled(let generationID):
            return "LM Studio generation was cancelled: \(generationID)"
        case .generationNotFound(let generationID):
            return "No active LM Studio generation found for id: \(generationID)"
        case .transport(let endpoint, let reason):
            return "LM Studio transport error for \(endpoint): \(reason)"
        }
    }

    public var retryable: Bool {
        switch self {
        case .unavailable, .httpStatus, .transport:
            return true
        case .noModels, .requestEncoding, .badResponse, .streamDecoding, .generationCancelled, .generationNotFound:
            return false
        }
    }

    public var backendError: BackendError {
        switch self {
        case .unavailable:
            return BackendError(
                provider: .lmStudio,
                code: "backend_unavailable",
                message: "LM Studio is not reachable from the Mac runtime.",
                retryable: true
            )
        case .noModels:
            return BackendError(
                provider: .lmStudio,
                code: "no_models",
                message: "LM Studio did not report any local chat models.",
                retryable: false
            )
        case .httpStatus(_, let statusCode, _):
            return BackendError(
                provider: .lmStudio,
                code: "backend_unavailable",
                message: "LM Studio returned HTTP \(statusCode) to the Mac runtime.",
                retryable: true
            )
        case .transport:
            return BackendError(
                provider: .lmStudio,
                code: "transport_error",
                message: "The Mac runtime lost communication with LM Studio.",
                retryable: true
            )
        case .generationNotFound(let generationID):
            return BackendError(
                provider: .lmStudio,
                code: "generation_not_found",
                message: "No active generation found for request id: \(generationID)",
                retryable: false
            )
        case .generationCancelled(let generationID):
            return BackendError(
                provider: .lmStudio,
                code: "generation_cancelled",
                message: "Generation was cancelled for request id: \(generationID)",
                retryable: false
            )
        case .requestEncoding:
            return BackendError(
                provider: .lmStudio,
                code: "internal_error",
                message: "The Mac runtime could not encode the LM Studio request.",
                retryable: false
            )
        case .badResponse, .streamDecoding:
            return BackendError(
                provider: .lmStudio,
                code: "bad_backend_response",
                message: "The Mac runtime could not decode the LM Studio response.",
                retryable: false
            )
        }
    }
}
