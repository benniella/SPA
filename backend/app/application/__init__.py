"""Use-case orchestration: one module per capability.

Use cases receive parsed input, coordinate domain objects through ports, commit,
and return domain objects — never HTTP responses. No FastAPI imports are
permitted in this package, so it stays testable without a running server.
"""
