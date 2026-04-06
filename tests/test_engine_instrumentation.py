"""Phase 5.1.1 instrumentation tests — D-22.1..D-22.10."""
from __future__ import annotations

import pytest

from engine import (
    run_simulation,
    SimulationContext,
    EventCompleted,
    LongEventWarning,
    SenescentEntered,
    SenescentExited,
    EventReceived,
    TransitionFired,
    InstanceDeleted,
    Event,
)


# ---------------------------------------------------------------------------
# D-22.1: EventCompleted is emitted exactly once per event dispatch
# ---------------------------------------------------------------------------


def test_event_completed_emitted():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.2: LongEventWarning is NOT emitted when threshold is None (default)
# ---------------------------------------------------------------------------


def test_no_long_event_warning_by_default():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.3: LongEventWarning fires when a long-running action exceeds threshold
# ---------------------------------------------------------------------------


def test_long_event_warning_fires():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.4: SenescentEntered fires on transition into a senescent state
# ---------------------------------------------------------------------------


def test_senescent_entered_on_transition():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.5: SenescentExited fires on dispatch out of a senescent state
# ---------------------------------------------------------------------------


def test_senescent_exited_on_wakeup():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.6: No double-emit — SenescentEntered fires once across sen→sen transitions
# ---------------------------------------------------------------------------


def test_no_double_senescent_entered():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.7: Final state wins — entering a state that is both senescent AND final
#         emits InstanceDeleted and does NOT emit SenescentEntered
# ---------------------------------------------------------------------------


def test_final_state_wins_over_senescence():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.8: Initial state senescence — newly-created instance whose initial state
#         is senescent emits SenescentEntered immediately after StateEntered
# ---------------------------------------------------------------------------


def test_initial_state_senescence():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.9: senescent_states defaults to set() — scheduler never emits senescence
#         micro-steps for classes that don't populate it
# ---------------------------------------------------------------------------


def test_empty_senescent_states_no_emission():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")


# ---------------------------------------------------------------------------
# D-22.10: Manifest with multiple classes, mixed senescent/non-senescent —
#          each class's classification is independent
# ---------------------------------------------------------------------------


def test_multi_class_senescence_independent():
    pytest.fail("Phase 5.1.1 plan 02/03 — not yet implemented")
