# AetherLink Client-Runtime JSON Protocol

## Citation And Device Trusted-Source Review Contract

`citation.resolve` is an authenticated opt-in resolver for a canonical `source_anchor_id` returned by `retrieval.query`. A successful response contains a version-1 `citation` envelope, a one-time ten-minute `review` envelope, and an optional existing `trusted_source` grant for the authenticated device. The citation carries only an opaque `citation_[32 lowercase hex]` handle, the source anchor, safe document metadata, and the existing bounded chunk summary. The runtime stores the full approved source revision only behind the opaque handle; source revision, approval id, path, body, snippet, query, model, vector, cache, backend, workspace, and project metadata stay off the wire.

The review envelope contains `source_review_[32 lowercase hex]`, a one-time `source_confirmation_[64 lowercase hex]` token, exact disclosure version `runtime-trusted-source-v1`, fixed `chat_context` usage scope, and an ISO-8601 expiry. Preparing a new review invalidates the same device's previous pending review. `trusted_source.approve` consumes the exact review id, token, disclosure version, and usage scope once. `trusted_source.dismiss` discards a pending review. `trusted_source.list` returns at most 100 current grants owned by the authenticated device, and `trusted_source.revoke` removes only that device's named grant.

This client grant does not create, replace, revoke, or widen the host's `runtime_shared` approval. It records that one authenticated device reviewed one exact approved source revision for future `chat_context` use. Same-revision reindex preserves it; changed replacement, host revoke, or deletion makes the citation/review/grant stale before later use. Prepare, approve, list, dismiss, revoke, revision validation, and content-free audit changes are serialized in the document SQLite store. Confirmation tokens, review ids, grant ids, query text, snippets, and bodies are not audit fields.

Android keeps review ids, confirmation tokens, and grant ids private and transient for the authenticated connection. Only safe document metadata, trust status, and transient source selection enter `RuntimeUiState`. A chat request may carry `trusted_source_grant_ids` only as a top-level authorization array; grant, citation, and anchor ids never enter client-visible messages, persistence, accessibility text, or backend model context.

`chat.send.payload.trusted_source_grant_ids` is optional. When present it contains one through eight unique canonical `trusted_source_[32 lowercase hex]` ids. The runtime validates the complete ordered set in one document-store transaction against the authenticated device, `chat_context` scope, non-revoked grant, non-stale citation, current `runtime_shared` approval, exact source revision, current document metadata, source anchor, and chunk identity. It appends one content-free `trusted_source_context_consumed` audit event per source in that transaction and returns text only after commit. A malformed array is `invalid_payload`; any unknown, wrong-device, revoked, deleted, or stale member makes the whole request `trusted_source_not_found`; storage or audit failure is `document_index_unavailable`.

The runtime bounds each selected excerpt to 4,096 UTF-8 bytes, serializes only safe document name, MIME type, chunk index, and text into a runtime-owned JSON reference block, and appends that block only to the backend copy of the newest user message. The capability guard tells the model that source text is reference data rather than instructions. Original client messages remain the sole transcript authority, so source text and opaque authorization handles do not enter chat events, title generation inputs, history reads, or Android persistence. A committed use remains valid for that request if revoke commits afterward; revoke or revision change blocks every later use. Physical Android interaction and live-provider answer quality remain separate proof.

## Authenticated Historical Chat Source Attribution Review Contract

`chat.source_attribution.resolve` is an authenticated, capability-negotiated review preparation request for one attribution on one canonical stored assistant answer. Its request payload contains exactly `session_id`, `assistant_message_id`, and `source_index`. `assistant_message_id` is a server-generated opaque locator, not an authorization handle. The runtime projects it only on attribution-bearing successful `chat.done` and assistant `chat.messages.list` entries for connections advertising `chat.source_attribution.resolve.v1`; it is absent from source-free, cancelled, errored, incomplete, user, legacy, and capability-omitting payloads. `source_attributions` remains exactly the four safe display fields `source_index`, `document_name`, `mime_type`, and `chunk_index`.

The runtime resolves the tuple only from canonical owner-scoped chat history. The stored assistant terminal event atomically records one internal binding with exactly `source_index`, `source_anchor_id`, `document_id`, and `source_revision` for each safe attribution. Approval state and a separate chunk identifier are not binding fields, and the binding never appears in ordinary `chat.done` or history. Before preparing review, one atomic document-store operation uses the bound source anchor, document, and revision and revalidates current `runtime_shared` approval and the exact historical revision. Unknown owners, sessions, messages, source indexes, legacy rows without a binding, regenerated or deleted answers, deleted sources, changed revisions, revoked approvals, and malformed storage all fail closed without inferring authority from display metadata.

Request:

```json
{
  "version": 1,
  "type": "chat.source_attribution.resolve",
  "request_id": "req_source_attribution_001",
  "timestamp": "2026-07-12T09:02:07Z",
  "payload": {
    "session_id": "default",
    "assistant_message_id": "assistant_message_0123456789abcdef0123456789abcdef",
    "source_index": 1
  }
}
```

A successful response uses the same bounded `citation`, one-time `review`, and optional current-device `trusted_source` envelopes documented for `citation.resolve`. The historical locator and source index select the binding but grant no access by themselves. Source text, internal anchor/document/revision/approval binding, confirmation material, and authority identifiers do not enter normal chat completion or history payloads.

`research.notebooks.v1` advertises runtime-owned, chat-backed research notebooks. `research.brief.create` requires exactly a canonical `research_notebook_[32 lowercase hex]` id, a nonblank backing `session_id`, a bounded topic, a selected installed chat model, optional locale, and one through eight unique current-device `trusted_source_[32 lowercase hex]` grants. The runtime stores only owner-scoped notebook metadata and the ordered private grant ids, injects its research instruction and the currently revalidated approved excerpts only into the backend request, and returns the answer through the existing `chat.delta`/`chat.done` stream under the original request id.

Notebook follow-ups use ordinary `chat.send`. An omitted grant array is replaced with the notebook's pinned ordered grants; a client-supplied different array is `invalid_payload`, and a revoked, stale, deleted, wrong-device, or no-longer-host-approved grant fails through the existing trusted-source gate before backend dispatch. Existing `chat.cancel`, `chat.messages.list`, `chat.source_attribution.resolve`, and chat session archive/restore/delete operations remain authoritative for streaming, history, source review, and lifecycle.

`research.notebooks.list` returns only safe notebook summaries. An initial request contains exactly `include_archived` and a `1...200` `limit`; a continuation contains exactly one opaque, nonblank `cursor` bounded to 512 UTF-8 bytes. Its response contains only notebook id, backing session id, bounded title/model, source count, created/updated times, optional archived time, and the negotiated pagination metadata described below. The backing runtime-owned chat session is the title authority: the list projects its current title instead of treating the immutable notebook-creation title as a second mutable source of truth. A successful `chat.session.rename` advances the projected `updated_at` through separate title metadata without changing conversational `last_activity_at`, participates in canonical `updated_at` descending then notebook-id unsigned UTF-8 byte ordering, and invalidates previously issued authoritative notebook cursors for that owner. Every page preserves unique notebook ids and unique backing session ids. It never returns grant ids, source anchors/text/revisions, snippets, paths, URLs, backend settings, tokens, vectors, or prompt internals. This feature does not add web search, external network access, whole-document authority, project indexing, or automatic memory mutation.

Clients advertising `research.notebooks.authoritative_sync.v1` receive `snapshot_count` on every accepted page and an optional `next_cursor` when another page exists. `snapshot_count` is bounded to `0...10000`, a capable page contains at most 200 notebooks, and its page size cannot exceed the snapshot count. A client that does not advertise authoritative notebook sync receives the legacy `notebooks`-only response with at most 100 notebooks and no `snapshot_count` or `next_cursor`. Request and response branches are strict and cannot mix initial fields, cursor continuation fields, legacy fields, or capable pagination fields.

The shared fixture and focused protocol/schema checks establish only a no-device/no-network wire contract, including generated 201-notebook `100/100/1` pagination. They do not prove a running host snapshot store, live connection continuation, physical Android behavior, provider access, external research, or any network transport.

Android opens the existing trusted-source review dialog from an attribution click. The locator may persist as non-authorizing history metadata, but review ids, confirmation tokens, citation/grant/anchor/document ids, approval ids, and source revisions remain private transient ViewModel state and must not enter `RuntimeUiState`, chat persistence, visible text, accessibility content, logs, or a later request except through the existing explicit review/approval operations.

## Approved Semantic Document Retrieval Contract

`retrieval.query` accepts optional provider-qualified `embedding_model_id`. Omission uses deterministic lexical retrieval and preserves the legacy result key set with no `match_kind`. Explicit opt-in uses runtime-host semantic ranking and returns `match_kind: semantic`; semantic errors do not silently fall back. Missing or explicit lexical origin requires one through 16 honest `matched_terms`, while explicit semantic origin may carry zero through 16 literal overlaps. Snippets remain non-empty and capped at 500 characters; a requested zero snippet ceiling is normalized to one character.

Android sends its selected runtime-host embedding model only with a valid bounded document query, decodes the typed origin into transient state, and renders a localized semantic label without inventing a lexical term. For an older strict runtime that returns `invalid_payload` naming the unsupported field, Android retries once with the same query, limit, and snippet bound but without the hint. It does not retry backend or index failures. Model ids, scores, vectors, fingerprints, source revisions, query text, and cache metadata remain absent from result payloads.

For a strong immutable model fingerprint, the runtime embeds the query once, considers at most 200 usable `runtime_shared` chunks, and embeds missing candidates in batches of at most 64 and 262,144 bytes. For weak/no-fingerprint providers, including LM Studio, it selects at most 63 candidates and embeds `[query, candidates...]` in one atomic request; this path is recomputed on demand and cannot mix vectors from different backend calls. Candidate selection round-robins deterministically across documents, each input is capped by the selected model allowance and 4,096 UTF-8 bytes, and numerically stable cosine similarity becomes contiguous 1-based ranks with display-name, document-id, and chunk-index ties. The host accepts at most 800 `runtime_shared` approvals and its local management view can list and revoke all of them independently of the remote 100-row catalog response ceiling; semantic reads fail closed if a legacy database exceeds the approval ceiling. Candidate discovery selects at most 200 usable documents, distributes a hard total budget of 800 chunk rows without a corpus-sized window CTE, and installs a SQLite progress handler so connection cancellation interrupts ongoing discovery.

Before candidate inference, one immediate SQLite transaction revalidates approval, source revision, chunk identity, model input byte limit, and bounded-content fingerprint and appends a content-free `semantic_accessed` audit. Before response serialization, another immediate transaction drops candidates changed or revoked during inference and conditionally appends content-free `.queried` with the final result count. Backend failure or cancellation observed before that final commit keeps an access event but no completed-query event; after commit, the runtime proceeds with response serialization. Query text and vectors are never persisted.

The candidate cache is not a wire feature. It shares the runtime document SQLite database and stores only strong-model candidate vectors keyed by the full approved identity, model input byte limit, and encoding version. Canonical Ollama artifact SHA-256 revisions qualify; providers without an immutable revision remain on-demand. Replacement, revoke, delete, and filtered maintenance remove derived rows transactionally. The phone is disconnected, so current proof is no-device schema/SQLite/Swift/JVM/development-mock evidence rather than physical Android, live-provider quality, optical QR, production relay/P2P, or real-network proof. The newer citation section adds only review/grant lifecycle and does not inject sources into chat.

## Host Document Source Review Boundary

This host workflow adds no wire message or response field. The macOS runtime snapshots a selected regular file under security-scoped access, publishes only a safe review summary, and changes the active `runtime_shared` approval only after a versioned one-time confirmation. Replacement keeps the prior approved revision active until source-revision compare-and-swap succeeds; cancel, expiry, stale revision, and removal cannot expose a pending candidate.

The host manager and runtime router share one SQLite store. Existing authenticated `index.documents.list`, lexical `retrieval.query`, and `source_anchor.resolve` therefore observe approve, replace, and remove changes without a client management command. Removal revokes and deletes local indexed content while preserving content-free audit tombstones.

Audit retains the newest 100,000 local events in both in-memory and SQLite stores. Each insert removes only oldest overflow in the same transaction; host export is capped at the latest 1,000 events and contains no source paths, bookmarks, file bodies, query text, snippets, confirmation tokens, or pending content. The newer sections above activate approved semantic ranking and device-scoped citation review without adding cache metadata or host approval controls to the wire. The phone is disconnected; this is no-device host workflow evidence, not physical Android, optical QR, live-provider, production relay/P2P, or real-network proof.

## Runtime-Shared Document Source Governance Boundary

This foundation adds no wire message or response field. Existing authenticated `index.documents.list`, lexical `retrieval.query`, and `source_anchor.resolve` keep their current JSON shapes. The runtime serves only sources with an internal `runtime_shared` approval, meaning every trusted device authenticated to that runtime can read the same approved shared library; this is not per-device document isolation.

Host-owned `replaceDocument` creates an approval bound to a strong revision over canonical safe document metadata and the complete normalized chunk set. Legacy SQLite rows do not receive approvals during schema creation and are invisible until explicitly replaced through that host operation. Revoke/delete removes document, chunk, FTS, and approval state atomically and makes old source anchors unresolved.

Before serializing a successful catalog, retrieval, or anchor response, the runtime performs the approved read and appends its authenticated-device audit event in one store transaction. This commit is the read's linearization point: concurrent revoke cannot cross it, and every operation starting after revoke commits sees no source. Every accepted retrieval query is audited, including punctuation-only or zero-limit requests that return zero results. Audit fields are action, safe document/revision identity when applicable, source anchor id when applicable, result count, and time; query text, snippet text, and document body are not fields. An unavailable governance store or failed audit write returns `document_index_unavailable` instead of the successful response.

No client command can change host source approval. The active citation/trusted-source commands above create only authenticated-device `chat_context` review grants bound to the current host-approved revision. Approved semantic ranking and optional `retrieval.query` embedding hints remain active; vector cache and approval metadata stay host-internal.

## Production P2P/NAT Design Boundary

The reviewed [production P2P/NAT security hardening portfolio](security-hardening/production-p2p-nat-v1/hardening.md) defines a protocol profile for future authenticated candidate exchange and path-independent endpoint security, but that profile is not implemented. `route.refresh` remains the only active `route.*` message. The active wire schema still contains no `p2p.*`, `rendezvous.*`, `bootstrap.*`, `dht.*`, `nat.*`, `stun.*`, `turn.*`, `session.*`, `key_exchange.*`, `encrypted_session.*`, `anti_replay.*`, `transport.*`, or `crypto.*` control messages.

Future candidate signaling must bind a pair-scoped exchange ID, pair epoch, sender role, monotonic sequence, issue/expiry times, protocol offer set, ICE generation and credentials, bounded candidate-set digest, and prior-envelope digest inside an authenticated encrypted envelope. Raw host candidates must not enter QR data or public rendezvous indexes. ICE connectivity checks and TURN allocation establish reachability only; normal paired-device identity verification and mutual key confirmation remain mandatory before runtime commands.

Future direct and relay paths must carry the same transport-neutral secure-session transcript over both pinned identities and roles, both ephemeral shares and nonces, pair epoch, candidate-exchange digest, selected path, protocol selection, and relay lease digest. Migration or relay fallback must validate the new path while retaining the current authenticated path, and must never negotiate down to development plaintext or weaker authentication. Reserved namespaces remain rejected as `unknown_message_type` until a selected implementation adds exact schemas and cross-platform vectors.

## Development Relay Waiting Peer Policy Contract

This policy adds no wire message. After successful matcher admission, the first unmatched peer creates one monotonic room deadline. The default is `60` seconds, configuration accepts canonical positive values through `3600`, there is no disable value, and an allocated room's deadline is capped by its remaining lease. Registration and readiness probes atomically remove expired rooms under the matcher lock before matching, replacement, or visibility decisions, independent of timer delivery latency. A waiting result carries its deadline out of the same matcher transaction, so the server does not re-read room state after a counterpart can move it active. Same-role replacement inherits the existing live deadline. Timeout closes silently. Match, disconnect, invalidation, replacement cleanup, timeout, and close release exact waiting ownership; active bridge activation cancels the waiting deadline and encrypted forwarding remains timeout-free.

Post-authenticated identity fairness uses only verified allocation-binding identity. Runtime proof admits `(runtime, runtime_key_fingerprint)` and paired-client proof admits `(client, paired_client_key_fingerprint)`; the role domains are distinct. The default quota is `4` unmatched waits per authenticated identity across source addresses, configurable through `65536` with no disable value. Immediate matches and active bridges consume no identity waiting quota. Bootstrap clients without paired-client proof and legacy peers remain identity-untracked and source-limited. Failed proofs never reach identity accounting.

Stable source-free reasons are `waiting_peer_timed_out` and `authenticated_identity_waiting_quota_reached`; aggregate saturating metrics omit source addresses, fingerprints, roles, relay IDs, route/allocation tokens, lease material, and proof fields. Source/global admission still occurs at TCP accept before parsing and authentication. This is development fairness rather than per-user isolation, Sybil resistance, production identity service, public-network capacity proof, production TLS/KEX/pair-epoch implementation, or physical Android proof; the phone is disconnected.

## Development Relay Source Peer Quota Contract

Source peer quotas do not add or change any wire message. At TCP accept, the relay canonicalizes the peer socket address using the same identity contract as allocation rate limiting: IPv4-mapped IPv6 becomes IPv4, native IPv6 includes scope ID, exact IPv6 addresses remain distinct, and unsupported families share the unknown identity. Source ports are excluded.

The default limits are `64` concurrent accepted sockets and `32` unmatched waiting peers per source. Normal admission leaves one global and one per-source slot available before the first waiter exists. Every waiting insertion atomically requires `connections + waiting + 1 <= limit` for both scopes, and each waiter then removes one additional slot from normal admission. A socket admitted from that reserve is counterpart-only until an immediate opposite-role match or authenticated same-source waiting replacement confirms it; probe/allocation, cross-source replacement, and new-room use close it. Reserve provenance is retained: a candidate consuming per-source reserve can discharge only a waiter owned by that source, while a global-only reserve candidate may match across sources. Active bridge sockets retain source connection capacity until close. The `2 * waiting <= connections` validation preserves counterpart headroom, and there is no disable value. A matching counterpart never consumes a new waiting permit, same-source replacement is net-zero, and cross-source replacement either atomically transfers ownership or leaves the original waiter intact when normal admission applies; reserve candidates cannot transfer waiting ownership across sources.

Quota rejection closes silently without a new response frame. Stable source-free reasons and saturating metrics expose aggregate counts only. Established active bridge frame forwarding is not throttled or evicted. Shared NAT/VPN users share quotas, so this is a configurable development fairness contract rather than per-user isolation, production capacity validation, public-relay/live-network proof, or physical Android proof. The production TLS/KEX/pair-epoch design remains selection-gated.

## Development Relay Source Rate-Limit Contract

After a control line is recognized by its allocation or renewal prefix, the development relay classifies and charges it before full request parsing. Only the exact strict envelope `AETHERLINK_RELAY allocate <route_token> crypto=2 [allocation_token=<token>] preflight=1\n` selects `preflight`. Duplicate markers, extra or mutation-like fields, malformed spacing/line endings, legacy `preflight=true`, every other allocation attempt, and every paired claim/renew attempt select `allocationMutation`. A rejected request closes silently before parsing, allocation-token comparison, or cryptographic challenge generation.

The default contract is `120/minute`, burst `30` for preflight and `30/minute`, burst `10` for mutations. The source is derived from the accepted socket, IPv4-mapped IPv6 canonicalizes to IPv4, native IPv6 includes its scope ID, and unknown families share one bucket. Refill is monotonic; one shared overflow bucket and periodic idle cleanup enforce the state cap without capacity-reset or per-request full-map-scan behavior. Both bursts must fully refill within idle retention before a configuration is accepted.

Stable reasons are `allocation_preflight_source_rate_limited` and `allocation_mutation_source_rate_limited`. Metrics expose the two request totals, two rejection totals, overflow request total, idle sweep total, idle source eviction total, and current tracked-bucket count without source or route labels. Logs carry only a reason and global reason count.

Probe, runtime/client registration, waiting rooms, active bridges, and encrypted frame forwarding are not part of this rate-limit contract; connection and waiting admission are governed separately by the source peer quota contract above. Shared NAT/VPN users share a bucket. This is not production capacity validation, a wire-format change, production TLS/KEX/pair-epoch implementation, or physical Android proof; the phone is disconnected.

## Development Relay Abuse-Control Contract

Every accepted development-relay TCP descriptor consumes one global connection permit until close. This includes allocation/probe requests, incomplete control records, waiting runtime/client registrations, and both sockets in an active bridge. A waiting peer is monitored for EOF or protocol-early bytes; either condition removes the matcher registration and releases the permit before a later counterpart can match it.

