"""Sample content for new guests and accounts.

See /workspace/specs/onboarding-samples.md. Sample rabbits are Maple (doe) and
Cedar (buck) — made-up names that don't clash with the demo herd's Juniper line
or the bot name Hazel. Samples never count toward stats, exports, caps or reminders.
"""

from .registry import EXEMPT_OWNER_MODELS, SAMPLE_CHILD_MODELS, SAMPLE_OWNER_MODELS, sample_models
from .service import add_samples, clear_samples, sample_count, screen_has_samples

__all__ = [
    "SAMPLE_OWNER_MODELS", "SAMPLE_CHILD_MODELS", "EXEMPT_OWNER_MODELS", "sample_models",
    "add_samples", "clear_samples", "sample_count", "screen_has_samples",
]
