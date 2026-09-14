"""Pydantic v2 request/response schemas, one module per API resource.

Conventions (sprint brief): money as int cents, dates ISO-8601, UUIDs as strings,
[enc] columns never exposed (only *_last4), audit before/after redacted.
"""