Each control record must complete within one configured absolute monotonic deadline. The deadline restarts only for the next protocol record, not for each byte, so trickled input cannot hold a worker indefinitely. The newline remains part of the 4096-byte maximum. Once a pair is matched and ready metadata is sent, frame forwarding has no control-line timeout.

`probe_policy=loopback-only` is the default. `disabled` closes every probe, while `legacy-unauthenticated` is an explicit diagnostic route-state oracle. Exposed default probe closure is `Unsupported` to Android and must fall through to actual authenticated registration; a canonical `known=0` response is `Unavailable` and may fail early. Unallocated legacy relay mode is loopback-only.

This contract is complemented by the waiting-peer, allocation-rate, and source-peer quota contracts above. It is not production TLS/KEX or physical Android proof. It does not change strict crypto-v2 registration, allocation authorization, peer key confirmation, or encrypted frame formats.

## Production Relay V3 Design Boundary

The reviewed [production relay security hardening portfolio](security-hardening/production-relay-v1/hardening.md) is the decision record for the next transport protocol milestone. It recommends TLS 1.3 for allocation, a delegated service-signed canonical lease, and a peer-verifiable endpoint identity KEX that binds both long-term identities, both ephemeral shares, both session nonces, `pair_epoch`, lease generation, and the signed lease digest. The endpoint traffic secret remains endpoint-owned and never enters allocation or relay infrastructure.

The companion recovery contract recommends monotonic `pair_epoch` and `revocation_counter`, dual-signed same-epoch renewal, one-sided deny-only revocation, fresh-QR replacement, active/waiting room closure, idempotent `transition_id`, and a read-only authenticated status response carrying the signed winning state. The status operation must not renew a lease, extend expiry, authorize a key, or create another epoch.

These are reviewed design requirements, not current wire behavior. Current crypto v2, paired allocation v2, schema v4, local direct transport, and explicit development relay compatibility remain unchanged until the recommendations are selected and a versioned implementation is approved. No automatic production downgrade to the current plain control protocol is allowed.

v0.1 uses length-prefixed JSON messages between a client app and AetherLink Runtime on a runtime host. The current implementation has mobile-client and desktop-runtime targets, but the protocol boundary is OS-neutral: the client must never call Ollama or LM Studio directly, and all model access goes through the trusted runtime.

Each JSON envelope is UTF-8 encoded and prefixed by a 4-byte big-endian unsigned length. This framing is for v0.1 development transport and can be reused inside, or replaced by, an end-to-end encrypted channel over local direct, remote P2P, or encrypted blind relay/TURN-style connectivity later.

## Relay Allocation Cross-Process Ownership No-Device Gate

- A durable schema-v4 allocation registry is coordinated by one stable mode-`0600` transaction marker file with a fixed-format `U`/`A`/`E` state and a 64-character lowercase hexadecimal coordination token. The schema-v4 store carries the same token, binding the store to that marker.
- POSIX `F_SETLK` byte range 0 serializes every reload, binding lookup, proposal revalidation, compare-and-swap, commit, paired claim or renewal, and tombstone lookup. Blocking acquisition uses a five-second monotonic retry deadline. Byte range 1 is the `RelayServer` lifetime owner lock. The process-local pool keys entries by marker inode, reuses the pooled descriptor, and retains only duplicate descriptors that cannot safely be closed while process locks may exist.
- Compare-and-swap remains binding-aware after reload. Disjoint relay-ID commits are merged, while competing creates for one relay ID and competing paired claims from one bootstrap produce one commit and one `allocationConflict`. A stale create cannot restore a consumed bootstrap ID. The winning pair binding and consumed-bootstrap tombstone persist in one atomic envelope.
- Store operations are descriptor-relative through `openat`, `fstatat`, `renameat`, and `unlinkat`, use `O_NOFOLLOW`, and require a current-user-owned regular file with `nlink == 1` beneath a secure parent that is not group- or world-writable. Persistence reconciles with an owner-only temporary file, file `fsync`, atomic rename, and directory `fsync`.
- A missing established store, dangling symlink, hard link, case/path alias, marker replacement, or store/marker token mismatch fails closed. A valid unversioned `rt1` store is recognized, but because its identity cannot be migrated, all leases are revoked and persisted as an empty token-bound schema-v4 store.
- A token-matched schema-v4 store left beside a `U` marker after interrupted first initialization is recovered and advanced to `E`; other unexpected marker/store combinations fail closed. A second relay process using the same store fails before an independent matcher or active-room state can form. A concurrent `run()` on the same server instance fails without releasing the original listener. Bind failure releases byte range 1. Simultaneous first startup converges on one owner, process exit releases ownership, and a successor can acquire the same marker and store.
- Ephemeral loopback allocation registries remain intentionally process-local and do not claim durable ownership.
- Final evidence covers 64 `RelayAllocationTests`, 21 relay socket tests, 100 related relay tests, 797 full Swift tests, the actual-process ownership smoke, and `build/qa/check-no-device-quality-relay-cross-process-ownership-20260710.log`. The aggregate gate passed with 41 authenticated relay connections and 688 encrypted frame bodies. This is cooperative single-host advisory locking, not distributed consensus, allocation-channel TLS/server authentication, immediate revocation, production P2P/NAT traversal, or physical Android proof. The phone is disconnected.

## Pair-Scoped Relay Room Isolation No-Device Gate

- Paired allocation authorization uses `runtime-client-p256-v2` and protocol version 2. Runtime and client signatures bind both `current_relay_id` and `next_relay_id` under role-separated v2 contexts.
- A first `claim` must rotate from the runtime-only QR bootstrap ID to the deterministic pair ID derived from route token, runtime fingerprint, and client fingerprint. A later `renew` stays on that pair ID; schema-v3 paired records rotate once during schema-v4 migration.
- Relay allocation schema v4 atomically replaces the consumed bootstrap record with the pair record and persists a closed `consumed_bootstrap_allocations` tombstone. Reallocating a consumed bootstrap ID fails closed.
- Paired client socket admission uses `paired-client-p256-v1`. The relay challenges the QR-pinned client key before matcher insertion and binds the proof to relay ID, lease, nonce, both fingerprints, generation, session nonce, ephemeral key, and challenge expiry.
- `RelayMatcher` retains explicit waiting and active room state. A room accepts only an exact generation/nonce/owner binding, rejects duplicate pairs while active, releases on bridge close, and closes stale waiting peers after renewal.
- macOS stores pair routes by client fingerprint in a strict schema-v1 envelope and keeps each relay secret in the secret store, not UserDefaults. It keeps separate relay transports for pair rooms and rotates the global bootstrap token after a successful first claim so future QR pairing does not reuse a consumed room.
- Android derives and validates the expected pair ID before signing, persists the returned pair ID and generation, authenticates with its persistent P-256 key before relay `ready`, and rejects missing admission challenges as downgrade.
- Focused no-device tests cover shared digests, schema-v4 migration/tombstones, client admission, two simultaneous pair rooms with no frame cross-talk, pair-route persistence, response-before-activation ordering, Android route switching, and strict reconnect admission.
- Remaining limits: allocation transport has no TLS/server authentication or service-signed response; relay-side allocation revocation is lease-based; production P2P/NAT traversal and physical optical/different-network proof remain incomplete.
- No physical Android was connected for this slice.

## Message Envelope

Every message includes `type`, `timestamp`, and `payload`. Messages tied to a request, response, stream, cancel, or error include `request_id`; v0.1 should include it on every runtime socket message for simpler tracing.

```json
{
  "version": 1,
  "type": "models.list",
  "request_id": "req_001",
  "timestamp": "2026-06-23T09:00:00Z",
  "payload": {}
}
```

Rules:

- `version` is `1`.
- `type` must be a string. Missing or non-string envelope message types return `invalid_payload` at decode time before authentication checks, backend dispatch, route refresh, or runtime store mutation. Unknown string message types decode successfully and return `unknown_message_type`.
- `version` must be `1`. Missing or mistyped envelope versions return `invalid_payload` at decode time, and unsupported integer envelope versions return `invalid_payload` after decode but before authentication checks, backend dispatch, route refresh, or runtime store mutation.
- `request_id` must be a non-blank string. Missing or non-string envelope request ids return `invalid_payload` at decode time, and blank envelope request ids return `invalid_payload` after decode but before authentication checks, backend dispatch, route refresh, or runtime store mutation.
- `timestamp` must be an ISO-8601 UTC string. Missing, non-string, or malformed envelope timestamps return `invalid_payload` at decode time before authentication checks, backend dispatch, route refresh, or runtime store mutation.
- `payload` is always an object. Missing or non-object payload values return `invalid_payload` at decode time before authentication checks, backend dispatch, route refresh, or runtime store mutation.
- Unknown top-level envelope metadata fields return `invalid_payload` at decode time before authentication checks, backend dispatch, route refresh, or runtime store mutation. Route, backend, workspace, source, permission, and other future metadata must live in the explicitly versioned message payload or QR schema that owns it, not as ad hoc envelope fields.
- Responses reuse the originating `request_id`.
- Streaming messages reuse the `chat.send` `request_id`.
- Unknown message types return `error` with `code = "unknown_message_type"`.
- Runtime-to-client response message types sent by clients return `error` with `code = "unexpected_message_direction"`.
- Invalid payloads return `error` with `code = "invalid_payload"`.

## Connection Lifecycle

1. AetherLink Runtime starts the runtime connection manager.
2. The runtime host shows QR pairing data generated by AetherLink Runtime.
3. The client app scans the QR code and signs `pairing.request` with its persistent device key, binding the request id, QR credentials, both identities, and current transport binding.
4. AetherLink Runtime verifies the client proof inside an active pairing window before reserving the request and storing the trusted client identity/key.
5. The runtime signs the accepted `pairing.result`; the client stores the trusted runtime identity/key only after the request digest, QR-pinned runtime key, and transport binding verify.
6. For later sessions, the connection manager resolves ordered route candidates from the paired runtime identity.
7. The connection manager targets the paired runtime identity, not a raw endpoint. Product builds use QR-bootstrapped overlay material to resolve local, P2P, or relay routes without user-entered endpoints.
8. The v0.1 direct endpoint hint, when present, is one developer/local diagnostic candidate only. It is not required for product pairing and must not become the normal reconnect model.
9. If QR pairing supplied complete development relay metadata, the current client can prepare a relay route and connect outbound to the relay by `relay_id`; this remains diagnostics/development transport.
10. Future production builds should replace this temporary route with a private per-user encrypted overlay: remote P2P NAT traversal candidates gathered through STUN-like address discovery, authenticated hole punching, paired-identity-bound key exchange, and encrypted blind relay/TURN-style fallback.
11. After a transport path is established, the client app sends `hello` with its persisted device id.
12. AetherLink Runtime verifies that the device is trusted and replies with `auth.challenge`.
13. If the client pinned a runtime public key during QR pairing, the client verifies the runtime proof in `auth.challenge` before signing anything.
14. The client app signs a domain-separated client-auth message for the challenge and sends `auth.response`.
15. AetherLink Runtime accepts the authenticated runtime session. Production end-to-end transport encryption remains a hardening milestone beyond the current development transport.
16. The client app sends `runtime.health`.
17. AetherLink Runtime replies with runtime/Ollama/LM Studio status.
18. The client app sends `models.list`.
19. AetherLink Runtime returns installed local backend models and optional running status.
20. If the client app requests installation of an Ollama model name, it sends `models.pull`.
21. AetherLink Runtime calls Ollama `/api/pull` on the runtime host and reports the result.
22. The client app sends `chat.send` for an installed model.
23. AetherLink Runtime streams `chat.delta` and finishes with `chat.done`.
24. The client app may ask AetherLink Runtime for runtime-owned session summaries with `chat.sessions.list`.
25. The client app may ask AetherLink Runtime for a stored transcript with `chat.messages.list`.
26. The client app may ask AetherLink Runtime for a short generated chat title with `chat.title.request`.
27. The client app may rename a runtime-owned session with `chat.session.rename`.
28. The client app may archive, restore, or delete runtime-owned sessions with `chat.session.archive`, `chat.session.restore`, and `chat.session.delete`.
29. The protocol still defines authenticated `route.refresh` for explicit diagnostic or test coverage of fresh remote route material before an existing QR-provisioned route expires. The Android product default does not advertise or automatically send it; normal users refresh routes by scanning the latest QR. The current implementation can carry relay lease material and opaque P2P rendezvous material, but the P2P material is still only route record renewal, not real NAT traversal.
30. The client app may list runtime-generated review drafts for long-inactive chat memory summaries with `memory.summary.drafts.list`.
31. The client app may ask an installed runtime-host local chat model to replace a deterministic draft preview with a cached review-required summary using `memory.summary.draft.generate`.
32. The client app may approve one long-inactivity memory summary draft into runtime-owned memory with `memory.summary.draft.approve`.
33. The client app may dismiss one long-inactivity memory summary draft without writing runtime-owned memory with `memory.summary.draft.dismiss`.
34. The client app may send `chat.cancel` for an active request.

Runtime commands are gated after pairing. `runtime.health`, `models.list`, `models.pull`, `route.refresh`, `index.documents.list`, `retrieval.query`, `source_anchor.resolve`, `citation.resolve`, `trusted_source.approve`, `trusted_source.dismiss`, `trusted_source.list`, `trusted_source.revoke`, `research.brief.create`, `research.notebooks.list`, `chat.send`, `chat.source_attribution.resolve`, `chat.sessions.list`, `chat.messages.list`, `chat.title.request`, `chat.session.rename`, `chat.session.archive`, `chat.session.restore`, `chat.session.delete`, `memory.list`, `memory.upsert`, `memory.delete`, `memory.duplicate_suggestions.list`, `memory.semantic_duplicate_suggestions.list`, `memory.semantic_duplicate_clusters.list`, `memory.summary.drafts.list`, `memory.summary.draft.generate`, `memory.summary.draft.approve`, `memory.summary.draft.dismiss`, and `chat.cancel` require an authenticated session; unauthenticated requests return `authentication_required`. The runtime must continue checking that the authenticated device id is still present in the trusted-device store before accepting later commands. If trust is removed while a connection is still open, the next command fails with `pairing_required` and the cached authenticated session is cleared.

The authentication flow is part of the v0.1 product contract even if a development build uses minimal local transport plumbing while the channel is being hardened.

## Strict Relay Crypto V2 And Authentication Binding

Strict allocated encrypted relay connections use crypto v2. Each endpoint generates a fresh P-256 ephemeral key and 128-bit session nonce before opening the TCP connection. Its registration is exactly:

```text
AETHERLINK_RELAY <client|runtime> <relay_id> crypto=2 session_nonce=<32-lowercase-hex> ephemeral_key=<130-lowercase-hex>
```

The ephemeral key is the canonical 65-byte ANSI X9.63 uncompressed point `04 || X || Y`. Endpoints validate that the peer point is on P-256. The relay validates only canonical field shape, returns `AETHERLINK_RELAY registered crypto=2`, and then sends the opposite peer metadata as `AETHERLINK_RELAY ready crypto=2 peer_session_nonce=<32-lowercase-hex> peer_ephemeral_key=<130-lowercase-hex>`.

Both endpoints perform P-256 ECDH and build this exact UTF-8 transcript without a final newline:

```text
AetherLink relay session binding v2
crypto_version
2
relay_id
<relay-id>
route_nonce
<route-nonce-or-empty>
client_session_nonce
<client-session-nonce>
runtime_session_nonce
<runtime-session-nonce>
client_ephemeral_key
<client-key>
runtime_ephemeral_key
<runtime-key>
```

`transport_binding` is the lowercase hexadecimal SHA-256 digest of those bytes. HKDF-SHA256 uses the raw binding digest as salt and `ECDH_shared_secret || UTF8(relay_secret)` as input key material. Separate expansion labels derive the confirmation key, client traffic secret, and runtime traffic secret: `AetherLink relay confirmation v2`, `AetherLink relay client traffic v2`, and `AetherLink relay runtime traffic v2`.

The confirmation proof is HMAC-SHA256 over `AetherLink relay key confirmation v2\nrole\n<role>\ntransport_binding\n<binding>`. Peers exchange the existing control-line shape before frame ciphers become active:

```text
AETHERLINK_RELAY confirm <role> binding=<transport_binding> proof=<lowercase-hmac-sha256>
```

The client sends role `client`; the runtime validates it and replies with role `runtime`. Strict peers reject missing, malformed, wrong-role, wrong-binding, or wrong-proof lines and do not fall back to crypto v1. Only after both proofs succeed does the transport expose `TransportSecurityContext(bindingID: transport_binding)` and install the directional AES-GCM frame ciphers.

Each direction maintains an implicit ordered frame index. Epoch keys rotate every 65,536 frames by applying HMAC-SHA256 to the direction's traffic secret with `AetherLink relay frame epoch v2\n || direction || UInt64BE(epoch)`. AES-GCM nonces use `direction || UInt64BE(sequence)`, where `sequence = frame_index & 0xffff`; authenticated data binds the v2 frame label, binding digest, direction, epoch, and sequence. A failed authentication does not advance the receive index, replay or reordering fails against the next expected index, and both implementations reject `Int64.max` before cryptography rather than wrapping a counter.

On that bound transport, `hello`, `auth.challenge`, the client `auth.response`, and the accepted authentication result carry the exact `transport_binding`. Runtime and client signatures use these v2 domain-separated bytes:

```text
AetherLink runtime auth challenge v2
<device-id>
<auth-nonce>
<transport-binding>

AetherLink client auth response v2
<device-id>
<auth-nonce>
<transport-binding>
```

Missing or mismatched bindings, a v1 signature on a bound strict relay, and a valid signature replayed from an old binding fail before runtime command authorization. Local direct connections and legacy unallocated/plaintext relay diagnostics do not expose a binding and preserve the exact v1 authentication messages.

This is PSK-mixed ephemeral P-256 ECDH plus paired-identity transport binding for the strict development relay. Assuming ephemeral private keys are not retained, recorded traffic remains protected from later compromise of only the QR relay secret. Endpoint-owned allocation v2 keeps that secret out of the default allocation-required relay, but it does not protect a leaked endpoint/QR secret, provide post-compromise security, implement an unordered replay window, authenticate allocation as a paired-device action, or establish complete production end-to-end transport deployment. Local direct connections and legacy unallocated/plaintext relay diagnostics keep their existing plaintext framing and v1 paired-identity authentication.

## Endpoint-Owned Relay Secret Allocation V2

An allocation-required relay accepts this exact request family:

```text
AETHERLINK_RELAY allocate <route_token> crypto=2 [allocation_token=<token>] [preflight=1]
```

When both optional fields are present, `allocation_token` precedes `preflight=1`. Unknown, duplicated, reordered, versionless, auth-alias, requested-secret, or non-v2 forms fail closed before an allocation ticket is issued. `preflight=1` validates the endpoint and response contract without persisting the ticket.

The response begins with `AETHERLINK_RELAY allocation ` followed by one JSON object containing exactly these fields:

```json
{
  "relay_id": "<opaque-relay-id>",
  "relay_expires_at": 4102444800000,
  "relay_nonce": "<fresh-route-nonce>",
  "crypto_version": 2
}
```

The allocation service does not accept or return `relay_secret`. The runtime host generates or reuses a cryptographically random 32-byte base64 traffic secret locally, stores it through the existing secret-store boundary, and attaches it to the allocated relay metadata only when building endpoint route material such as the pairing QR or explicitly enabled authenticated `route.refresh`. Persisted relay tickets contain only the opaque relay id, expiry, and nonce. Legacy secret-bearing allocation is isolated to explicit non-allocation-required diagnostics and cannot issue a ticket usable by the strict allocation-required server.

Fixed IP/manual host entry, raw local host/port from QR data, USB reverse/dev-server localhost forwarding, mDNS/Bonjour service records, and `relay_host` development relay metadata are v0.1 development reachability hints. They are route candidates only, not the final product connection model. Current code implements a temporary outbound TCP relay path. QR-provisioned relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, so the client and runtime encrypt relay frame bodies with AES-GCM while the relay still only matches peers by `relay_id`, and stale QR route material is rejected before relay socket setup. Strict allocated encrypted connections also require fresh client/runtime 128-bit canonical lowercase hexadecimal session nonces; both peers bind the ordered nonce pair into frame-key derivation so reconnect counters do not restart under the prior key. The no-device paired allocation gate now authorizes claim and renewal for one pinned runtime/client key pair, but the code still does not implement the production private per-user encrypted overlay, real NAT traversal, decentralized signaling, global room or multi-client isolation, immediate revocation, post-compromise recovery, complete replay defense, or complete production end-to-end transport deployment. Pure mDNS/local IP discovery and raw local sockets cannot guarantee connectivity when the client device and runtime host are on different networks.

A future DHT-like or bootstrap-peer discovery layer may help paired devices exchange short-lived rendezvous records. Those records should be derived from paired-device secrets or rotating route tokens, not stable public device ids. Bootstrap peers are optional connectivity infrastructure; they are not accounts, not cloud backend state, not trust authorities, and not a place where AI protocol payloads or backend URLs appear.

