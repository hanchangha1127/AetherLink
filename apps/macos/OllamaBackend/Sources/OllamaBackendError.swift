import Foundation

public enum OllamaBackendError: Error, Equatable, LocalizedError, Sendable {
    case unreachable(endpoint: String, baseURL: String, reason: String)
    case httpStatus(endpoint: String, statusCode: Int, body: String?)
    case requestEncoding(endpoint: String, reason: String)
    case responseDecoding(endpoint: String, reason: String)
    case streamDecoding(line: String, reason: String)
    case generationCancelled(generationID: String)
    case generationNotFound(generationID: String)
    case transport(endpoint: String, reason: String)

    public var errorDescription: String? {
        message
    }

    public var code: String {
        switch self {
        case .unreachable:
            return "ollama_unreachable"
        case .httpStatus(_, let statusCode, _) where statusCode == 401 || statusCode == 403:
            return "ollama_auth_required"
        case .httpStatus:
            return "ollama_http_status"
        case .requestEncoding:
            return "ollama_request_encoding"
        case .responseDecoding:
            return "ollama_response_decoding"
        case .streamDecoding:
            return "ollama_stream_decoding"
        case .generationCancelled:
            return "ollama_generation_cancelled"
        case .generationNotFound:
            return "ollama_generation_not_found"
        case .transport:
            return "ollama_transport_error"
        }
    }

    public var message: String {
        switch self {
        case .unreachable(let endpoint, let baseURL, let reason):
            return "Ollama is not reachable at \(baseURL) for \(endpoint): \(reason)"
        case .httpStatus(let endpoint, let statusCode, let body):
            let suffix = body.map { " Body: \($0)" } ?? ""
            return "Ollama returned HTTP \(statusCode) for \(endpoint).\(suffix)"
        case .requestEncoding(let endpoint, let reason):
            return "Could not encode Ollama request for \(endpoint): \(reason)"
        case .responseDecoding(let endpoint, let reason):
            return "Could not decode Ollama response from \(endpoint): \(reason)"
        case .streamDecoding(let line, let reason):
            return "Could not decode Ollama stream line '\(line)': \(reason)"
        case .generationCancelled(let generationID):
            return "Ollama generation was cancelled: \(generationID)"
        case .generationNotFound(let generationID):
            return "No active Ollama generation found for id: \(generationID)"
        case .transport(let endpoint, let reason):
            return "Ollama transport error for \(endpoint): \(reason)"
        }
    }

    public var retryable: Bool {
        switch self {
        case .unreachable, .httpStatus, .transport:
            return true
        case .requestEncoding, .responseDecoding, .streamDecoding, .generationCancelled, .generationNotFound:
            return false
        }
    }

    public var backendError: BackendError {
        switch self {
        case .unreachable:
            return BackendError(
                provider: .ollama,
                code: "backend_unavailable",
                message: "Ollama is not reachable from the runtime host.",
                retryable: true
            )
        case .httpStatus(_, let statusCode, _) where statusCode == 401 || statusCode == 403:
            return BackendError(
                provider: .ollama,
                code: "ollama_auth_required",
                message: "Ollama rejected the request. Open Ollama on the paired runtime, sign in or refresh model access, then try again.",
                retryable: true
            )
        case .httpStatus(_, let statusCode, _):
            return BackendError(
                provider: .ollama,
                code: "backend_unavailable",
                message: "Ollama returned HTTP \(statusCode) to the runtime host.",
                retryable: true
            )
        case .transport:
            return BackendError(
                provider: .ollama,
                code: "transport_error",
                message: "The runtime host lost communication with Ollama.",
                retryable: true
            )
        case .generationNotFound(let generationID):
            return BackendError(
                provider: .ollama,
                code: "generation_not_found",
                message: "No active generation found for request id: \(generationID)",
                retryable: false
            )
        case .generationCancelled(let generationID):
            return BackendError(
                provider: .ollama,
                code: "generation_cancelled",
                message: "Generation was cancelled for request id: \(generationID)",
                retryable: false
            )
        case .requestEncoding:
            return BackendError(
                provider: .ollama,
                code: "internal_error",
                message: "The runtime host could not encode the Ollama request.",
                retryable: false
            )
        case .responseDecoding:
            return BackendError(
                provider: .ollama,
                code: "bad_backend_response",
                message: "The runtime host could not decode the Ollama response.",
                retryable: false
            )
        case .streamDecoding:
            return BackendError(
                provider: .ollama,
                code: "bad_backend_response",
                message: "The runtime host could not decode the Ollama stream.",
                retryable: false
            )
        }
    }
}
