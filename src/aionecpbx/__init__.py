"""Async clients for NEC SL2100 and SV9100 phone systems.

* :class:`SmdrClient` keeps a connection to the phone system's SMDR port and
  hands over each call-log line; :func:`parse_line` turns a line into an
  :class:`SmdrRecord`.
* :class:`AmiClient` follows live calls (ringing, answered, ended) through
  FreePBX's Asterisk Manager Interface, and turns do-not-disturb on and off.
"""

from __future__ import annotations

from .ami import (
    DEFAULT_AMI_PORT,
    LIVE_ANSWERED,
    LIVE_ENDED,
    LIVE_RINGING,
    AmiAuthError,
    AmiClient,
    LiveCall,
    async_test_login,
    parse_message,
)
from .client import DEFAULT_SMDR_PORT, SmdrClient, async_probe
from .smdr import (
    DATE_AUTO,
    DATE_DMY,
    DATE_MDY,
    DATE_ORDERS,
    DIRECTION_INCOMING,
    DIRECTION_INTERNAL,
    DIRECTION_OUTGOING,
    DIRECTION_UNKNOWN,
    SmdrRecord,
    format_mapping,
    is_record_line,
    lookup_name,
    normalise_number,
    parse_line,
    parse_mapping,
)

__version__ = "0.1.0"

__all__ = [
    "DATE_AUTO",
    "DATE_DMY",
    "DATE_MDY",
    "DATE_ORDERS",
    "DEFAULT_AMI_PORT",
    "DEFAULT_SMDR_PORT",
    "DIRECTION_INCOMING",
    "DIRECTION_INTERNAL",
    "DIRECTION_OUTGOING",
    "DIRECTION_UNKNOWN",
    "LIVE_ANSWERED",
    "LIVE_ENDED",
    "LIVE_RINGING",
    "AmiAuthError",
    "AmiClient",
    "LiveCall",
    "SmdrClient",
    "SmdrRecord",
    "__version__",
    "async_probe",
    "async_test_login",
    "format_mapping",
    "is_record_line",
    "lookup_name",
    "normalise_number",
    "parse_line",
    "parse_mapping",
    "parse_message",
]