Bonjour/local discovery records should include minimal routing hints when available. The preferred local TXT metadata is a pairing-derived `route_token`, not a stable public device id. The client app must only auto-route a pinned trusted runtime identity to discovered endpoints whose hints match the trusted runtime record. Stable `device_id` and `fingerprint` TXT hints remain legacy/development fallback metadata only. A discovered endpoint with no identity metadata, or with metadata that cannot be matched to the trusted record, is a local/dev/manual reachability candidate only and must not be promoted to an automatic trusted-identity match.

Discovery identity hints must not contain backend URLs, Ollama/LM Studio host details, model names, provider health, prompts, files, memory, or other runtime payload metadata. These hints only help pick a candidate endpoint before authentication. They are not a substitute for QR pairing, pinned runtime identity, challenge-response authentication, or end-to-end encryption.

## Document Catalog And Retrieval Messages

`index.documents.list` is the active read-only runtime document catalog message. Its request payload may be empty or may include `limit` as an integer from 0 through 100. Its response contains a `documents` array capped at 100 rows and a `summary` object. Each document row is metadata-only: `id`, `display_name`, `mime_type` as a runtime-canonical lowercase `type/subtype` token capped at 128 characters, `content_fingerprint` as a 16-character lowercase hex value, `extracted_character_count`, `chunk_count`, and `quality`; `id` is capped at 128 characters and `display_name` is capped at 256 characters. Document `quality` is derived from `chunk_count`: `0` maps to `no_usable_text`, `1` maps to `single_chunk`, and `2` or more maps to `chunked`. The summary `quality_counts` object always contains `no_usable_text`, `single_chunk`, and `chunked` integer counts, including zero values for qualities that are absent from the current catalog. The response must not carry chunk text, chunk IDs, source paths, workspace or project IDs, retrieval context, embeddings, citations, trusted-source fields, approval state, backend URLs, or route material.

`retrieval.query` is the active read-only document retrieval message with a deterministic lexical default and explicit approved semantic opt-in. Its request payload requires nonblank `query` text capped at 1024 characters and may include `limit` from 0 through 100, `max_snippet_characters` from 0 through 500, and nonblank provider-qualified `embedding_model_id`. A zero snippet ceiling is normalized to one character so every emitted row remains schema-valid. Omitting the model hint preserves lexical ranking and the legacy response key set; supplying it selects approved semantic ranking without a silent lexical fallback. The response `results` array is capped at 100 rows. Each result row contains the same bounded safe document metadata as `index.documents.list`, `source_anchor_id`, `chunk_index`, `start_character_offset`, `end_character_offset`, positive integer `rank`, required `matched_terms` capped at 16 terms of 64 characters each, and non-empty response `snippet` capped at 500 characters. Missing or explicit lexical `match_kind` requires non-empty `matched_terms`; explicit semantic origin may carry an empty array of honest lexical overlaps. The lexical runtime omits `match_kind`, while opted-in semantic results require `match_kind: semantic`. Character offsets are zero-based half-open ranges, so `end_character_offset` must be greater than or equal to `start_character_offset`. Clients must treat positive `rank` as implementation metadata, not a cross-model relevance score. `source_anchor_id` is response-only metadata for `retrieval.query` requests and must match `source_anchor_[16 lowercase hex]`.

`source_anchor.resolve` remains the minimal active read-only runtime source-anchor resolver. Its request payload accepts only `source_anchor_id`. Its response returns only `source_anchor_id`, `document`, and `chunk_summary`, where `document` uses the same safe metadata-only document shape as `index.documents.list`, and `chunk_summary` contains `chunk_index`, `start_character_offset`, `end_character_offset`, and `character_count`. A syntactically valid but stale anchor can return `source_anchor_not_found`. Citation/review state is available only through the explicit messages in the citation contract; this minimal resolver still returns no citation, trusted-source, approval, body, snippet, path, model, backend, or route metadata.

These document and citation messages remain runtime-owned. Host-reviewed `runtime_shared` approval, semantic ranking, internal candidate-vector caching, content-free audit, and device-scoped trusted-source review grants are active. They do not add client-controlled embedding generation, host approval controls, local result persistence, chat context injection, direct Android backend access, or production relay/session encryption.

For active legacy and lexical rows, the historical wire rule remains non-empty `matched_terms` capped at 16 terms of 64 characters each. The semantic exception applies only when `match_kind` is explicitly `semantic`. Android sends the selected runtime-host embedding model only with a valid bounded document query and retries one exact older-runtime unsupported-field rejection without the hint.

## QR Pairing Data

AetherLink Runtime displays a QR code containing pairing data encoded as a URI. The canonical URI form is `aetherlink://pair?...`; path-only custom-scheme forms such as `aetherlink:/pair?...` are not product QR output because Android intent routing is not consistently delivered to the app for hostless custom-scheme paths. Product QR payloads are versioned and must include `version=1` or compact `v=1`; unversioned or unsupported-version pair URIs are not accepted as valid pairing payloads. Normal product client scans also require `runtime_public_key`, `route_token`, and complete remote route material such as relay or future P2P rendezvous data. Product pairing is QR-only from the user's perspective: the user scans a QR to pair or refresh routes, and the client never asks for hostnames, ports, Ollama URLs, LM Studio URLs, or other backend URLs. For different-network use, the QR must bootstrap overlay/rendezvous/relay material. Identity-only QR remains a compatibility or diagnostic parser shape that can establish trust only when explicit tooling opts out of remote-route enforcement; it cannot make raw local sockets work across unrelated networks and is rejected by the normal product scan path.

The active runtime socket message schema is `packages/protocol-schema/protocol.schema.json`. The decoded `aetherlink://pair` query payload is intentionally separate and is documented by `packages/protocol-schema/pairing-qr.schema.json`; route bootstrap secrets belong in the QR payload, not in `pairing.request`.

```text
aetherlink://pair?version=1&pairing_nonce=<nonce>&pairing_code=<6-digit-code>&runtime_device_id=<stable-runtime-id>&runtime_name=AetherLink%20Runtime&runtime_key_fingerprint=<runtime-key-fingerprint>&runtime_public_key=<base64-runtime-public-key>&route_token=<paired-route-token>
```

Canonical field names remain the documentation/debugging form. App-displayed camera QR codes may use compact aliases to reduce QR density and improve optical scanning reliability. For example, `pairing_nonce`/`pairing_code`/`runtime_device_id`/`runtime_name`/`runtime_key_fingerprint`/`runtime_public_key`/`route_token` may be encoded as `n`/`c`/`rid`/`rn`/`rf`/`rk`/`rt`, and relay route material may be encoded as `rh`/`rp`/`ri`/`rs`/`rx`/`rrn` for `relay_host`/`relay_port`/`relay_id`/`relay_secret`/`relay_expires_at`/`relay_nonce`. The client accepts canonical names, compact aliases, and earlier compatibility aliases such as `mac_device_id`, `mac_name`, and `fingerprint`, but a decoded QR query key must not appear more than once. Semantic aliases for the same QR field must not be mixed in one payload; Android rejects conflicts such as `runtime_device_id` plus `rid`, `route_token` plus `rt`, or competing `relay_scope`/`route_scope`/`rsc` values before field selection. The shared pairing QR schema now rejects the same semantic alias conflicts for version, pairing nonce/code, runtime identity/name/key material, route token, diagnostic local endpoint, relay id, and relay scope, so QR artifacts cannot validate by carrying contradictory decoded aliases. Rendered QR artifact verification applies the same semantic alias rejection before accepting no-device QR evidence. Rendered QR artifact verification also rejects mixed relay and P2P alias families, accepts complete `rendezvous_*` relay route material, and rejects whitespace-mutated relay secrets before accepting no-device QR evidence. Repeated query keys are rejected before field selection so a QR cannot rely on last-wins parsing for identity or route material. Unknown decoded query keys are rejected instead of ignored, matching the shared pairing QR schema's closed field set. It also accepts complete `remote_*`, `route_*`, and `rendezvous_*` relay alias families; each family must include host, port, id, secret, expiration, and nonce together so partial QR route material is rejected before connection setup. Relay route material from different alias families is not combined into one route. The shared pairing QR schema rejects mixed relay alias families and mixed relay-scope aliases before a decoded QR payload can be treated as valid. Semantically, all QR identity fields identify the trusted runtime host.

The fingerprint identifies the runtime identity that the client app pins after a successful pairing result. QR payloads include `runtime_key_fingerprint`; normal product QR scans require `runtime_public_key`, while compatibility or diagnostic payloads may omit it only when explicit tooling opts out of production bootstrap enforcement. The accepted `pairing.result` must confirm the same runtime identity metadata before the client stores trust. `service_type`, when present from legacy or diagnostic emitters, is a discovery hint only and is limited to the AetherLink mDNS service names `_aetherlink._tcp.`, `_aetherlink._tcp.local.`, `_localagentbridge._tcp.`, or `_localagentbridge._tcp.local.`. It must not carry backend URLs, provider names, model identifiers, model commands, or runtime payload metadata. The trusted runtime record stores identity/key material and `route_token` first. Normal client pairing does not persist QR `host`/`port` as a trusted reconnect route. Local direct endpoint hints are accepted only by explicit diagnostic tooling and are never the trusted identity or product address.

Development QR payloads may include temporary local direct route hints:

```text
aetherlink://pair?version=1&pairing_nonce=<nonce>&pairing_code=<6-digit-code>&runtime_device_id=<stable-runtime-id>&runtime_name=AetherLink%20Runtime&runtime_key_fingerprint=<runtime-key-fingerprint>&runtime_public_key=<base64-runtime-public-key>&route_token=<paired-route-token>&host=<runtime-host>&port=43170&route_scope=local_diagnostic
```

`host` and `port` are developer/local diagnostic route candidates only and require explicit diagnostic scope such as `route_scope=local_diagnostic`. Product client parsing rejects identity-plus-direct-endpoint QR payloads by default. Product reconnect should use the paired runtime identity/key plus QR-bootstrapped overlay material so the connection manager can resolve current local discovery, remote P2P NAT traversal, or encrypted blind relay/TURN-style routes automatically. Identity-only QR pairing can establish trust and later resolve local routes, but it cannot cross unrelated networks without relay or P2P rendezvous material in the QR.

AetherLink Runtime's normal QR generation path must not silently fall back to `host`/`port` when the user expects QR-only different-network pairing. Local direct QR hints are an explicit diagnostic/development policy; the default product path requires remote route material such as relay or future P2P rendezvous data.

Remote-route QR payloads include the current temporary relay route:

```text
aetherlink://pair?version=1&pairing_nonce=<nonce>&pairing_code=<6-digit-code>&runtime_device_id=<stable-runtime-id>&runtime_name=AetherLink%20Runtime&runtime_key_fingerprint=<runtime-key-fingerprint>&runtime_public_key=<base64-runtime-public-key>&route_token=<paired-route-token>&relay_host=<relay-host>&relay_port=43171&relay_id=<private-network-id>&relay_secret=<pairwise-frame-secret>&relay_expires_at=<epoch-ms>&relay_nonce=<route-nonce>
```

The equivalent compact camera QR form is:

```text
aetherlink://pair?v=1&n=<nonce>&c=<6-digit-code>&rid=<stable-runtime-id>&rn=AetherLink%20Runtime&rf=<runtime-key-fingerprint>&rk=<base64-runtime-public-key>&rt=<paired-route-token>&rh=<relay-host>&rp=43171&ri=<private-network-id>&rs=<pairwise-frame-secret>&rx=<epoch-ms>&rrn=<route-nonce>
```

`relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce` are required route material for the current QR relay path. `relay_id` must be explicit route material; `route_token` is a paired-runtime routing token and is not accepted as a fallback relay id. The shared pairing QR schema caps opaque route values, ids, tokens, nonces, and secrets at 512 characters before client-specific parser handling. macOS QR generation omits malformed optional opaque route material before emission: whitespace-mutated or oversized runtime public keys, route tokens, relay ids/secrets/nonces, P2P record ids, P2P bodies, and P2P anti-replay nonces are not serialized into the camera QR, and invalid relay or P2P material prevents that complete route family from being emitted. macOS QR generation also omits relay/P2P route families with invalid relay ports or non-positive route expiries before camera QR emission. macOS QR generation also omits relay route families when `relay_host` and `relay_scope` do not match the shared schema policy: public or DNS hosts use no scope or `remote`, private/CGNAT/ULA hosts require `private_overlay`, and loopback hosts require `usb_reverse`. When relay route material is emitted, macOS QR generation emits the normalized relay host value used for the eligibility decision instead of the raw configured host: DNS names are lowercased without a trailing dot, and bracketed IPv6 literals are serialized without brackets. `relay_scope`, when present on a relay route, must exactly match one of `remote`, `private_overlay`, or `usb_reverse`. `route_scope` is a relay-scope alias for `route_*` relay material, and compact `rsc` is a relay-scope alias for compact relay material; `route_scope=local_diagnostic` remains only for explicit local-direct diagnostic QR payloads. `relay_secret` is shared only through QR pairing and is not sent in the relay registration line. `relay_expires_at` is an epoch-millisecond expiration, and `relay_nonce` is pairwise anti-replay material for the fresh QR route attempt. After pairing succeeds, the client persists the trusted runtime identity plus the current relay host/id/secret/lease/nonce route material. The trusted-device relationship is long-lived, but the saved relay lease is not; if it expires or is incomplete, normal Android product builds guide the user to scan a fresh QR. Authenticated relay refresh remains available only when explicitly enabled for diagnostic or test coverage; when enabled, it may preserve a stable relay id or frame secret, but the client rejects a refresh that reuses the current relay nonce or does not advance `relay_expires_at`. The current relay uses outbound TCP from both peers and forwards bytes after matching one runtime and one client by `relay_id`. AetherLink frame bodies over QR-provisioned relay routes are encrypted with AES-GCM using direction-bound nonces (`CLNT` for client-to-runtime, `RUNT` for runtime-to-client). The frame key is derived from the QR-provisioned `relay_secret` and `relay_nonce`, so a route lease with the same secret but a different nonce cannot decrypt frames from another lease. This supports QR-only different-network development testing when a mutually reachable, QR-eligible relay is configured because Android scans the route QR, stores the remote route with the pinned runtime identity, and does not ask for a host or port. It is still not a complete production relay/TURN system.

For a strict allocated encrypted connection, runtime and client use the crypto v2 registration, ECDH, transcript confirmation, and directional epoch framing defined above. Legacy unallocated/plaintext `--allow-legacy` diagnostics alone retain the 3-token registration and plain `AETHERLINK_RELAY ready`; strict and legacy peers reject cross-mode handshakes rather than downgrading.

P2P rendezvous QR payloads use a separate route namespace:

```text
aetherlink://pair?v=1&n=<nonce>&c=<6-digit-code>&rid=<stable-runtime-id>&rn=AetherLink%20Runtime&rf=<runtime-key-fingerprint>&rk=<base64-runtime-public-key>&rt=<paired-route-token>&pc=p2p_rendezvous&prid=<opaque-record-id>&peb=<opaque-encrypted-candidate-body>&px=<epoch-ms>&pn=<anti-replay-nonce>&pv=1
```

`p2p_class=p2p_rendezvous`, `p2p_record_id`, `p2p_encrypted_body`, `p2p_expires_at`, `p2p_anti_replay_nonce`, and `p2p_protocol_version=1` are a complete canonical family; `pc`, `prid`, `peb`, `px`, `pn`, and `pv` are the compact family for the same material. The P2P protocol version query value must be exactly `p2p_protocol_version=1` or `pv=1`; leading-zero or plus-prefixed values such as `01` or `+1` are invalid. P2P rendezvous route material from canonical and compact alias families is not combined into one route; a QR must use one P2P alias family for a complete P2P route. P2P aliases must not be mixed into the relay alias families. The shared pairing QR schema rejects mixed canonical/compact P2P alias families, caps opaque P2P encrypted bodies at 2048 characters, and caps other P2P route values/nonces at 512 characters. Android drops incomplete or expired P2P rendezvous material and stores complete future records only as opaque route material bound to the pinned runtime identity. The P2P body is treated as encrypted candidate material for a future connector; current code does not decrypt it, exchange candidates, run STUN, punch holes, or complete a real P2P connection.

Development USB smoke tests may add `relay_scope=usb_reverse` when the relay host is loopback and adb reverse maps the phone's loopback port to the runtime host. This is accepted only by debug clients for validation. The shared pairing QR schema mirrors this debug exception by accepting loopback relay hosts only when the decoded artifact carries an exact `usb_reverse` scope; release/product clients may still reject them by policy. Normal QR pairing rejects loopback, `.local`, unspecified, link-local, and multicast relay hosts. Carrier-grade NAT, private IPv4, and ULA IPv6 relay literals require explicit private-overlay opt-in before QR generation can include `relay_scope=private_overlay`; that scope means the user controls a VPN, tunnel, or private overlay that makes the route reachable from both paired devices. Scope-less private relay literals remain invalid because they otherwise look like same-network fixed IPs.

When Bonjour/local discovery is available after pairing, TXT hints should prefer the QR-provided `route_token` so the client app can match the trusted runtime to a current local endpoint without publishing stable identifiers. Legacy/development TXT hints may include `device_id` or `fingerprint`, but production discovery should not rely on broadcasting stable peer identifiers. Those TXT hints are only routing metadata; they must not disclose backend URLs, model inventory, or provider state, and they do not authenticate the endpoint by themselves.

The client app still talks only to the trusted runtime; Ollama and LM Studio stay behind the runtime host adapter.

Development bootstrap relay configuration may name one endpoint with `AETHERLINK_BOOTSTRAP_RELAY_HOST/PORT` or multiple failover endpoints with `AETHERLINK_BOOTSTRAP_RELAY_ENDPOINTS` before QR generation. Those environment variables select where the runtime obtains temporary relay route material; they are not included as backend URLs and they are not production NAT traversal. `AetherLinkRelay` requires allocation by default, rejects unknown or expired relay ids, and issues short-lived route leases. Explicit legacy relay-id handshakes require diagnostic `--allow-legacy` mode.

## Connection Metadata And Relay Boundaries

Signaling or relay messages are outside the AI protocol payload. If AetherLink uses a signaling, STUN-like, or TURN-style component, it may exchange only reachability metadata such as device-presence hints, public-reflexive address candidates, short-lived connection candidates, relay allocation identifiers, and opaque encrypted packets. It must not receive unencrypted `runtime.health`, `models.list`, `models.pull`, `chat.send`, `chat.delta`, `chat.done`, `chat.cancel`, prompts, responses, files, memory, model lists, or backend credentials in production. The current development relay forwards the frame stream without parsing AI protocol payloads; QR relay routes require `relay_secret`, `relay_expires_at`, and `relay_nonce`, so those frame bodies are encrypted before they reach the relay and stale QR route material is rejected. This is still not the final production security model.

The target end-to-end encryption boundary is between the paired client app and runtime host. Relay infrastructure must not terminate that session, authenticate devices on behalf of the runtime host, or inspect JSON payloads. A relay is therefore not a cloud AI backend.

Bitcoin-network analogy note: AetherLink may use decentralized peer-discovery ideas, but only for finding QR-paired trusted runtime/client identities. It is not a public untrusted network, and unpaired peers must not receive usable routing metadata or AI protocol access.

