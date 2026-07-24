# Bounded dependency source acquisition Wave3 decision v1

This decision fixes the exact Wave3 acquisition request set derived from the
validated 32-of-32 checksum-identity successor decision. The set contains 16
ordered module-version tuples and exactly two resources per tuple: the public
Go module proxy `.mod` response followed by its `.zip` response. Every request
has a deterministic escaped path and a pinned expected H1.

This document is preparation, not execution authority. It does not authorize
DNS, TCP, TLS, HTTPS, filesystem mutation, source acquisition, extraction,
loading, execution, compilation, package-manager use, subprocesses, Git,
devices, deployment, authentication, credentials, or user action. Checksum
identity is not source, author, or repository attestation.

The only next action is a separately bound one-use execution permit for the
exact 32-resource sequence.
