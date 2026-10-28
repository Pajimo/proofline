"""Safety layer: hard stops, the injection guard and the outbound check.

Order for every inbound customer message:
  1. rules.check_text: keyword rules on text and transcripts. Deterministic, no model.
  2. model.check: Spark reads text + video for danger the keywords missed.
  3. Only then does the agent see the message, wrapped by guard.wrap_untrusted.
And for every outbound message: guard.check_outbound blocks prices that weren't approved.
"""
from .guard import OutboundBlocked, check_outbound, looks_like_injection, wrap_untrusted
from .rules import Stop, check_text, stop_message

__all__ = ["OutboundBlocked", "Stop", "check_outbound", "check_text", "looks_like_injection",
           "stop_message", "wrap_untrusted"]