Route records are defined at the connection overlay layer. See [connection-overlay.md](connection-overlay.md#route-record-contract). The only product target is a paired runtime identity; `host` and `port` remain development/local-direct hints. Future route records should be opaque, expiring, pairwise, replay-protected records such as `local_direct`, `p2p_rendezvous`, and `relay_allocation`. macOS pairing QR generation and Android QR parsing now share a first QR-carried `p2p_rendezvous` family using `p2p_class`, `p2p_record_id`, `p2p_encrypted_body`, `p2p_expires_at`, `p2p_anti_replay_nonce`, and `p2p_protocol_version`, plus compact aliases `pc`, `prid`, `peb`, `px`, `pn`, and `pv`. Android can persist complete P2P rendezvous records as pending pairing route material and, after accepted pairing, same-runtime QR route-refresh scan, or explicitly enabled authenticated `route.refresh` response, as trusted runtime route material for later restore planning. This is QR generation, optional diagnostic route-material renewal, storage, and route planning only, not real NAT traversal.

## `route.refresh`

Direction: Client -> Runtime, then Runtime -> Client with the same `request_id`.

`route.refresh` lets an already-authenticated client ask the paired runtime host for fresh remote route material before QR-provisioned material expires. Android keeps this path disabled by default for normal users so route repair remains a latest-QR scan flow; the message is used only when explicitly enabled for diagnostic and no-device regression coverage. The macOS app runtime also keeps authenticated `route.refresh` unavailable by default and emits fresh route material only when diagnostic route refresh is explicitly opted in. This is not model access, not backend discovery, and not a direct connection to Ollama or LM Studio. It renews client-to-runtime overlay route records only.

Request payload:

```json
{
  "version": 1,
  "type": "route.refresh",
  "request_id": "req_route_refresh_001",
  "timestamp": "2026-06-25T12:00:00Z",
  "payload": {}
}
```

`route.refresh.payload` accepts only an empty object on client requests. Clients must not send response-only relay or P2P route material, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, model commands, or direct-provider route material.

Successful relay response payload:

```json
{
  "version": 1,
  "type": "route.refresh",
  "request_id": "req_route_refresh_001",
  "timestamp": "2026-06-25T12:00:01Z",
  "payload": {
    "runtime_device_id": "stable-runtime-id",
    "runtime_key_fingerprint": "runtime-key-fingerprint",
    "relay_host": "relay.example.test",
    "relay_port": 43171,
    "relay_id": "opaque-relay-id",
    "relay_secret": "pairwise-frame-secret",
    "relay_expires_at": 1782205505000,
    "relay_nonce": "fresh-route-nonce",
    "relay_scope": "remote"
  }
}
```

Successful opaque P2P rendezvous response payload:

```json
{
  "version": 1,
  "type": "route.refresh",
  "request_id": "req_route_refresh_001",
  "timestamp": "2026-06-25T12:00:01Z",
  "payload": {
    "runtime_device_id": "stable-runtime-id",
    "runtime_key_fingerprint": "runtime-key-fingerprint",
    "p2p_class": "p2p_rendezvous",
    "p2p_record_id": "opaque-record-id",
    "p2p_encrypted_body": "opaque-encrypted-candidate-body",
    "p2p_expires_at": 1782205505000,
    "p2p_anti_replay_nonce": "fresh-p2p-route-nonce",
    "p2p_protocol_version": 1
  }
}
```

The runtime must bind successful refresh material to the paired runtime identity with `runtime_device_id` and `runtime_key_fingerprint`. The client must reject a refresh response whose identity fields are missing or do not match the pinned trusted runtime. The runtime may return `route_refresh_unavailable` when no refreshable route is configured, allocation fails, the route is not QR-eligible, or the route scope cannot be represented by the protocol enum. The client should keep the existing trusted runtime identity and fall back to scanning a fresh QR when refresh fails. `relay_host` is route material, not a URL or endpoint. The shared `route.refresh` schema rejects whitespace-mutated, URL-shaped, path-shaped, query, fragment, and user-info-shaped relay hosts before a response is schema-valid. It also rejects mDNS-local, unspecified, link-local, multicast, and broadcast relay hosts. `relay_scope` is optional, but when present it must be exactly one of `remote`, `private_overlay`, or `usb_reverse`; unknown or whitespace-mutated values are invalid and must not be saved as trusted route material. `relay_scope = private_overlay` is allowed only for explicit VPN, tunnel, or private-overlay routes that both devices can reach; scope-less private relay literals stay invalid. Loopback route.refresh relay hosts require `relay_scope=usb_reverse`; scope-less or remote-scoped loopback refresh material is invalid outside explicit USB reverse debugging. The shared `route.refresh` schema enforces both scope contracts before the payload is schema-valid.

Relay route material and P2P rendezvous material are both complete families. If any relay field is present, `relay_host`, `relay_port`, `relay_id`, `relay_secret`, `relay_expires_at`, and `relay_nonce` must all be valid and fresh. If any P2P field is present, `p2p_class=p2p_rendezvous`, `p2p_record_id`, `p2p_encrypted_body`, `p2p_expires_at`, `p2p_anti_replay_nonce`, and `p2p_protocol_version=1` must all be valid and fresh. The shared `route.refresh` schema applies the same size contract as pairing QR: opaque route values, ids, tokens, nonces, and secrets at 512 characters, and opaque P2P encrypted bodies at 2048 characters. Partial or expired families are rejected before trusted route storage. A response may contain relay, P2P, or both families, but P2P data remains opaque route material for a future connector; current code does not decrypt candidates, run STUN, exchange candidates, punch holes, or complete a real P2P connection.

## `pairing.request`

Direction: Client -> Runtime.

After scanning the QR code, the client app connects to the AetherLink Runtime and submits the QR nonce/code plus its own persistent device identity. The AetherLink Runtime accepts this only while the pairing session is active.

QR trust and routing identifiers are opaque canonical values. Clients must reject `pairing_nonce`, `runtime_device_id`, `runtime_key_fingerprint`, `runtime_public_key`, `route_token`, `relay_id`, `relay_nonce`, and `relay_scope` values that are blank, leading/trailing-space mutated, or contain whitespace before they are used for trust storage, discovery matching, or relay routing. Clients must also reject unknown or case-mutated relay scope values instead of normalizing them. Human-facing runtime names may be normalized for display; relay frame secrets remain opaque secret material.

The runtime applies the same fail-closed policy to the client identity submitted in `pairing.request`. `device_id` is an opaque canonical identifier, `device_name` is normalized only for display, and `public_key` must be a canonical Base64-encoded P-256 DER public key that can later verify `auth.response` signatures. `pairing_signature` proves possession of that key. A malformed identity, wrong proof key, transcript mutation, noncanonical key/signature, or unsupported proof scheme returns `pairing.result` with `accepted: false` and `code: "pairing_invalid_device_identity"`; it must not create or update a trusted-device record.

Blank required `pairing.request` fields return `invalid_payload` before failed-attempt accounting or trust mutation. Nonblank but canonicality-mutated `device_id` or `public_key` values still return the structured non-trusting `pairing.result` rejection described above.

```json
{
  "version": 1,
  "type": "pairing.request",
  "request_id": "req_pair_001",
  "timestamp": "2026-06-23T09:00:00Z",
  "payload": {
    "pairing_nonce": "nonce-from-qr",
    "pairing_code": "123456",
    "device_id": "client-device-id",
    "device_name": "Client Device",
    "public_key": "base64-encoded-client-public-key",
    "pairing_proof_scheme": "p256-sha256-der-v1",
    "pairing_signature": "base64-canonical-DER-signature",
    "transport_binding": "64-lowercase-hex-when-present"
  }
}
```

`pairing.request.payload` accepts only `pairing_nonce`, `pairing_code`, `device_id`, `device_name`, `public_key`, `pairing_proof_scheme`, `pairing_signature`, and optional `transport_binding`. A bound relay requires the exact current 64-character lowercase hexadecimal binding; an unbound local diagnostic transport omits the wire field and signs the literal `none`. Clients must not send response-only pairing result fields, runtime identity fields, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-provider route material in this payload.

The client proof transcript starts with `AetherLink initial pairing client proof v1`. It then length-frames, in order, `scheme`, `protocol_version`, `request_id`, `pairing_nonce`, `pairing_code`, `runtime_device_id`, `runtime_public_key`, `runtime_key_fingerprint`, `client_device_id`, `client_device_name`, `client_public_key`, `client_key_fingerprint`, and `transport_binding`. Each field is encoded as field name, canonical decimal UTF-8 byte length, and exact value on separate lines, with no trailing newline. The signature is canonical DER ECDSA P-256 over SHA-256 of those bytes.

## `pairing.result`

Direction: Runtime -> Client.

```json
{
  "version": 1,
  "type": "pairing.result",
  "request_id": "req_pair_001",
  "timestamp": "2026-06-23T09:00:01Z",
  "payload": {
    "accepted": true,
    "mac_device_id": "stable-runtime-id",
    "runtime_device_id": "stable-runtime-id",
    "runtime_public_key": "base64-encoded-runtime-public-key",
    "runtime_key_fingerprint": "runtime-key-fingerprint",
    "trusted_device_id": "android-device-id",
    "message": "Client Device is now trusted by AetherLink Runtime.",
    "pairing_proof_scheme": "p256-sha256-der-v1",
    "pairing_request_digest": "64-lowercase-hex-sha256",
    "runtime_pairing_signature": "base64-canonical-DER-signature",
    "transport_binding": "64-lowercase-hex-when-present"
  }
}
```

If rejected, `accepted` is `false` and `message` explains whether the code expired, credentials were invalid, identity material was malformed, or the active attempt limit was exceeded. Rejections are not trust-creating proof. Android may display a matching unsigned rejection, but it keeps pending QR route material so an unauthenticated rejection cannot erase recovery state. The client persists the trusted runtime only after an accepted result whose request id/digest, trusted client id, runtime id/key/fingerprint, message, signature, and transport binding all verify against the pending request and scanned QR.

Accepted `pairing.result` payloads accept only `accepted`, optional legacy `mac_device_id`, `runtime_device_id`, `runtime_public_key`, `runtime_key_fingerprint`, `trusted_device_id`, `message`, `pairing_proof_scheme`, `pairing_request_digest`, `runtime_pairing_signature`, and optional `transport_binding`. Rejected results use only the rejection/status field family and never carry accepted-result proof fields. Pairing results must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source approval handles, citations, trusted-source review data, audit handles, direct-store metadata, or direct-provider route material. Android clients reject unsupported or unsigned accepted result metadata before trusted-runtime persistence, pending route cleanup, authenticated session state, or runtime refresh fanout.

The runtime result transcript starts with `AetherLink initial pairing runtime result proof v1` and length-frames, in order, `scheme`, `protocol_version`, `request_id`, `pairing_request_digest`, `accepted`, `runtime_device_id`, `runtime_public_key`, `runtime_key_fingerprint`, `trusted_device_id`, `message`, and `transport_binding`. Only `accepted=true` is signed. The runtime signs before trusted-device persistence; the pairing coordinator reserves the verified request and releases the reservation on signing or storage failure before a later retry.

## `hello`

Direction: Client -> Runtime.

After pairing, the client app opens a runtime connection and identifies itself with the persistent device id that the AetherLink Runtime stored during `pairing.request`.

```json
{
  "version": 1,
  "type": "hello",
  "request_id": "req_auth_001",
  "timestamp": "2026-06-23T09:00:00Z",
  "payload": {
    "device_id": "client-device-id",
    "device_name": "Client Device",
    "client_capabilities": ["chat", "streaming", "attachments", "chat.source_attributions.v1", "chat.source_attribution.resolve.v1", "research.notebooks.v1", "research.notebooks.authoritative_sync.v1"]
  }
}
```

`hello.payload` accepts only `device_id`, `device_name`, and `client_capabilities`. Only `device_id` is required, and it must be a non-blank string. When present, `device_name` must be a non-blank string, and `client_capabilities` must be an array of at most 64 unique non-blank strings. Malformed allowed fields return `invalid_payload` before challenge creation. Clients must not send challenge or response fields such as `nonce`, `signature`, `runtime_signature`, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, workspace IDs, permission grants, source paths, source-control state, or direct-provider route material in this payload.

`chat.source_attributions.v1` advertises strict support for the optional safe attribution arrays on `chat.done` and `chat.messages.list`. The runtime preserves this capability across the authentication challenge and emits those arrays only on a connection that advertised it. Clients without the capability retain the legacy response key set even when the runtime stores attribution provenance.

`chat.source_attribution.resolve.v1` advertises support for authenticated historical attribution review. It does not authorize source access. On connections advertising it, attribution-bearing successful completions and assistant history rows also carry the server-generated `assistant_message_id` needed to address `chat.source_attribution.resolve`; every other payload omits that locator.

`research.notebooks.v1` advertises both active research messages. Clients that omit it receive `unsupported_operation` before research payload handling and do not gain notebook metadata or pinned-source behavior.

`research.notebooks.authoritative_sync.v1` advertises strict snapshot-count and cursor pagination for `research.notebooks.list`. It does not add another message type or grant research/source authority; clients still require `research.notebooks.v1` for the research operations themselves.

If the device is not trusted, the AetherLink Runtime returns `error` with `code = "pairing_required"`.

## `auth.challenge`

Direction: Runtime -> Client.

For a trusted device id, the AetherLink Runtime replies with a one-time nonce scoped to the current connection. When the runtime has a signing identity, the challenge also includes a runtime proof: `runtime_signature` signs the domain-separated message `AetherLink runtime auth challenge v1\n<device_id>\n<nonce>` with the runtime private key whose public key/fingerprint was pinned from the pairing QR. Clients that have a pinned `runtime_public_key` must verify this proof before sending `auth.response`.

```json
{
  "version": 1,
  "type": "auth.challenge",
  "request_id": "req_auth_001",
  "timestamp": "2026-06-23T09:00:01Z",
  "payload": {
    "device_id": "android-device-id",
    "nonce": "base64-or-hex-nonce",
    "runtime_key_fingerprint": "runtime-key-fingerprint",
    "runtime_signature": "base64-runtime-signature"
  }
}
```

Runtime `auth.challenge` payloads accept only `device_id`, `nonce`, `runtime_key_fingerprint`, and `runtime_signature`. Auth challenges must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source approval handles, citations, trusted-source review data, audit handles, direct-store metadata, or direct-provider route material. Android clients reject unsupported auth.challenge metadata before device identity loading, runtime proof verification, auth.response signing/sending, authenticated session state, route-refresh scheduling, or runtime refresh fanout.

## `auth.response`

Direction: Client -> Runtime, Runtime -> Client.

The client app signs the domain-separated message `AetherLink client auth response v1\n<device_id>\n<nonce>` with its paired private key. The AetherLink Runtime verifies that exact message against the trusted public key before allowing runtime commands on that connection. A raw nonce signature is not accepted.

```json
{
  "version": 1,
  "type": "auth.response",
  "request_id": "req_auth_001",
  "timestamp": "2026-06-23T09:00:02Z",
  "payload": {
    "device_id": "android-device-id",
    "nonce": "base64-or-hex-nonce",
    "signature": "base64-signature"
  }
}
```

`auth.response` request payload accepts only `device_id`, `nonce`, and `signature`. Those fields must be non-blank strings. Malformed or blank allowed fields return `invalid_payload` before authentication, challenge consumption, or runtime command access. Clients must not send response-only `accepted`, runtime proof fields, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, workspace IDs, permission grants, source paths, source-control state, or direct-provider route material in this payload.

Accepted response:

```json
{
  "version": 1,
  "type": "auth.response",
  "request_id": "req_auth_001",
  "timestamp": "2026-06-23T09:00:03Z",
  "payload": {
    "accepted": true,
    "device_id": "android-device-id"
  }
}
```

Runtime `auth.response` result payloads accept only `accepted`, `device_id`, and `message`. `accepted` is required for a successful result, `device_id` and `message` are optional result metadata, and malformed allowed fields return `invalid_payload` before authenticated runtime access. Auth response results must not carry nonces, signatures, runtime proof fields, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-provider route material. Android clients reject unsupported auth.response result metadata before authenticated session state, route-refresh scheduling, or runtime refresh fanout.

If verification fails, the AetherLink Runtime returns `error` with `code = "authentication_failed"`. If the client app sends a runtime command before this succeeds, the AetherLink Runtime returns `error` with `code = "authentication_required"`.

## `runtime.health`

Direction: Client -> Runtime, Runtime -> Client.

Request:

```json
{
  "version": 1,
  "type": "runtime.health",
  "request_id": "req_health_001",
  "timestamp": "2026-06-23T09:00:00Z",
  "payload": {}
}
```

`runtime.health.payload` accepts only an empty object on client requests. Clients must not send response-only `status`, backend health objects, model residency fields, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, model commands, or direct-provider route material.

Response:

```json
{
  "version": 1,
  "type": "runtime.health",
  "request_id": "req_health_001",
  "timestamp": "2026-06-23T09:00:01Z",
  "payload": {
    "status": "ok",
    "ollama": {
      "available": true,
      "message": "Ollama is reachable from the AetherLink Runtime"
    },
    "model_residency": {
      "supported": true,
      "active_provider": "ollama",
      "active_model_id": "llama3.1:8b",
      "in_flight_generations": 1,
      "idle_unload_delay_seconds": 600,
      "last_unload_failure": {
        "provider": "ollama",
        "model_id": "qwen-local",
        "reason": "model_switch"
      }
    }
  }
}
```

When both local backends are enabled, the response includes `ollama` and `lm_studio` objects. `status` is `ok` if at least one local backend is reachable, otherwise `unavailable`. Each backend object requires `available`; `code`, `message`, and `retryable` are optional provider-health metadata.

Aggregate runtime hosts may include `model_residency` to report the runtime-owned model residency policy snapshot. `supported` indicates whether the runtime host can report model residency, `active_provider` and `active_model_id` identify the currently resident model when one exists, `in_flight_generations` counts active generations protected from idle unload, and `idle_unload_delay_seconds` reports the current idle-unload policy delay. `last_unload_failure`, when present, is a structured runtime-owned summary of the most recent failed unload attempt for a provider/model/reason. Known reasons are `model_switch`, `idle_timeout`, and runtime-host-owned `manual` unload. It must not contain raw provider error strings, backend URLs, route material, relay secrets, or endpoint paths. Clients must treat this as runtime status metadata; the residency policy remains enforced by the runtime host.

## `models.list`

Direction: Client -> Runtime.

```json
{
  "version": 1,
  "type": "models.list",
  "request_id": "req_models_001",
  "timestamp": "2026-06-23T09:01:00Z",
  "payload": {}
}
```

`models.list.payload` accepts only an empty object on client requests. Clients must not send response-only `models`, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, model commands, or direct-provider route material.

The AetherLink Runtime responds with the same `type` in v0.1:

```json
{
  "version": 1,
  "type": "models.list",
  "request_id": "req_models_001",
  "timestamp": "2026-06-23T09:01:01Z",
  "payload": {
    "models": [
      {
        "id": "llama3.1:8b",
        "name": "llama3.1:8b",
        "backend": "ollama",
        "provider": "ollama",
        "provider_model_id": "llama3.1:8b",
        "qualified_id": "ollama:llama3.1:8b",
        "model_kind": "chat",
        "capabilities": ["chat"],
        "size_bytes": 4660000000,
        "context_window_tokens": 32768,
        "modified_at": "2026-06-23T09:00:00Z",
        "installed": true,
        "running": true,
        "source": "local"
      },
      {
        "id": "google/gemma-4-26b-a4b",
        "name": "Gemma 4 26B A4B",
        "backend": "lm_studio",
        "provider": "lm_studio",
        "provider_model_id": "google/gemma-4-26b-a4b",
        "qualified_id": "lm_studio:google/gemma-4-26b-a4b",
        "model_kind": "chat",
        "capabilities": ["chat"],
        "size_bytes": 17990911801,
        "installed": true,
        "running": true,
        "source": "local"
      },
      {
        "id": "nomic-embed-text",
        "name": "nomic-embed-text",
        "backend": "ollama",
        "provider": "ollama",
        "provider_model_id": "nomic-embed-text",
        "qualified_id": "ollama:nomic-embed-text",
        "model_kind": "embedding",
        "capabilities": ["embedding"],
        "installed": true,
        "running": false,
        "source": "local"
      }
    ]
  }
}
```

Installed Ollama models are derived from the AetherLink Runtime calling Ollama `/api/tags` on the runtime host, with optional `/api/show` capability checks to classify chat vs embedding models. Installed LM Studio local models are derived from the AetherLink Runtime calling LM Studio native `GET /api/v1/models`, with fallback to OpenAI-compatible `GET /v1/models` if native response shape differs. Local models are the main path. The normal client chat picker should show installed runtime-host-local chat models only. Ollama cloud/source metadata may remain in protocol data for compatibility, but it is not a default, recommendation, or normal chat selection path. Running status may be derived from backend metadata when available. The runtime does not invent recommended/default model cards when backend model lists are empty.

The client app must not show embedding models in the chat model picker. Models with `model_kind = "embedding"` or `capabilities` containing `"embedding"` are selected only from the embedding-model setting for future retrieval/ranking/research features.

Model fields:

- `id`: backend model id retained for backwards compatibility.
- `name`: display name.
- `backend`: provider id, currently `ollama` or `lm_studio`.
- `provider`: same provider id as `backend`; added for clients that use provider terminology.
- `provider_model_id`: raw model id to send to the provider adapter after routing.
- `qualified_id`: provider-prefixed model id, such as `ollama:llama3.1:8b` or `lm_studio:google/gemma-4-26b-a4b`, recommended for `chat.send` when more than one provider is enabled.
- `model_kind`: `chat` for conversational/text-generation models, `embedding` for embedding models.
- `capabilities`: capability tags such as `chat` or `embedding`; clients should prefer these over name heuristics when present.
- `context_window_tokens`: optional runtime-host-derived model context window hint. When present, the runtime may use it to choose backend-side compaction budgets; clients should treat it as metadata and must not call provider APIs directly to derive or enforce it.
- `installed`: `true` only when the AetherLink Runtime sees the model in a local backend model list.
- `running`: `true` when the AetherLink Runtime detects the model as loaded or running.
- `source`: optional backend-derived source metadata. `local` means runtime-host-local. Other values are compatibility metadata and should not make a model appear as a normal chat-picker recommendation.
- `remote_model`: optional Ollama cloud model id from `/api/tags`.
- Backend host metadata from Ollama or LM Studio is runtime-internal and must not be sent to the client app in `models.result`.

The client app must not call `/api/tags`, `/api/ps`, `/api/pull`, `/api/chat`, LM Studio `/api/v1/*`, or LM Studio `/v1/*` URLs directly. It sends protocol messages only to the AetherLink Runtime.

## `models.pull`

Direction: Client -> Runtime, Runtime -> Client.

`models.pull` requests that the AetherLink Runtime pull a model through Ollama. The AetherLink Runtime converts the request to Ollama `/api/pull` on the runtime host. LM Studio downloads are not exposed as client-initiated pulls; users manage them on the runtime host through LM Studio or `lms`. Clients should refresh `models.list` after a successful pull and keep the normal chat picker focused on installed runtime-host-local chat models.

`models.pull.payload` accepts only `model` and optional legacy `backend`. `model` must be a non-blank string and legacy `backend`, when present, must be `ollama`. It must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, or direct-provider route material. Provider routing and credential configuration remain runtime-host concerns, not mobile-client payload metadata.

`models.pull` result payloads accept only `model`, compatibility `id`, `backend`, `provider`, `accepted`, `success`, `status`, `installed`, and `message`. `backend` and `provider` are provider identifiers, not provider URLs. Results must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, tool results, retrieval context, or direct-provider route material. Clients ignore stale `models.pull` result frames whose `request_id` does not match the active pull request.

Request:

```json
{
  "version": 1,
  "type": "models.pull",
  "request_id": "req_pull_001",
  "timestamp": "2026-06-23T09:01:30Z",
  "payload": {
    "model": "deepseek-v4-pro:cloud"
  }
}
```

Result:

```json
{
  "version": 1,
  "type": "models.pull",
  "request_id": "req_pull_001",
  "timestamp": "2026-06-23T09:02:30Z",
  "payload": {
    "model": "deepseek-v4-pro:cloud",
    "backend": "ollama",
    "provider": "ollama",
    "status": "success",
    "installed": true
  }
}
```

If pull fails, the AetherLink Runtime returns `error` with `backend_unavailable`, `model_not_found`, or another structured retryable/non-retryable error. The client app should refresh `models.list` after a successful pull and only send `chat.send` with models where `installed` is `true`.

## `chat.send`

Direction: Client -> Runtime.

```json
{
  "version": 1,
  "type": "chat.send",
  "request_id": "req_chat_001",
  "timestamp": "2026-06-23T09:02:00Z",
  "payload": {
    "session_id": "default",
    "model": "ollama:llama3.1:8b",
    "locale": "en",
    "messages": [
      {
        "role": "user",
        "content": "Hello",
        "attachments": []
      }
    ],
    "trusted_source_grant_ids": [
      "trusted_source_0123456789abcdef0123456789abcdef"
    ]
  }
}
```

The AetherLink Runtime routes provider-prefixed model ids to the selected runtime-host backend. Unprefixed model ids remain accepted for backwards compatibility, with Ollama treated as the default when the id is ambiguous. Ollama chat uses `/api/chat` with `stream = true`. LM Studio chat prefers native `/api/v1/chat` with `stream = true` and falls back to OpenAI-compatible `/v1/chat/completions` if native endpoint shape differs.

The AetherLink Runtime is the authoritative source for runtime-owned user memory. Current clients should not prepend cached memory as `chat.send` system context; they send client-visible conversation messages and manage memory through `memory.list`, `memory.upsert`, and `memory.delete`. If a compatibility client still sends a `system` message beginning with `Runtime user memory:`, the runtime removes that stale client context and replaces it with enabled entries from its own memory store before calling a backend. If no enabled runtime entries exist, no cached client memory is forwarded. This does not create a direct client-to-backend path; the entire message list still goes only to the AetherLink Runtime, and only the AetherLink Runtime calls Ollama or LM Studio.

`chat.send.locale` is optional and carries the client's normalized app-language preference for runtime-generated chat side effects, such as automatic chat titles triggered after the response. It does not change transport routing and must not expose backend or device locale details. Current client implementations normalize this to the launch language set: English, Korean, Japanese, Simplified Chinese, and French.

`chat.send.payload` accepts only `session_id`, `model`, `locale`, `messages`, and optional `trusted_source_grant_ids`; `session_id` and `model` must be non-blank strings, `locale` must be a string when present, and malformed allowed fields return `invalid_payload` instead of being coerced or treated as omitted. The grant array is authorization metadata only and must contain one through eight unique canonical ids. The payload must not carry raw source anchors, source text, source revision, approval state, project IDs, workspace IDs, retrieval context, permission grants, backend URLs, backend credentials, route material, or tool results.

The AetherLink Runtime is the authoritative processing boundary for chat. After a syntactically valid `chat.send` is parsed, the runtime host refuses to append to an existing archived session unless the client restores it first. Archived-session sends return `error` with `code = "chat_session_must_be_restored_before_send"` before backend dispatch or chat-event mutation. For active or new sessions, the runtime host stores request metadata and client-visible messages before model resolution, attachment capability checks, or generation starts, then stores streamed answer deltas, reasoning deltas, completion usage, cancellation, and errors as processing events. Runtime-only context, including the AetherLink capability guard, `Runtime user memory:` prompt context, and validated trusted-source reference blocks, is backend-call context only and must not be stored or returned as user-visible chat history. Inline attachment bytes are not kept in the event log. Client-side history can exist as UI cache, but it is not the only source of processing state. Authenticated clients can read runtime-owned summaries and transcripts through `chat.sessions.list` and `chat.messages.list`.

Runtime-side context compaction is backend-call context only. When the selected model reports a positive `context_window_tokens`, the runtime uses `conservative_utf8_bytes_vision_framing_v2` accounting: text and base64 payloads are bounded at one estimated token per UTF-8 byte, decoded image dimensions add a one-token-per-pixel upper bound, and message/attachment framing is included. The runtime reserves `max(512, min(4096, context_window_tokens / 8))` tokens for output. The remaining tokens are a hard estimator input budget: a request that already fits is forwarded unchanged, while an oversized request compacts a contiguous oldest prefix of whole user/assistant turns until the estimated request fits. All runtime-owned non-conversation system context is preserved, and the newest user turn plus every later conversation turn is kept verbatim. If the newest user message or mandatory runtime context cannot fit, compaction fails before backend dispatch with nonretryable `chat_context_window_exceeded`.

Adaptive compaction inserts a fixed runtime-owned `system` provenance message and an adjacent `assistant` historical summary explicitly labeled as untrusted conversation data. User-controlled historical text never becomes generated system instructions. After the deterministic fallback fits the hard budget, the runtime may ask the same selected runtime-host model for a bounded backend-only summary prepass. Reasoning is discarded, the derived generation is cancelled with the parent request, and blank, failed, oversized, or non-fitting output leaves the deterministic fallback unchanged. Only the connection that owns the active request id may cancel its primary or derived generation; the ownership check and cancellation claim occur atomically before any backend cancellation call. The active runtime context persists durable cancellation intent even when neither backend generation is registered during the prepass-to-primary handoff, preventing later primary dispatch. The primary backend stream registration is atomic with the final cancellation-state check, so a successful cancellation cannot race a new primary dispatch. The aggregate backend reserves the generation before async provider routing and rechecks cancellation while registering the selected provider stream. Primary and derived generation ids share one active reservation namespace, so a colliding active id is rejected before it can replace the original runtime context or reach backend chat.

The generated summary remains backend-only and outside the chat event log, transcript, and FTS index. After the primary request reaches a successfully stored `done`, the production runtime may retain the generated text in an owner-only SQLite sidecar. Exact reuse binds normalized owner, session, the bounded prepass source under `sha256-length-framed-chat-compaction-summary-source-v1`, its UTF-8 byte count, the full compacted-prefix lineage under `sha256-length-framed-chat-compaction-summary-lineage-v1`, the compacted turn count, the actually resolved provider-qualified model id, and `llm_prepass_with_incremental_lineage_v2`. On an exact miss, the cache may reuse only the newest smaller lineage whose digest exactly matches the corresponding prefix of the current storage-safe conversation. The runtime then presents the previous generated summary and only the newly compacted whole-turn delta as separately labeled untrusted input to the bounded same-model prepass. Edit, reorder, deletion, owner/session/model/policy mismatch, malformed lineage, or a non-strict extension fails closed to an independent full-source prepass. Cache lookup or commit failure also degrades to a fresh prepass without failing chat. Cancellation, primary error, or a non-fitting generated summary never commits a row, including after a successful incremental prepass. Session deletion purges the owner/session-derived rows before the authoritative lifecycle mutation; a purge failure blocks that mutation, while a later lifecycle failure may conservatively discard only the derived cache. The previous cache schema is derived data and is dropped rather than migrated if the required lineage columns are absent. New adaptive request events use `adaptive_backend_only_summary_v3`. Its separate request-bound source pointer includes `source_fingerprint_algorithm = sha256-length-framed-chat-compaction-source-v1`, a lowercase 64-hex `source_fingerprint`, and `source_canonical_byte_count`. The length-framed digest binds the pointer identity and turn ranges to the exact storage-safe compacted user/assistant prefix, including exact UTF-8 role/content and ordered attachment fields after inline attachment data has been removed for storage. Event validation recomputes the digest and byte count from the stored request before append and after reopen. This request-bound integrity binding is distinct from the reusable summary lineage; neither is a signature, external trust proof, tokenizer result, source excerpt, or replacement for the transcript. Existing `adaptive_backend_only_summary_v2` and `backend_only_summary_v1` records remain readable without fingerprint fields.

V3 request metadata labels `estimated_input_tokens_after` with `estimate_kind = planned_upper_bound` and, for newly written requests, `summary_policy = llm_prepass_with_incremental_lineage_v2`; `llm_prepass_with_deterministic_fallback_v1` remains readable for existing v3 records. The metadata describes the safe deterministic plan recorded before the optional prepass, not necessarily the request eventually dispatched. A terminal `done`, `cancelled`, or `error` event may carry `compaction_resolution`. When `primary_dispatched = true`, it records `summary_method = deterministic_preview_v1 | llm_summary_v1`, the same estimator id and input budget, and the effective conservative estimate of the exact primary request. When cancellation or failure prevents primary dispatch, `primary_dispatched = false` and method/estimate are omitted. SQLite and JSONL accept a resolution only after an adaptive v3 request with the same normalized owner, session id, and request id, and require its estimator id and input budget to match that request; append and reopen validation both enforce the binding. Missing resolution remains unknown and must not be inferred, preserving crash and legacy compatibility.

On a successfully dispatched `done`, a provider adapter that receives an actual nonnegative input-token count may place its source in a bounded generation-id-scoped one-shot registry without changing the established `ChatStreamEvent` cases or two-value `done` shape. `LlmBackend.takeProviderUsageSource(generationID:)` has a default nil implementation for existing conformers. Ollama and LM Studio native report terminal statistics directly. The LM Studio OpenAI-compatible path requests `stream_options.include_usage = true`, waits past the first `finish_reason`, and consumes the later usage-only chunk before completing. An aggregate backend transfers the one-shot source before forwarding `done`, and the runtime consumes it immediately. The runtime may then add `provider_usage_calibration` to the resolution. `count_source` is exactly `provider_usage_calibration_v1`; `resolved_provider_qualified_model_id` records the router-resolved dispatch identity; `provider`, canonical `provider_model_id`, and `wire_mode` must match that identity and bind the count to `ollama_chat`, `lmstudio_native`, or `lmstudio_openai_compat`; `input_tokens` must equal the terminal event usage; and `relation` is recomputed as `within_conservative_estimate`, `exceeded_conservative_estimate_within_budget`, or `exceeded_input_budget`. A resolved-model, provider/wire, canonical-model, count, placement, or relation mismatch corrupts the event. A mismatched one-shot source or `exceeded_input_budget` prevents a newly generated compaction summary from entering the reusable sidecar cache. Missing provider usage, cancellation, error, and legacy resolution records remain valid and do not synthesize a count. This is post-dispatch provider-reported calibration only: it does not alter the conservative pre-dispatch estimator, run a probe request, auto-tune policy, or prove provider-tokenizer parity. Runtime event stores must not persist prompt excerpts, backend-only deterministic/LLM summary text, lineage material, or a generated-summary hash in compaction metadata or resolution. The client-visible transcript, `chat.messages.list`, `chat.sessions.list`, archive state, and delete state are not rewritten; compaction metadata is not exposed through transcript reads or session search indexes, and terminal resolution follows the same boundary. Archived and deleted sessions are not compaction inputs.

If model metadata omits `context_window_tokens`, the runtime retains the compatibility behavior: it uses the legacy 24,000-character heuristic, keeps the newest 12 whole conversation turns, and may emit the existing `backend_only_summary_v1` structural source pointer. This fallback is not provider-tokenizer parity. On the adaptive path, the capability guard, runtime-owned memory prompt context, fixed provenance, and untrusted historical summary remain separate runtime-only contexts.

If the requested model is not installed on the AetherLink Runtime, the AetherLink Runtime returns `error` with `code = "model_not_installed"`. Clients should call `models.pull` through the AetherLink Runtime first.

Backend adapters that expose reasoning or think content preserve it as a separate protocol field or stream from the final assistant answer text. The AetherLink Runtime does not mix reasoning/think text into the assistant message body; the client app can then render it as a muted, compact/collapsed section that expands on demand. Ollama chat requests opt into this with the runtime-side `/api/chat` request field `"think": true` and map `message.thinking` to protocol reasoning deltas. LM Studio native and OpenAI-compatible streams map common local-model reasoning fields such as `reasoning_content`, `reasoning_delta`, `thinking_delta`, `reasoning`, `thinking`, and `thoughts` to protocol reasoning deltas. If a backend leaks inline `<think>...</think>` or `<thinking>...</thinking>` tags inside ordinary text deltas, the AetherLink Runtime splits those chunks before storage and before forwarding `chat.delta`, so the tagged content becomes `reasoning_delta` and the visible assistant `delta` stays clean. The client app still sends only `chat.send` to the AetherLink Runtime.

`chat.send.messages[]` may include `attachments` when the client has a real ingestion path. Message objects accept only `role`, `content`, and `attachments`; `role` must be one of `system`, `user`, or `assistant`. They must not carry source paths, workspace IDs, source-control state, backend URLs, backend credentials, route material, runtime memory context, tool results, or trusted-source metadata. Attachments are optional and default to an empty array. Clients must not expose file/image controls before the runtime can actually ingest and route the selected input.

Attachment objects accept only `type`, `mime_type`, `name`, `data_base64`, and `text`. `type` must be one of `image`, `document`, or `file`; `mime_type` must be a non-empty string; and optional `name`, `data_base64`, and `text` must be strings when present. Malformed allowed attachment fields return `invalid_payload` before backend dispatch instead of being silently dropped.

```json
{
  "role": "user",
  "content": "Describe this image.",
  "attachments": [
    {
      "type": "image",
      "mime_type": "image/png",
      "name": "diagram.png",
      "data_base64": "base64-image-bytes"
    }
  ]
}
```

For image attachments, the runtime forwards image bytes only to models whose capabilities include `vision`, `image`, or `multimodal`. Ollama-compatible vision models receive images through the runtime-owned backend adapter rather than through a direct client-to-backend connection. LM Studio vision models use the runtime-owned native `/api/v1/chat` image input shape first, with OpenAI-compatible chat completions as a fallback when the native endpoint rejects the request shape. Backends that do not yet have a verified multimodal request shape must reject image attachments with a structured `unsupported_attachment` error instead of dropping or mis-shaping image data.

For document attachments, the runtime must parse files before model use. PDF, DOCX/DOCM/DOTX, DOC, HWPX, HWP, ODT/ODS/ODP, XLSX/XLSM, XLS, PPTX/PPTM/PPSX, PPT/PPS, EPUB, RTF, WebArchive, HTML/XHTML, Markdown, AsciiDoc, reStructuredText, plain text/log-style text, CSV/TSV, JSON/JSONL, YAML, TOML, INI/properties, and XML inputs should become extracted text plus metadata or chunks owned by the runtime. Pages/Numbers/Keynote archives are best-effort when text-bearing XML/HTML entries are available. Legacy binary HWP/XLS/PPT files are best-effort until dedicated parsers are added. A document attachment can carry extracted text when parsing already happened on the runtime side:

```json
{
  "role": "user",
  "content": "Summarize the attached document.",
  "attachments": [
    {
      "type": "document",
      "mime_type": "application/pdf",
      "name": "brief.pdf",
      "text": "extracted document text or a runtime chunk reference"
    }
  ]
}
```

## `chat.delta`

Direction: Runtime -> Client.

```json
{
  "version": 1,
  "type": "chat.delta",
  "request_id": "req_chat_001",
  "timestamp": "2026-06-23T09:02:01Z",
  "payload": {
    "delta": "partial response"
  }
}
```

The AetherLink Runtime should send assistant text as `delta`. Client apps also accept `text` as a compatibility alias for early v0.1 clients and external mock transports, but runtime adapters should normalize backend output to `delta` before sending it.

When a backend streams reasoning or thinking text, the AetherLink Runtime sends it on the same `chat.delta` type with `reasoning_delta` instead of `delta`:

```json
{
  "version": 1,
  "type": "chat.delta",
  "request_id": "req_chat_001",
  "timestamp": "2026-06-23T09:02:01Z",
  "payload": {
    "reasoning_delta": "intermediate reasoning"
  }
}
```

The AetherLink Runtime should send reasoning text as `reasoning_delta`. Client apps also accept `thinking_delta` as a compatibility alias, but runtime adapters should normalize Ollama/LM Studio/OpenAI-compatible thinking fields to `reasoning_delta` before sending them. The client app appends reasoning deltas to the active message's reasoning section, separate from the final assistant content.

`chat.delta.payload` accepts only `delta`, `text`, `reasoning_delta`, and `thinking_delta`. Runtime streaming deltas must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, tool results, retrieval context, or direct-provider route material.

## `chat.done`

Direction: Runtime -> Client.

```json
{
  "version": 1,
  "type": "chat.done",
  "request_id": "req_chat_001",
  "timestamp": "2026-06-23T09:02:05Z",
  "payload": {
    "finish_reason": "stop",
    "assistant_message_id": "assistant_message_0123456789abcdef0123456789abcdef",
    "source_attributions": [
      {
        "source_index": 1,
        "document_name": "guide.md",
        "mime_type": "text/markdown",
        "chunk_index": 0
      }
    ],
    "usage": {
      "input_tokens": 12,
      "output_tokens": 48
    }
  }
}
```

If a request is cancelled, `finish_reason` may be `cancelled`. `source_attributions` is allowed only with `finish_reason = "stop"`, only when at least one reviewed source was actually consumed for that request, and only for clients advertising `chat.source_attributions.v1`. It contains one through eight entries in the original consumed-source order. `source_index` is contiguous from one, `document_name` is non-empty and capped at 256 characters, `mime_type` is a canonical lowercase type/subtype token capped at 128 characters, and `chunk_index` is nonnegative. `assistant_message_id` is allowed only beside a non-empty attribution array for clients advertising `chat.source_attribution.resolve.v1`; it remains a locator rather than source authority.

`chat.done.payload` accepts only `finish_reason`, `usage`, optional `source_attributions`, and the capability-gated optional `assistant_message_id`; nested `usage` accepts only `input_tokens` and `output_tokens`, and each attribution accepts only `source_index`, `document_name`, `mime_type`, and `chunk_index`. The array is runtime-generated historical provenance that proves those reviewed excerpts were provided to the answer-generation context. It does not claim that the model used a source for a particular sentence and does not represent current access permission. Later revoke or revision change blocks future consumption but does not rewrite an already completed answer's provenance. Grant, citation, source-anchor, document, fingerprint, revision, approval, source text, snippet, offset, path, workspace, project, backend, route, credential, and tool metadata are forbidden.

## `chat.sessions.list`

Direction: Client -> Runtime, Runtime -> Client.

This reads runtime-host-owned session summaries. It is not a model backend request, and the client must be authenticated before it can list sessions.

An initial `chat.sessions.list.payload` accepts only `limit`, `include_archived`, `query`, and `embedding_model_id`. A continuation payload accepts only `cursor`; it must not combine the opaque cursor with any initial-request field. `limit` must be an integer, `include_archived` must be a boolean, and `query`, `embedding_model_id`, plus `cursor` must be strings when present. Cursors are nonblank and bounded to 512 UTF-8 bytes. Malformed allowed fields return `invalid_payload` instead of being coerced or ignored. Neither request shape may carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-store metadata. Session listing is a runtime-owned chat store query; backend/provider routing, source indexing, workspace context, and permission grants remain outside this active payload.

Request:

```json
{
  "version": 1,
  "type": "chat.sessions.list",
  "request_id": "req_sessions_001",
  "timestamp": "2026-06-23T09:02:06Z",
  "payload": {
    "limit": 100,
    "include_archived": true,
    "query": "relay route",
    "embedding_model_id": "ollama:nomic-embed-text"
  }
}
```

Response:

```json
{
  "version": 1,
  "type": "chat.sessions.list",
  "request_id": "req_sessions_001",
  "timestamp": "2026-06-23T09:02:06Z",
  "payload": {
    "snapshot_count": 2,
    "sessions": [
      {
        "session_id": "default",
        "title": "Runtime-Mediated Model Access",
        "model": "ollama:llama3.1:8b",
        "last_activity_at": "2026-06-23T09:02:05Z",
        "message_count": 2,
        "status": "active",
        "last_event": "done",
        "last_finish_reason": "stop",
        "search": {
          "rank": 1,
          "snippet": "Runtime-mediated model access without a direct client backend.",
          "matched_fields": ["title", "transcript"]
        }
      },
      {
        "session_id": "archived-1",
        "title": "Archived Runtime Notes",
        "model": "ollama:llama3.1:8b",
        "last_activity_at": "2026-06-23T08:58:05Z",
        "message_count": 4,
        "status": "archived",
        "archived_at": "2026-06-23T09:10:05Z",
        "last_event": "error",
        "last_error_code": "model_not_installed"
      }
    ]
  }
}
```

Clients advertising `chat.sessions.authoritative_sync.v1` receive `snapshot_count` on every accepted page and an opaque `next_cursor` when another page exists. A continuation sends only that cursor with a fresh request id:

```json
{
  "version": 1,
  "type": "chat.sessions.list",
  "request_id": "req_sessions_002",
  "timestamp": "2026-06-23T09:02:07Z",
  "payload": {
    "cursor": "v1.6d203dd2-6998-4263-bf20-05fdde0f7646.100.1782191047.17e44c47d4d82037df39c693da90e8e270a988dc51637351376fd4d8e7333a80"
  }
}
```

The runtime materializes the complete deterministic ranking once, assigns absolute search ranks before slicing, and binds the fixed-field HMAC-SHA-256 cursor to the authenticated connection, normalized owner, search mode and filters, embedding-model hint, page limit, snapshot count, snapshot id, offset, and expiry. A process restart, connection or authentication change, lifecycle mutation, expiration, eviction, noncanonical token, or authentication-code mismatch invalidates continuation instead of silently restarting from page one. Snapshots expire after 120 monotonic seconds while retaining the signed wall-clock expiry, contain at most 10,000 rows, and are limited to one per connection and eight globally. Reauthentication invalidates the current snapshot and any in-flight initial publication; a per-connection initial generation prevents an older slow request from evicting a newer snapshot. A trusted authentication response is accepted only if the exact challenge identity, device, nonce, transport binding, and advertised capabilities still match after the awaited trusted-device lookup. The client must reject duplicate session ids, cursor loops, count drift, a terminal accumulated count different from `snapshot_count`, and a `sessions`-only response after authoritative support was established; it must not publish or persist a partial full-history or search snapshot. After such a downgrade, bulk authority remains disabled until a fresh unqueried capable snapshot completes. Clients issue session-list and transcript reads in dedicated request-id namespaces. A current matching history request takes precedence over an older closed correlation; otherwise an error in either history namespace is discarded before payload validation even after bounded closed-correlation diagnostics evict the original record. Current history errors still apply normal authentication-loss handling. Clients that do not advertise the capability continue receiving the legacy `sessions`-only response.

`include_archived` defaults to `false`. When it is `false`, archived sessions are omitted. When it is `true`, the runtime may return active and archived sessions with `status`; deleted sessions are never returned. Archived summaries include `archived_at` when known. `last_activity_at` remains the last chat activity timestamp, not necessarily the archive timestamp.

`query` is optional. When present, the runtime filters within the authenticated device's owner scope after applying the normal active/archived/deleted lifecycle rules. `embedding_model_id` is optional and should be sent only with a real search query when the client has a selected runtime-host-local embedding model. When present, the runtime resolves that provider-qualified installed local embedding model, batch-embeds the query plus bounded owner-scoped candidate documents, and ranks candidates by cosine similarity. This remains a runtime-host operation, not a `chat.send` model override and not a direct client-to-provider request. The runtime ignores `embedding_model_id` when there is no real nonblank `query`, must not silently fall back to lexical search after an embedding failure, and must not echo the model id or vectors in response payloads. Query responses may include per-session `search` metadata with a 1-based `rank`, a bounded `snippet`, and stable `matched_fields` names such as `title`, `model`, `transcript`, `reasoning`, `attachment`, or `semantic`. Semantic search is bounded to the latest 200 lifecycle-eligible sessions, 100 stored messages per candidate, a selected-model-context-derived candidate ceiling capped at 8,192 UTF-8 bytes with a 1,024-byte fallback when metadata is absent, 256 query characters, and 16 distinct query terms. The runtime reads each owner's candidate sessions/messages from one store snapshot, gives newer messages priority within the byte budget, accepts one semantic search per connection and at most four globally, and cancels tracked inference when the connection closes. Runtime-only system context, compaction metadata, and inline attachment bytes are excluded from semantic documents. Without `embedding_model_id`, the SQLite/FTS default event-store backend continues using its deterministic lexical candidate/rank/snippet path. With a canonical lowercase Ollama artifact digest, candidate vectors persist under owner/session/canonical-model/model-fingerprint/document-fingerprint keys and can be reused after reopen; query vectors never persist. The source event sequence is revalidated in the write transaction, append/lifecycle changes invalidate rows, and cancellation is checked before commit. Providers without a strong immutable revision, including the current documented LM Studio model-list shape, continue on-demand semantic search without persistent writes. Android treats queried responses as transient search results; only unqueried list responses replace the complete locally cached runtime summary list.

`limit` is optional. The runtime clamps it to an implementation-defined maximum. A legacy one-page request may use `0` for an empty result window; a client advertising `chat.sessions.authoritative_sync.v1` must use a capable initial page size from 1 through 200 because a zero-sized page cannot advance an authoritative snapshot. `title` is runtime-owned metadata when a `chat.title.request` result has been generated and saved by the runtime; otherwise it should remain a neutral placeholder such as `New chat` instead of exposing the first user prompt verbatim.

Runtime summaries may include processing metadata: `last_event`, `last_finish_reason`, and `last_error_code`. `last_event` describes the latest runtime-side processing event for that session, such as `done`, `cancelled`, or `error`. These fields let a client show runtime-owned processing state without making the client the durable transcript store.

## `chat.messages.list`

Direction: Client -> Runtime, Runtime -> Client.

This reads a runtime-host-owned transcript for one session. Stored assistant reasoning is returned separately from assistant answer text so clients can render it in a muted/collapsible reasoning section.

`chat.messages.list.payload` accepts only `session_id` and `limit`. `session_id` must be a non-blank string, and `limit` must be an integer when present; malformed allowed fields return `invalid_payload` instead of being coerced or ignored. It must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-store metadata. Transcript listing is a runtime-owned chat store query for one session; backend/provider routing, source indexing, workspace context, and permission grants remain outside this active payload.

Request:

```json
{
  "version": 1,
  "type": "chat.messages.list",
  "request_id": "req_messages_001",
  "timestamp": "2026-06-23T09:02:07Z",
  "payload": {
    "session_id": "default",
    "limit": 200
  }
}
```

Response:

```json
{
  "version": 1,
  "type": "chat.messages.list",
  "request_id": "req_messages_001",
  "timestamp": "2026-06-23T09:02:07Z",
  "payload": {
    "session_id": "default",
    "messages": [
      {
        "role": "user",
        "content": "Explain this architecture.",
        "attachments": [
          {
            "type": "document",
            "mime_type": "text/plain",
            "name": "notes.txt",
            "text": "Extracted document text retained by the runtime."
          }
        ],
        "created_at": "2026-06-23T09:02:00Z"
      },
      {
        "role": "assistant",
        "content": "The runtime mediates local model access...",
        "reasoning": "Checking the runtime boundary.",
        "assistant_message_id": "assistant_message_0123456789abcdef0123456789abcdef",
        "source_attributions": [
          {
            "source_index": 1,
            "document_name": "guide.md",
            "mime_type": "text/markdown",
            "chunk_index": 0
          }
        ],
        "created_at": "2026-06-23T09:02:05Z"
      }
    ]
  }
}
```

`limit` is optional. The runtime clamps it to an implementation-defined maximum, and `0` returns an empty result window. The runtime must omit inline attachment bytes from stored transcripts. Stored message attachments may include safe metadata such as `type`, `mime_type`, `name`, and extracted `text`, but must not include `data_base64`. For clients advertising `chat.source_attributions.v1`, completed assistant messages may include the exact safe attribution projection stored on their successful terminal event; user, cancelled, error, and incomplete messages omit it. For clients also advertising `chat.source_attribution.resolve.v1`, only those attribution-bearing assistant rows include their server-generated `assistant_message_id`. The current runtime store reconstructs multi-turn transcripts from stored request/response event pairs, rewinds an older assistant answer when a regenerate request supplies the preceding transcript prefix, and returns attachment metadata for user messages when available. Archive/delete semantics are runtime-owned; clients may keep local suppression metadata so a locally deleted runtime-owned session does not reappear after the next history sync.

## `chat.title.request`

Direction: Client -> Runtime.

After the first assistant response completes, the client app may ask the AetherLink Runtime to generate a concise chat title for local conversation lists. This request is a runtime-mediated model call through the selected backend adapter. The client app must not call Ollama, LM Studio, or another serving backend directly for title generation.

```json
{
  "version": 1,
  "type": "chat.title.request",
  "request_id": "req_title_001",
  "timestamp": "2026-06-23T09:02:08Z",
  "payload": {
    "session_id": "default",
    "model": "ollama:llama3.1:8b",
    "locale": "en",
    "messages": [
      {
        "role": "user",
        "content": "Explain this architecture."
      },
      {
        "role": "assistant",
        "content": "The runtime mediates local model access..."
      }
    ]
  }
}
```

The AetherLink Runtime should use recent `messages`, the selected `model`, and the optional `locale` to generate one short title. The runtime should return a single non-streaming result; it should not emit `chat.delta` or normal assistant output for title requests. The request is valid only for an existing active session whose current title is the neutral placeholder. A missing session returns `chat_session_not_found`; an archived, deleted, or already titled session returns an empty result without backend title generation.

`chat.title.request.payload` accepts only `session_id`, `model`, `locale`, and `messages`; `session_id` and `model` must be non-blank strings, `locale` must be a string when present, and malformed allowed fields return `invalid_payload` instead of being coerced or treated as omitted. Clients must not send response-only `title`, project IDs, workspace IDs, retrieval context, permission grants, backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, source paths, source-control state, tool results, or direct-provider route material in this payload.

## `chat.title.result`

Direction: Runtime -> Client.

```json
{
  "version": 1,
  "type": "chat.title.result",
  "request_id": "req_title_001",
  "timestamp": "2026-06-23T09:02:09Z",
  "payload": {
    "title": "Runtime-Mediated Model Access"
  }
}
```

The client app may use `title` as local UI metadata for the chat only if the user has not manually renamed that chat. Empty or invalid backend output is represented as an empty title string rather than streamed assistant text. Before dispatch, the runtime captures the active placeholder title and its monotonic title revision. Before committing a nonempty explicit or automatic generated title, it revalidates the exact authenticated owner, active lifecycle, placeholder title, and captured revision; a concurrent rename or title event suppresses the stale commit. The common JSONL/SQLite append boundary accepts only exact NFC-normalized, trimmed, control-free titles of at most 256 Unicode scalars. Replay preserves append/revision authority even when wall-clock timestamps are equal or move backward; new mutations use a canonical timestamp at least one second after the prior title update. Existing pre-hardening non-NFC, control-bearing, or oversized title rows are projected deterministically to a bounded canonical display title rather than making the complete event store unreadable, while new writes remain strict. A successful commit invalidates both chat-session and research-notebook snapshots for that owner. The explicit result is published under the same lifecycle authorization lock as its commit, so reauthentication cannot expose a committed title through the superseded request authority.

The `chat.title.result.payload` object is closed. The chat.title.result.payload accepts only `title`. Runtime title results must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, tool results, retrieval context, or direct-provider route material.

## `chat.session.rename`

Direction: Client -> Runtime, Runtime -> Client.

This records a user-provided title for a runtime-owned chat session on the runtime host. Client apps may update their local UI cache optimistically, but the runtime remains the source of truth for the title returned by `chat.sessions.list`. If the session backs a research notebook, the same title is also the authoritative title projected by `research.notebooks.list`; clients reuse this command rather than sending a notebook-specific title mutation. A successful rename increments the stored title revision, invalidates both chat-session and research-notebook authoritative snapshots for the authenticated owner, and publishes its acknowledgement under the same lifecycle authorization lock as the commit so a continuation or superseded connection authority cannot publish the prior title.

`chat.session.rename` request payloads accept only `session_id` and `title`. `session_id` must be a non-blank string. `title` must be a string, is NFC-normalized and trimmed by the runtime, must remain nonempty, must contain no control characters, and is bounded to 256 Unicode scalars. Malformed allowed fields return `invalid_payload` instead of being coerced or treated as omitted. Clients must not supply `renamed_at`; it is runtime-generated acknowledgement metadata. Rename requests also must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-store metadata.

Request:

```json
{
  "version": 1,
  "type": "chat.session.rename",
  "request_id": "req_rename_001",
  "timestamp": "2026-06-23T09:02:00Z",
  "payload": {
    "session_id": "default",
    "title": "Runtime route notes"
  }
}
```

Acknowledgement:

```json
{
  "version": 1,
  "type": "chat.session.rename",
  "request_id": "req_rename_001",
  "timestamp": "2026-06-23T09:02:00Z",
  "payload": {
    "session_id": "default",
    "title": "Runtime route notes",
    "renamed_at": "2026-06-23T09:02:00Z"
  }
}
```

`chat.session.rename` acknowledgement payloads accept only `session_id`, `title`, and `renamed_at`. Runtime rename acknowledgements must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, tool results, retrieval context, or direct-store metadata.

If the session is missing, deleted, or not visible to the authenticated device, the runtime returns `error` with `code: "chat_session_not_found"`.

## `chat.session.archive`

Direction: Client -> Runtime, Runtime -> Client.

This archives a runtime-owned chat session on the runtime host. Archived sessions are omitted from the default `chat.sessions.list` response, but can be returned to authenticated clients that request `include_archived: true`. They should not be used as active memory/research context unless explicitly restored by the user.

Single-session `chat.session.archive`, `chat.session.restore`, and `chat.session.delete` request payloads accept only `session_id`. `session_id` must be a non-blank string; malformed allowed fields return `invalid_payload` instead of being coerced or treated as omitted. A client that has advertised `chat.sessions.authoritative_sync.v1` and received an authoritative list response may instead send the bounded bulk archive shape `{ "scope": "all_active", "limit": 200 }` or bulk delete shape `{ "scope": "all_archived", "limit": 200 }`. `limit` is optional and bounded to `1...200`; bulk restore is not defined. The runtime derives the target set from the authenticated owner scope and never accepts client session ids as the definition of “all.” Before either single-session or bulk mutation commits, the runtime revalidates request-task cancellation, exact owner scope, authentication generation, authenticated session, and, for bulk, authoritative-sync capability under the lifecycle lock; reauthentication, connection closure, owner change, or capability downgrade fails closed. Connection closure cancels tracked request tasks instead of retaining permanent per-connection tombstones. No lifecycle payload may carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-store metadata. Session lifecycle commands mutate runtime-owned chat store state; backend/provider routing, source indexing, workspace context, and permission grants remain outside these active payloads.

Request:

```json
{
  "version": 1,
  "type": "chat.session.archive",
  "request_id": "req_archive_001",
  "timestamp": "2026-06-23T09:03:00Z",
  "payload": {
    "session_id": "default"
  }
}
```

Runtime-authoritative bulk archive request and acknowledgement:

```json
{
  "version": 1,
  "type": "chat.session.archive",
  "request_id": "req_archive_all_001",
  "timestamp": "2026-06-23T09:03:01Z",
  "payload": {
    "scope": "all_active",
    "limit": 200
  }
}
```

```json
{
  "version": 1,
  "type": "chat.session.archive",
  "request_id": "req_archive_all_001",
  "timestamp": "2026-06-23T09:03:01Z",
  "payload": {
    "scope": "all_active",
    "status": "archived",
    "affected_count": 200,
    "remaining_count": 12,
    "completed_at": "2026-06-23T09:03:01Z"
  }
}
```

Each bulk request selects one deterministic owner-scoped batch and commits that batch atomically. When `remaining_count` is positive, the client may send a new request id for the next batch. The client must not optimistically mutate runtime-owned rows, automatically retry a request whose delivery is ambiguous, or treat a partial response as success. A lost, malformed, stale, or failed acknowledgement requires a fresh authoritative list reconciliation. A terminal acknowledgement may update local-only presentation and must then be followed by a complete unqueried paginated refresh.

Acknowledgement:

```json
{
  "version": 1,
  "type": "chat.session.archive",
  "request_id": "req_archive_001",
  "timestamp": "2026-06-23T09:03:00Z",
  "payload": {
    "session_id": "default",
    "status": "archived",
    "archived_at": "2026-06-23T09:03:00Z"
  }
}
```

## `chat.session.restore`

Direction: Client -> Runtime, Runtime -> Client.

This restores an archived runtime-owned chat session so it can appear in default session history again.

Request payload:

```json
{
  "session_id": "default"
}
```

Acknowledgement payload:

```json
{
  "session_id": "default",
  "status": "restored",
  "restored_at": "2026-06-23T09:04:00Z"
}
```

Single-session `chat.session.archive`, `chat.session.restore`, and `chat.session.delete` acknowledgement payloads accept only `session_id`, `status`, `archived_at`, `restored_at`, and `deleted_at`. Bulk archive/delete acknowledgements accept only `scope`, `status`, `affected_count`, `remaining_count`, and `completed_at`; `all_active` binds to `archived`, and `all_archived` binds to `deleted`. Runtime lifecycle acknowledgements must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, tool results, retrieval context, or direct-store metadata.

## `chat.session.delete`

Direction: Client -> Runtime, Runtime -> Client.

This records a runtime-side deletion/tombstone for a chat session. The runtime must only accept deletion for an already archived session; active sessions must return `error` with `code: "chat_session_must_be_archived_before_delete"`. This keeps archive and permanent delete as distinct operations even if a future client bypasses UI confirmation. After deletion, the runtime must stop returning the deleted session from `chat.sessions.list` and should return no transcript for `chat.messages.list`. Implementations may keep append-only audit events internally, but deleted sessions must not be used for memory, retrieval, or compaction inputs.

Request payload:

```json
{
  "session_id": "default"
}
```

Acknowledgement payload:

```json
{
  "session_id": "default",
  "status": "deleted",
  "deleted_at": "2026-06-23T09:05:00Z"
}
```

The bulk delete request uses `{ "scope": "all_archived", "limit": 200 }` and returns `status: "deleted"` with nonnegative `affected_count`, nonnegative `remaining_count`, and RFC 3339 `completed_at`. The same bounded batching, no-optimistic-mutation, no-automatic-retry, and mandatory reconciliation rules apply.

## `chat.cancel`

Direction: Client -> Runtime, Runtime -> Client.

For requests, `chat.cancel.payload` accepts only `target_request_id`. Acknowledgement payloads accept only `target_request_id` and `cancelled`. `target_request_id` must be a non-blank string; malformed or blank allowed fields return `invalid_payload` before backend cancel dispatch, and acknowledgement payloads echo the same non-blank target request id. `chat.cancel` payloads must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, workspace IDs, permission grants, source-control state, or direct-provider cancel metadata. Cancellation targets runtime-owned in-flight request ids; provider-specific cancellation and routing remain runtime-host concerns.

Request:

```json
{
  "version": 1,
  "type": "chat.cancel",
  "request_id": "req_cancel_001",
  "timestamp": "2026-06-23T09:02:02Z",
  "payload": {
    "target_request_id": "req_chat_001"
  }
}
```

Acknowledgement:

```json
{
  "version": 1,
  "type": "chat.cancel",
  "request_id": "req_cancel_001",
  "timestamp": "2026-06-23T09:02:03Z",
  "payload": {
    "target_request_id": "req_chat_001",
    "cancelled": true
  }
}
```

If the target generation is unknown, the AetherLink Runtime returns `error` with `code = "generation_not_found"`.

When cancellation succeeds, the runtime also closes the target `chat.send` stream by sending `chat.done` with the target request id and `finish_reason = "cancelled"`. Clients may optimistically clear local streaming UI from the `chat.cancel` acknowledgement, but the target stream lifecycle is not complete until the matching `chat.done` is observed.

## `error`

Direction: either side -> other side.

```json
{
  "version": 1,
  "type": "error",
  "request_id": "req_models_001",
  "timestamp": "2026-06-23T09:03:00Z",
  "payload": {
    "code": "backend_unavailable",
    "message": "Ollama is not running.",
    "retryable": true
  }
}
```

`error` result/response payloads accept only `code`, `message`, and `retryable`. `code` must be one of the canonical error codes below, `message` must be a string when present, and `retryable` must be a boolean when present. Error payloads must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source approval handles, citations, trusted-source review data, audit handles, direct-store metadata, or direct-provider route material. Android clients reject unsupported error metadata before pending request cleanup, active stream termination, route/auth state mutation, or device storage mutation; canonical errors on the same request id still drive the existing failure/retry behavior.

Common v0.1 error codes:

- `unknown_message_type`
- `unexpected_message_direction`
- `invalid_payload`
- `not_connected`
- `pairing_required`
- `authentication_required`
- `authentication_failed`
- `backend_unavailable`
- `bad_backend_response`
- `no_models`
- `model_not_found`
- `model_not_installed`
- `generation_not_found`
- `generation_cancelled`
- `route_refresh_unavailable`
- `unsupported_operation`
- `unsupported_attachment`
- `unreadable_attachment`
- `chat_session_not_found`
- `chat_session_must_be_archived_before_delete`
- `chat_session_must_be_restored_before_send`
- `chat_store_unavailable`
- `chat_context_window_exceeded`
- `document_index_unavailable`
- `source_anchor_not_found`
- `memory_store_unavailable`
- `memory_summary_draft_unavailable`
- `memory_summary_draft_stale`
- `transport_error`
- `internal_error`

## Runtime Memory Messages

Basic runtime-owned memory CRUD is active after authentication. These messages store short user-managed notes on the AetherLink Runtime host so future clients can sync the same trusted-runtime memory state. `memory.list` supports deterministic lexical filtering and an optional runtime-host semantic ranking hint for approved entries; it does not implement automatic unreviewed extraction, reflection, MCP, tools, or web search. The current `chat.send` compaction slice is separate: it is a runtime-side, backend-only active-session prompt-shaping path, not memory CRUD or durable memory extraction.

Current clients do not include cached memory context inside `chat.send.messages`. Compatibility clients may still send stale memory context, but the runtime treats it as defensive compatibility input, strips it, and rebuilds memory prompt context from the runtime-owned memory store. Archived or deleted chat sessions must not be used as memory inputs unless restored or explicitly selected by a future permissioned workflow.

Long-inactivity memory summary drafts are review artifacts. `memory.summary.drafts.list` identifies active, owner-scoped, sufficiently old chats and returns bounded visible-transcript source pointers plus either a deterministic preview or a previously cached generated summary. Listing itself does not call a model, write memory, inject memory into `chat.send`, or include assistant reasoning, runtime-only system context, archived/deleted sessions, or another trusted device's sessions. `memory.summary.draft.generate` is an explicit review action: the runtime revalidates the owner-scoped current draft and exact stale guards, resolves an installed runtime-host local chat model, sends only bounded visible user/final-assistant excerpts to that model, requires strict bounded JSON output, and caches the generated review draft on the runtime host. It never auto-approves memory. Repeated generation or reopening returns the owner-scoped cache without another model call. A source change after inference returns `memory_summary_draft_stale` and persists nothing; malformed, oversized, or backend-failed output returns `memory_summary_draft_generation_failed` and leaves the deterministic preview unchanged. `memory.summary.draft.approve` is the separate write command: the runtime recomputes the owner-scoped draft, overlays any matching generated cache, validates optional expected metadata, and writes an idempotent runtime memory entry with id `memory-summary:<draft_id>`. Approved summary entries carry durable `source` metadata that records `deterministic_preview` or `llm_summary_v1`, source session metadata, source range, and bounded visible-transcript source pointers. `memory.summary.draft.dismiss` persists an owner-scoped decision without creating or updating memory. Approved or dismissed drafts are hidden from later draft-list responses for that owner.

Memory entries may include a `source` object. Current runtimes only emit it for approved long-inactivity summary drafts, and clients must treat it as audit metadata for the approved entry, not as additional chat context. Clients must not send `source` in `memory.upsert`; runtimes reject client-supplied source metadata as `invalid_payload` and preserve any existing runtime-derived source metadata during later content/enabled edits. Clients should show source metadata as a review aid only, keep source excerpts collapsed by default, and avoid presenting the field as a full transcript. Source excerpts are bounded visible transcript excerpts; runtimes must not persist assistant reasoning, runtime-only system prompts, runtime memory context, compaction summaries, archived/deleted sessions, or another trusted device's transcript in this field.

### `memory.list`

Request:

```json
{
  "version": 1,
  "type": "memory.list",
  "request_id": "req_memory_list_001",
  "timestamp": "2026-06-25T05:25:00Z",
  "payload": {
    "query": "concise answers",
    "embedding_model_id": "ollama:nomic-embed-text"
  }
}
```

`query` is optional. Blank or omitted queries return the normal owner-scoped memory list without `search` metadata. Without `embedding_model_id`, nonblank queries use deterministic lexical filtering over memory content and bounded runtime-derived source audit metadata. With a provider-qualified installed runtime-host-local embedding model, the runtime semantically ranks only persisted `RuntimeMemoryEntry` values and embeds only their approved `content`; generated review drafts, dismissed drafts, source titles, source excerpts, model ids, audit pointers, and query vectors are not persisted as candidate documents. There is no separate `memory.search` command.

`memory.list.payload` accepts only optional `query` and optional `embedding_model_id`. Both must be strings when present; malformed allowed fields return `invalid_payload` instead of being coerced or treated as omitted. Nonblank queries are bounded to 256 characters and 16 distinct normalized terms, must fit the selected model's conservative input budget, and consider at most the latest 200 approved entries. Overlong, excessive-term, or model-budget-exceeding queries return `invalid_payload`. An embedding hint without a real query is ignored. Clients must not supply `entries`; it is response-only memory list data. List requests also must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-store metadata.

Semantic candidate vectors persist in an owner-only SQLite sidecar under owner, memory id, canonical provider-qualified model, strong model fingerprint, exact content-document fingerprint, and current approved-entry source revision. Only canonical lowercase Ollama SHA-256 artifact revisions enable persistence; providers without a strong immutable revision recompute candidates on demand. Memory edits, enabled-state changes, source-audit changes, and deletion rotate the source revision and synchronously purge derived vectors before the mutation is committed. The store revalidates current source revisions after inference and again while committing cache rows, and cancellation is checked after cache-lock acquisition and before commit. Cache read/write failures degrade semantic search to on-demand inference, but a purge failure blocks the privacy-sensitive mutation rather than leaving derived data silently behind.

Android sends the selected embedding model only for a real memory query, treats queried responses as transient search results, and accepts only the exact pending request id. Only an unqueried refresh replaces the complete locally persisted memory cache. When an older strict runtime rejects only the unknown `embedding_model_id` field, Android retries that query once without the hint for lexical compatibility.

Response:

```json
{
  "version": 1,
  "type": "memory.list",
  "request_id": "req_memory_list_001",
  "timestamp": "2026-06-25T05:25:01Z",
  "payload": {
    "entries": [
      {
        "id": "memory-1",
        "content": "Prefers concise answers.",
        "enabled": true,
        "created_at": "2026-06-25T05:20:00Z",
        "updated_at": "2026-06-25T05:20:00Z",
        "search": {
          "rank": 1,
          "snippet": "Prefers concise answers.",
          "matched_fields": ["content"]
        }
      }
    ]
  }
}
```

When `query` is nonblank, returned entries include `search.rank`, a bounded `search.snippet`, and `search.matched_fields`. Search metadata is response-only and must not be persisted by clients as memory content. Semantic results use the existing `content` matched-field shape and do not expose model, vector, cache, or source-revision metadata. Lexical matches may still include `source_title`, `source_range`, or `source_excerpt` when the query matches source audit metadata.

### `memory.duplicate_suggestions.list`

Returns bounded, review-only suggestions for runtime-owned memory entries whose stored `content` is byte-for-byte identical. The command is authenticated, owner-scoped, and available only to a connection that advertised `memory.duplicate_suggestions.v1` in `hello.client_capabilities`. It is not semantic clustering, does not call an embedding or chat model, and never merges, edits, enables, disables, or deletes memory.

The request payload is empty. Unknown request fields return `invalid_payload` before memory-store access.

```json
{
  "version": 1,
  "type": "memory.duplicate_suggestions.list",
  "request_id": "req_memory_duplicates_001",
  "timestamp": "2026-07-14T07:00:00Z",
  "payload": {}
}
```

The production JSONL runtime reads at most 8 MiB of memory event-log input for this operation, considers at most the latest 200 entries for the authenticated owner, and fails closed if the selected candidates exceed 1 MiB of stored UTF-8 content. Content has already passed the memory store's outer-whitespace trimming boundary; this operation performs no additional case folding, inner-whitespace normalization, Unicode normalization, tokenization, or similarity thresholding. `truncated` is `true` when the owner has more entries than were scanned. IDs within each group are unique and sorted by unsigned UTF-8 byte order, groups contain at least two IDs and are sorted by the same ordering of their first ID, and one ID cannot appear in multiple groups. Existing memory IDs remain unbounded individually for compatibility, while the aggregate UTF-8 bytes of all IDs returned in duplicate groups must not exceed 128 KiB.

```json
{
  "version": 1,
  "type": "memory.duplicate_suggestions.list",
  "request_id": "req_memory_duplicates_001",
  "timestamp": "2026-07-14T07:00:01Z",
  "payload": {
    "groups": [
      {
        "entry_ids": ["memory-1", "memory-7"]
      }
    ],
    "scanned_count": 12,
    "truncated": false
  }
}
```

The response payload contains exactly `groups`, `scanned_count`, and `truncated`. It must not expose memory content, content hashes, vectors, embedding or chat model identifiers, source revisions, source/audit metadata, backend/provider configuration, credentials, route material, workspace or permission state, or direct-store metadata. After storage work and before publishing IDs, the runtime rechecks both the exact authenticated session and the trusted-device public key; trust removal or same-ID key replacement fails closed without a success response. Clients enable the action only after accepting a current-authority unqueried `memory.list`; queried search results cannot grant availability. They accept only the exact pending request response, namespace duplicate-scan request IDs so every noncurrent namespaced error is discarded before global authentication handling even after bounded correlation-history eviction, keep suggestions transient, and validate every returned ID against that authoritative memory list. They disable the feature for the current authority when the runtime returns correlated `unknown_message_type` or `unsupported_operation`, and clear suggestions on a new scan, memory mutation, authoritative memory refresh, disconnect, authentication loss, or channel replacement. Suggestions are review aids only; any later removal remains an explicit existing `memory.delete` action.

### `memory.semantic_duplicate_suggestions.list`

Returns bounded, review-only pair suggestions for approved runtime memory whose full trimmed content is similar under one explicitly selected installed runtime-host-local embedding model. This is a separate operation negotiated by `memory.semantic_duplicate_suggestions.v1`; it does not widen or reinterpret exact `memory.duplicate_suggestions.v1`. Similarity is non-transitive, so the response is a list of pairs rather than clusters. The same memory ID may appear in multiple distinct pairs.

```json
{
  "version": 1,
  "type": "memory.semantic_duplicate_suggestions.list",
  "request_id": "req_memory_semantic_duplicates_001",
  "timestamp": "2026-07-14T09:00:00Z",
  "payload": {
    "embedding_model_id": "ollama:nomic-embed-text",
    "minimum_similarity_basis_points": 9000
  }
}
```

The request payload is closed to the two required fields above. `embedding_model_id` is a nonblank provider-qualified string of at most 256 Unicode code points. `minimum_similarity_basis_points` is an exact JSON integer from 8000 through 10000; booleans, strings, fractional numbers, and integral floating-point spellings are invalid. Standard JSON Schema treats mathematically integral spellings such as `9000.0` as integers, so the schema carries `x-aetherlink-wire-kind: exact-json-integer-token` and transport codecs must preserve and enforce the original number token kind. The runtime rejects missing, nonlocal, nonembedding, or uninstalled models without lexical or exact-scan fallback.

The host reads at most 8 MiB of the authenticated owner's production memory event log and considers only the latest 200 persisted entries, including enabled and disabled entries. Generated drafts, source excerpts, and audit text are not candidates. A candidate is omitted rather than prefixed when its full trimmed content is blank, exceeds the selected model document limit, or would exceed the 1 MiB selected-content budget. Embedding calls contain at most 64 documents and 262,144 UTF-8 bytes, and returned vectors are limited to 65,536 dimensions. Providers with a strong immutable model fingerprint may reuse owner/model/document/source-revision-bound cached vectors; weak-revision providers run on demand without durable cache reuse and fail closed when the selected candidates would require more than one embedding batch. The runtime shares the existing one-semantic-operation-per-connection and four-global-operation limit.

Byte-identical stored-content pairs are excluded because the exact operation already reports them. Cosine similarity is normalized with finite, dimension-consistent vectors and quantized to integer basis points. At most 100 unique pairs are returned. IDs inside each pair use unsigned UTF-8 order; pairs use score descending, then both IDs in unsigned UTF-8 order. Returned ID bytes are capped at 128 KiB. `scanned_count` and `omitted_count` are each bounded to 0...200, and `truncated` reports candidate or pair truncation.

```json
{
  "version": 1,
  "type": "memory.semantic_duplicate_suggestions.list",
  "request_id": "req_memory_semantic_duplicates_001",
  "timestamp": "2026-07-14T09:00:01Z",
  "payload": {
    "pairs": [
      {
        "entry_ids": ["memory-1", "memory-7"],
        "similarity_basis_points": 9342
      }
    ],
    "scanned_count": 12,
    "omitted_count": 1,
    "truncated": false
  }
}
```

The response payload contains exactly `pairs`, `scanned_count`, `omitted_count`, and `truncated`; each pair contains exactly `entry_ids` and `similarity_basis_points`. It never exposes content, vectors, model identifiers or fingerprints, cache state, source revisions, provider configuration, source/audit metadata, credentials, route material, workspace state, or permission state. After inference, the runtime rechecks the selected model identity and source revisions, retrying once on drift. Final publication holds an atomic trusted-device actor snapshot, the selected model's latest runtime-observed descriptor generation, the exact authentication generation/session, and a lifecycle lock that serializes the final source-identity read with runtime-owned memory upsert, delete, and summary approval. Model generations use resolved canonical provider-qualified identities, retain no failed lookup, and cap observed valid states at 256 with fail-closed eviction. The model token covers runtime catalog observations; this no-device contract does not claim live-provider state or quality between provider observations.

Android makes the semantic action available only after a current-authority unqueried `memory.list` and selection of an installed runtime-host-local embedding model. It correlates request ID, channel identity, connection generation, authority generation, model ID, and integer threshold; a response score below that correlated threshold or an ID absent from the current authoritative list fails closed. Semantic state is transient and separate from exact suggestions and device persistence. A new semantic scan, model change, memory mutation, authoritative refresh, disconnect, authentication loss, or channel replacement clears it. Correlated `unknown_message_type` or `unsupported_operation` disables only the semantic capability for that authority. There is no automatic merge, edit, enable, disable, delete, lexical fallback, or first-version cancel operation.

### `memory.semantic_duplicate_clusters.list`

Returns bounded, review-only complete-link clusters under the independently negotiated `memory.semantic_duplicate_clusters.v1` capability. This operation does not reinterpret exact duplicate groups or the existing non-transitive semantic-pair response. The request is exactly the same provider-qualified installed runtime-host-local embedding model plus exact JSON integer 8000...10000 threshold used by semantic pair review.

```json
{
  "version": 1,
  "type": "memory.semantic_duplicate_clusters.list",
  "request_id": "req_memory_semantic_clusters_001",
  "timestamp": "2026-07-14T10:00:00Z",
  "payload": {
    "embedding_model_id": "ollama:nomic-embed-text",
    "minimum_similarity_basis_points": 9000
  }
}
```

The host uses the same owner-scoped latest-200 candidate set, 8 MiB event-log cap, 1 MiB selected-content cap, full-document admission, 64-document and 262,144-byte embedding batches, 65,536-dimension vector cap, strong-revision cache keys, weak-revision one-batch rule, and semantic-operation concurrency slots as pair review. It scores every admitted byte-nonexact pair before any pair-response limit is applied. Exact-content pairs are ineligible because exact duplicate review owns them.

Clustering is deterministic complete-link agglomeration. It starts with singleton candidates ordered by unsigned UTF-8 ID bytes. A merge is eligible only when every cross-cluster pair meets the threshold and is byte-nonexact. At each step the host selects the eligible merged cluster with the greatest minimum internal similarity; ties use the complete canonical merged ID array. Singletons are omitted. Consequently every two entries returned in one cluster directly meet the request threshold; threshold chains cannot place dissimilar endpoints together.

```json
{
  "version": 1,
  "type": "memory.semantic_duplicate_clusters.list",
  "request_id": "req_memory_semantic_clusters_001",
  "timestamp": "2026-07-14T10:00:01Z",
  "payload": {
    "clusters": [
      {
        "entry_ids": ["memory-1", "memory-4", "memory-7"],
        "minimum_similarity_basis_points": 9124
      }
    ],
    "scanned_count": 12,
    "omitted_count": 1,
    "truncated": false
  }
}
```

The response payload contains exactly `clusters`, `scanned_count`, `omitted_count`, and `truncated`. Each cluster contains exactly two through 200 canonical unique `entry_ids` and an exact integer `minimum_similarity_basis_points`; IDs cannot repeat across clusters. At most 100 clusters and 128 KiB of aggregate ID bytes are returned. Clusters order by minimum score descending and then the full canonical ID array. `truncated` reports candidate/source omission; a response-bound overflow fails closed instead of returning a partial cluster partition.

The operation reuses semantic pair review's selected-model/source retry, atomic trusted-device snapshot, canonical observed-model generation, exact authentication generation/session, and final memory-mutation lifecycle lock. It returns no content, vectors, model/cache/source identity, backend, credential, route, workspace, permission, or audit metadata and never mutates memory. Android correlates the exact channel, connection authority, selected model, and threshold; validates every ID against the current unqueried authoritative memory list; rejects below-threshold scores, repeated or unknown IDs, byte-identical members, and stale model or authority responses; and keeps cluster state transient. Unsupported cluster operation disables only this capability. New scans, model changes, memory mutations or authoritative refreshes, disconnect, authentication loss, and channel replacement clear the result. Manual existing row controls remain the only mutation path.

### `memory.upsert`

Creates or updates one runtime-owned memory entry. If `id` is omitted, the runtime assigns one. `enabled` defaults to `true` for new entries and preserves the previous value for updates when omitted. `source` is runtime-derived output metadata and is not accepted in this request.

`memory.upsert.payload` accepts only optional `id`, required `content`, and optional `enabled`. `id` must be a non-blank string when present, `content` must be a non-blank string, and `enabled` must be a boolean when present; malformed or blank allowed fields return `invalid_payload` instead of being coerced or treated as omitted. Clients must not supply `entry`; it is response-only saved memory data. Upsert requests also must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source metadata, search metadata, or direct-store metadata.

```json
{
  "version": 1,
  "type": "memory.upsert",
  "request_id": "req_memory_upsert_001",
  "timestamp": "2026-06-25T05:26:00Z",
  "payload": {
    "id": "memory-1",
    "content": "Prefers concise Korean answers.",
    "enabled": true
  }
}
```

The response uses the same `type` and returns the saved entry:

`memory.upsert` result payloads accept only `entry`. The saved result `entry` uses the same closed memory-entry shape as `memory.list`: top-level `entry` accepts only `id`, `content`, `enabled`, `created_at`, `updated_at`, `source`, and `search`; `entry.source` accepts only `kind`, `draft_id`, `summary_method`, `session`, `source_message_count`, `source_range`, and `source_pointers`; nested `source_pointers` accept only `session_id`, `message_index`, `role`, `created_at`, and `excerpt`. Upsert results must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source approval handles, citations, trusted-source review data, audit handles, direct-store metadata, or direct-provider route material.

```json
{
  "version": 1,
  "type": "memory.upsert",
  "request_id": "req_memory_upsert_001",
  "timestamp": "2026-06-25T05:26:01Z",
  "payload": {
    "entry": {
      "id": "memory-1",
      "content": "Prefers concise Korean answers.",
      "enabled": true,
      "created_at": "2026-06-25T05:20:00Z",
      "updated_at": "2026-06-25T05:26:01Z"
    }
  }
}
```

### `memory.delete`

Deletes one runtime-owned memory entry by id. Implementations may keep append-only tombstones internally, but deleted memory entries must not be returned by `memory.list` or injected into chat context.

`memory.delete.payload` accepts only `id`. `id` must be a non-blank string; malformed or blank allowed fields return `invalid_payload` before runtime memory store mutation. Clients must not supply `deleted_at`; it is runtime-generated acknowledgement metadata. Delete requests also must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-store metadata.

```json
{
  "version": 1,
  "type": "memory.delete",
  "request_id": "req_memory_delete_001",
  "timestamp": "2026-06-25T05:27:00Z",
  "payload": {
    "id": "memory-1"
  }
}
```

Response:

`memory.delete` result payloads accept only `id` and `deleted_at`. Delete results must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source approval handles, citations, trusted-source review data, audit handles, direct-store metadata, or direct-provider route material.

```json
{
  "version": 1,
  "type": "memory.delete",
  "request_id": "req_memory_delete_001",
  "timestamp": "2026-06-25T05:27:01Z",
  "payload": {
    "id": "memory-1",
    "deleted_at": "2026-06-25T05:27:01Z"
  }
}
```

### `memory.summary.drafts.list`

Lists deterministic long-inactivity memory summary drafts for the authenticated trusted device. This is a review/read command only; clients must not treat it as approved memory, and runtimes must not persist new memory entries from this request.

`memory.summary.drafts.list.payload` accepts only optional integer `limit`. Malformed allowed fields, such as string or fractional `limit` values, return `invalid_payload` instead of being coerced or treated as omitted. Clients must not supply `drafts`; it is response-only review data. Draft-list requests also must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, or direct-store metadata.

Request:

```json
{
  "version": 1,
  "type": "memory.summary.drafts.list",
  "request_id": "req_memory_summary_drafts_001",
  "timestamp": "2026-07-01T09:30:00Z",
  "payload": {
    "limit": 10
  }
}
```

Response:

```json
{
  "version": 1,
  "type": "memory.summary.drafts.list",
  "request_id": "req_memory_summary_drafts_001",
  "timestamp": "2026-07-01T09:30:01Z",
  "payload": {
    "drafts": [
      {
        "id": "long-inactivity:session-1:1780304525000:6",
        "session": {
          "session_id": "session-1",
          "title": "Runtime notes",
          "model": "ollama:llama3.1:8b",
          "last_activity_at": "2026-06-01T09:02:05Z",
          "message_count": 7,
          "inactive_seconds": 2592000
        },
        "source_message_count": 6,
        "source_range": "visible messages 1-6 of 6",
        "source_pointers": [
          {
            "session_id": "session-1",
            "message_index": 1,
            "role": "user",
            "created_at": "2026-06-01T09:00:00Z",
            "excerpt": "Summarize my preference."
          }
        ],
        "summary_preview": "User: Summarize my preference.",
        "summary_method": "deterministic_preview"
      }
    ]
  }
}
```

Draft payloads always include `summary_method`, which is `deterministic_preview` or `llm_summary_v1`. Generated drafts also include optional `generated_at` and `generated_model_id`; deterministic drafts omit those fields.

### `memory.summary.draft.generate`

Generates a review-required summary for one current owner-scoped draft. The request requires exact stale guards and an installed runtime-host local chat model. The runtime does not trust the client-supplied session id as authority, and it never stores the result as approved memory.

`memory.summary.draft.generate.payload` request data accepts exactly nonblank string `draft_id`, nonblank string `model`, nonblank string `expected_session_id`, and positive integer `expected_source_message_count`. The response accepts exactly `draft`, using the same closed draft shape as `memory.summary.drafts.list`. Unknown metadata or malformed values return `invalid_payload`. A missing or owner-inaccessible draft returns `memory_summary_draft_unavailable`; changed stale guards or a source mutation during inference return `memory_summary_draft_stale`; malformed, blank, oversized, or failed model output returns `memory_summary_draft_generation_failed` without replacing the deterministic preview or writing memory.

Request:

```json
{
  "version": 1,
  "type": "memory.summary.draft.generate",
  "request_id": "req_memory_summary_generate_001",
  "timestamp": "2026-07-11T05:30:00Z",
  "payload": {
    "draft_id": "long-inactivity:session-1:1780304525000:6",
    "model": "ollama:llama3.1:8b",
    "expected_session_id": "session-1",
    "expected_source_message_count": 6
  }
}
```

Response:

```json
{
  "version": 1,
  "type": "memory.summary.draft.generate",
  "request_id": "req_memory_summary_generate_001",
  "timestamp": "2026-07-11T05:30:02Z",
  "payload": {
    "draft": {
      "id": "long-inactivity:session-1:1780304525000:6",
      "session": {
        "session_id": "session-1",
        "title": "Runtime notes",
        "model": "ollama:llama3.1:8b",
        "last_activity_at": "2026-06-01T09:02:05Z",
        "message_count": 7,
        "inactive_seconds": 3457677
      },
      "source_message_count": 6,
      "source_range": "visible messages 1-6 of 6",
      "source_pointers": [
        {
          "session_id": "session-1",
          "message_index": 1,
          "role": "user",
          "created_at": "2026-06-01T09:00:00Z",
          "excerpt": "Summarize my preference."
        }
      ],
      "summary_preview": "The user prefers concise runtime notes.",
      "summary_method": "llm_summary_v1",
      "generated_at": "2026-07-11T05:30:02Z",
      "generated_model_id": "ollama:llama3.1:8b"
    }
  }
}
```

### `memory.summary.draft.approve`

Approves one currently available long-inactivity memory summary draft into runtime-owned memory for the authenticated trusted device. The runtime must look up the draft from its owner-scoped chat store by `draft_id`; it must not trust client-supplied session ids as authority. If `expected_session_id` or `expected_source_message_count` is supplied and no longer matches the recomputed draft, the runtime returns `memory_summary_draft_stale`. If the draft is unavailable or belongs to another owner, the runtime returns `memory_summary_draft_unavailable`.

`memory.summary.draft.approve.payload` accepts only string `draft_id`, optional string `content`, optional boolean `enabled`, optional string `expected_session_id`, and optional integer `expected_source_message_count`. Malformed allowed fields, such as blank `draft_id`, non-string or blank `content`, non-boolean `enabled`, non-string or blank `expected_session_id`, or string/fractional `expected_source_message_count` values, return `invalid_payload` instead of being coerced or treated as omitted. Clients must not supply `status` or `entry`; they are response-only approval data. Approval requests also must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source metadata, or direct-store metadata.

`memory.summary.draft.approve` result payloads accept only `draft_id`, `status`, and `entry`. The approved-memory result `entry` uses the same closed memory-entry shape as `memory.list`: top-level `entry` accepts only `id`, `content`, `enabled`, `created_at`, `updated_at`, `source`, and `search`; `entry.source` accepts only `kind`, `draft_id`, `summary_method`, `session`, `source_message_count`, `source_range`, and `source_pointers`. Approved-memory result `entry.source.source_pointers` accepts only `session_id`, `message_index`, `role`, `created_at`, and `excerpt`. Clients preserve pending draft decisions when unsupported result metadata is rejected, so a canonical retry on the same request id can still approve the draft. Approval results must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source approval handles, citations, trusted-source review data, audit handles, or direct-provider route material.

Request:

```json
{
  "version": 1,
  "type": "memory.summary.draft.approve",
  "request_id": "req_memory_summary_draft_approve_001",
  "timestamp": "2026-07-01T09:31:00Z",
  "payload": {
    "draft_id": "long-inactivity:session-1:1780304525000:6",
    "enabled": true,
    "expected_session_id": "session-1",
    "expected_source_message_count": 6
  }
}
```

Response:

```json
{
  "version": 1,
  "type": "memory.summary.draft.approve",
  "request_id": "req_memory_summary_draft_approve_001",
  "timestamp": "2026-07-01T09:31:01Z",
  "payload": {
    "draft_id": "long-inactivity:session-1:1780304525000:6",
    "status": "approved",
    "entry": {
      "id": "memory-summary:long-inactivity:session-1:1780304525000:6",
      "content": "User: Summarize my preference.",
      "enabled": true,
      "created_at": "2026-07-01T09:31:01Z",
      "updated_at": "2026-07-01T09:31:01Z",
      "source": {
        "kind": "long_inactivity_summary_draft",
        "draft_id": "long-inactivity:session-1:1780304525000:6",
        "summary_method": "deterministic_preview",
        "session": {
          "session_id": "session-1",
          "title": "Runtime notes",
          "model": "ollama:llama3.1:8b",
          "last_activity_at": "2026-06-01T09:02:05Z",
          "message_count": 7,
          "inactive_seconds": 2592000
        },
        "source_message_count": 6,
        "source_range": "visible messages 1-6 of 6",
        "source_pointers": [
          {
            "session_id": "session-1",
            "message_index": 1,
            "role": "user",
            "created_at": "2026-06-01T09:00:00Z",
            "excerpt": "Summarize my preference."
          }
        ]
      }
    }
  }
}
```

### `memory.summary.draft.dismiss`

Dismisses one currently available long-inactivity memory summary draft for the authenticated trusted device without creating runtime-owned memory. The runtime must recompute the owner-scoped draft by `draft_id`; it must not trust client-supplied session ids as authority. If `expected_session_id` or `expected_source_message_count` is supplied and no longer matches the recomputed draft, the runtime returns `memory_summary_draft_stale`. If the draft is unavailable or belongs to another owner, the runtime returns `memory_summary_draft_unavailable`. Dismissed drafts are hidden from later draft-list responses for that owner. Repeating dismiss for the same current draft id is idempotent.

`memory.summary.draft.dismiss.payload` accepts only string `draft_id`, optional string `expected_session_id`, and optional integer `expected_source_message_count`. Malformed allowed fields, such as blank `draft_id`, non-string or blank `expected_session_id`, or string/fractional `expected_source_message_count` values, return `invalid_payload` instead of being coerced or treated as omitted. Clients must not supply `status` or `dismissed_at`; they are response-only dismissal data. Dismiss requests also must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source metadata, or direct-store metadata.

`memory.summary.draft.dismiss` result payloads accept only `draft_id`, `status`, and `dismissed_at`. Clients preserve pending draft decisions when unsupported result metadata is rejected, so a canonical retry on the same request id can still dismiss the draft. Dismissal results must not carry backend URLs, provider URLs, backend credentials, route tokens, relay secrets, requested route tokens, workspace IDs, permission grants, source paths, source-control state, source approval handles, citations, trusted-source review data, audit handles, direct-store metadata, or direct-provider route material.

Request:

```json
{
  "version": 1,
  "type": "memory.summary.draft.dismiss",
  "request_id": "req_memory_summary_draft_dismiss_001",
  "timestamp": "2026-07-01T09:32:00Z",
  "payload": {
    "draft_id": "long-inactivity:session-1:1780304525000:6",
    "expected_session_id": "session-1",
    "expected_source_message_count": 6
  }
}
```

Response:

```json
{
  "version": 1,
  "type": "memory.summary.draft.dismiss",
  "request_id": "req_memory_summary_draft_dismiss_001",
  "timestamp": "2026-07-01T09:32:01Z",
  "payload": {
    "draft_id": "long-inactivity:session-1:1780304525000:6",
    "status": "dismissed",
    "dismissed_at": "2026-07-01T09:32:01Z"
  }
}
```

## Future Extension Points

Runtime-side chat history and basic memory CRUD are active. The broader namespaces below remain reserved until their product, privacy, and permission models are designed.

- Advanced memory: `memory.search`, automatic or unreviewed memory extraction, live-model cluster-threshold calibration, memory reflection, embedding-backed recall, memory compaction, richer dismiss/review policy, and project-scoped memory. Exact byte-identical groups, model-dependent review-only semantic pairs, deterministic complete-link review-only semantic clusters, and explicit review-required long-inactivity summary generation are active; none performs automatic merge or unreviewed extraction. Live-model calibration and automatic merge policy remain future work. Archived sessions remain excluded from memory, reflection, research, and compaction inputs unless restored or explicitly selected by the user.
- Session compaction: known model context windows now use conservative UTF-8/framing accounting, a bounded output reserve, a hard input budget, adaptive oldest-whole-turn compaction, fixed runtime provenance plus an untrusted assistant historical summary, a bounded same-model LLM summary prepass with deterministic fallback, an owner/session/model/policy-scoped durable sidecar cache with exact full-lineage reuse and strict-prefix incremental evolution committed only after successful primary completion, request-bound `adaptive_backend_only_summary_v3` source fingerprints, append-only effective terminal resolution, and pre-backend `chat_context_window_exceeded` rejection. Missing context-window metadata retains the legacy 24,000-character heuristic; v1/v2, the previous v3 summary policy, and resolution-free events remain readable. Provider-tokenizer parity and richer context-window policies remain future work. This is separate from model lifecycle messages such as unload-after-10-minutes-inactive.
- Embeddings/research: reserve the `embeddings.` namespace, keep `retrieval.query` as the only active document retrieval message with legacy lexical and explicit approved semantic modes, reserve unsupported `retrieval.*` beyond it, keep `index.documents.list` as the only active `index.*` catalog message, and allow only `research.brief.create` plus `research.notebooks.list` in `research.*`. `citation.resolve` is the only active `citation.*` message; `source_anchor.resolve` is the only active `source_anchor.*` message; `chat.source_attribution.resolve` is the only active `chat.source_attribution.*` message; and `trusted_source.approve`, `trusted_source.dismiss`, `trusted_source.list`, and `trusted_source.revoke` are the only active `trusted_source.*` messages. Every other message in those namespaces, including `research.web.query`, `citation.sources.list`, and `source_anchor.metadata.get`, remains reserved, as does `source_control.*`. `retrieval.query` returns canonical source anchors without paths, while the active citation and research flows add only opaque revision-bound handles, authenticated-device `chat_context` grants, safe attributions, and chat-backed notebook summaries. Embedding models remain separate from chat models. Protocol schema hygiene rejects unsupported namespace entries while validating the exact active request/response unions.
- Compatibility wording: the current `chat.sessions.list` and `memory.list` `embedding_model_id` hints are consumed by bounded semantic ranking; Android retries only a strict unknown-field rejection from an older memory runtime without the hint, while deterministic lexical fallbacks and `retrieval.query` remain available.
- Projects/workspaces: reserve the `projects.` namespace for future project-scoped chats, files, instructions, memory, indexes, model/backend preferences, trusted-source controls, and project-level search/research. Do not add active message names until the product shape is ready.
- Scheduling/automation: reserve the `automation.` namespace for future scheduled tasks, reminders, monitors, recurring automations, runtime-triggered jobs, permission prompts, audit logs, and mobile approval/status surfaces. Do not add active message names until the scheduler and permission model are designed.
- Protocol schema hygiene rejects active message enum entries under `projects.` and `automation.` until those product and permission models are ready.
- Generic tool execution: the generic `tool.` namespace remains reserved for future runtime-owned tool invocation, result delivery, permission prompts, and audit semantics. Candidate names such as `tool.call`, `tool.result`, and `tool.run` are examples only and are not active protocol messages. Protocol schema hygiene rejects active message enum entries under generic `tool.` until runtime tool permissions, execution, result handling, and audit semantics are designed.
- Permission, approval, and audit control: reserve the `permission.` namespace, reserve the `approval.` namespace, and reserve the `audit.` namespace for the future runtime permission broker, mobile approval surfaces, and audit-log review/control flows. Candidate names such as `permission.request`, `approval.prompt`, and `audit.events.list` are examples only and are not active protocol messages. Protocol schema hygiene rejects active message enum entries under `permission.`, `approval.`, and `audit.` until the production permission, approval, audit retention, redaction, and failure semantics are designed.
- Files/images: `chat.send.messages[].attachments[]` is the initial carrier for user-selected images and parsed documents. Attachment objects accept only `type`, `mime_type`, `name`, `data_base64`, and `text`; they must not carry source paths, workspace IDs, source-control state, backend URLs, backend credentials, route material, or trusted-source metadata. Runtime-side ingestion, parsing, indexing, and backend calls must run through the AetherLink Runtime, never direct client-to-backend access. Future dedicated file/index messages can extend this once project/workspace permissions are designed.
- Runtime action control: reserve the `file.` namespace, reserve the `terminal.` namespace, reserve the `network.` namespace, and reserve the `backend.` namespace for future runtime-owned file operations, terminal/process controls, network requests or URL opens, and backend/provider configuration calls. Candidate names such as `file.read`, `file.write`, `file.index`, `terminal.exec`, `terminal.kill`, `network.request`, `network.open`, `backend.call`, and `backend.configure` are examples only and are not active protocol messages. The `file.` namespace is distinct from current `chat.send` attachments, and `backend.` is distinct from current `models.list`, `models.pull`, and `chat.send` model selection. Protocol schema hygiene rejects active message enum entries under `file.`, `terminal.`, `network.`, and `backend.` until runtime permissions, approval UI, resource limits, redaction, and audit semantics are designed.
- Routes/connectivity: `route.refresh` is the current active route message for authenticated remote route-material renewal, currently covering relay lease material and opaque P2P rendezvous records. Other `route.*` names remain reserved for future route diagnostics, remote candidate exchange, encrypted relay allocation status, and route failure reporting because production NAT traversal, signaling, DHT/bootstrap discovery, and production relay transport are not complete yet. Candidate future names such as `route.candidates.exchange`, `route.diagnostics.report`, `route.allocation.status`, and `route.failure.report` are intentionally inactive. Protocol schema hygiene ensures route.refresh remains the only active `route.*` message.
- Private overlay routing: reserve the `p2p.` namespace, reserve the `rendezvous.` namespace, reserve the `bootstrap.` namespace, reserve the `dht.` namespace, reserve the `nat.` namespace, reserve the `stun.` namespace, and reserve the `turn.` namespace for future paired-device P2P sessions, short-lived rendezvous records, bootstrap/DHT lookup, NAT candidate gathering, STUN-like discovery, and TURN-style relay allocation. Candidate message names such as `p2p.session.open`, `rendezvous.records.publish`, `bootstrap.records.lookup`, `dht.records.put`, `nat.candidates.gather`, `stun.binding.request`, and `turn.relay.allocate` are examples only and are not active protocol messages. Current P2P support is QR/route-material storage and route planning for opaque `p2p_rendezvous` records, not active P2P signaling. Protocol schema hygiene rejects active message enum entries under `p2p.`, `rendezvous.`, `bootstrap.`, `dht.`, `nat.`, `stun.`, and `turn.` until production signaling, NAT traversal, replay protection, permission/audit semantics, and session key binding are designed.
- Encrypted session setup: reserve the `session.` namespace, reserve the `key_exchange.` namespace, reserve the `encrypted_session.` namespace, and reserve the `anti_replay.` namespace for future production session-key exchange, encrypted-session establishment, key rotation, and replay-window control. Candidate message names such as `session.key.exchange`, `key_exchange.begin`, `encrypted_session.open`, and `anti_replay.window.commit` are examples only and are not active protocol messages. Current relay-frame encryption is development route material, not the production encrypted-session handshake. Protocol schema hygiene rejects active message enum entries under `session.`, `key_exchange.`, `encrypted_session.`, and `anti_replay.` until the production encrypted session handshake, paired-identity binding, replay protection, token rotation, permission/audit semantics, and failure recovery are designed.
- Transport and crypto control: reserve the `transport.` namespace and reserve the `crypto.` namespace for future production transport handshakes, rekey operations, crypto-session establishment, and key rotation. Candidate message names such as `transport.handshake`, `transport.rekey`, `crypto.session.open`, and `crypto.key.rotate` are examples only and are not active protocol messages. Current relay-frame encryption is route-material-based development transport, not production E2E transport control. Protocol schema hygiene rejects active message enum entries under `transport.` and `crypto.` until the production E2E transport encryption, key rotation, replay-window, audit, and failure recovery model is designed.
- Internal Python tools: reserve the `python.` namespace for future deterministic Python execution through the runtime host. Candidate message names include `python.run` and `python.exec`, but they are examples only and are not active protocol messages. Do not add active message names until the runtime Python sandbox, permission prompts, resource limits, and audit model are designed. Python execution must run in the AetherLink Runtime with runtime-owned permissions, scoping, and audit logs.
- Skills: reserve the `skills.` namespace for future prompt-only skills, approval-required skill runs, results, permissions, and audit logs. Candidate message names include `skills.list`, `skills.run`, and `skills.result`. Do not add active message names until the runtime permission broker and skill registry are designed.
- MCP: reserve the `mcp.` namespace for future runtime-side MCP server registry, tool listing, tool calls, tool results, permissions, and audit logs. Candidate message names include `mcp.servers.list`, `mcp.tools.list`, `mcp.tool.call`, and `mcp.tool.result`. Do not add active message names until the runtime MCP client and permission model are designed.
- Web search: reserve the `web_search.` namespace for future runtime-side search provider requests, result lists, and result-opening/audit messages. Candidate message names include `web_search.query`, `web_search.results`, and `web_search.open_result`. Do not add active message names until the runtime search provider, citation, cache, and permission model are designed.
- Protocol schema hygiene rejects active message enum entries under `skills.`, `mcp.`, `web_search.`, and `python.` until those runtime permission models are ready.

Future tool execution, project/workspace handling, scheduling/automation, memory, file/image handling, Python, skills, MCP, and web search must execute on the AetherLink Runtime and flow through permission checks. The client app remains the controller UI. Project files, Python code, and scheduled jobs are sensitive runtime actions, even when a mobile client provides the approval or status UI.
