# Controlled-Spike Networking Fallback Review v2

## Trigger

The exact libjuice v1.7.2 source audit failed before compiler invocation. `libjuice-source-audit-v1.json` records multiple independent P1 blockers and activates the existing mandatory fallback rule. This review therefore closes libjuice as rejected and opens `libnice-0.1.23-glib-c-abi` only as the next proposal to evaluate.

## Proposal State

Status is `proposed_not_selected`. The fallback is not approved, selected, downloaded, compiled, linked, loaded, or executed. The earlier review's official libnice project and `NiceAgent` references are retained as review references; this step performed no libnice fetch.

The reason to evaluate libnice is narrow: the prior official API review identified explicit regular-nomination and consent-freshness controls. That does not establish suitability. GLib dependency closure, lifecycle, Android/macOS packaging, static C ABI shape, entropy, parser behavior, destination authorization, diagnostics, cancellation, and symbol visibility remain unproven.

## Required Next Decision

A separate explicit decision must authorize the exact official libnice 0.1.23 source and required dependency acquisition before any network access. That decision must fix hosts, URLs, transport, redirects, size ceilings, package identities, and digest recording. After acquisition, another reviewed manifest and source audit must pass before a compiler may be invoked.

No implicit fallback, package-manager fallback, source fork, or patched libjuice path is authorized. Socket execution, runtime or harness network I/O, Phase B, production networking, and deployment remain prohibited. The other three bounded Phase A recommendation records remain unchanged; this review changes only the failed networking-library unit.
