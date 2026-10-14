"""Opportunistic clock policy for the single LINK telemetry worker.

No thread, cached challenge, frame, HTTP implementation or persisted setting.
Only publish_clock performs the existing authenticated clock exchange.
"""
from collections import deque
import time

from clock_sync import publish_clock, TOTAL_EXCHANGE_S
from push_fsless_metrics import validate_host


CLOCK_INTERVAL_S = 60.0
CLOCK_SLOT_S = TOTAL_EXCHANGE_S + 0.25
RESULTS = frozenset(('CLOCK_SAMPLE_ACCEPTED', 'CLOCK_COORDINATION_HOLD',
                     'CLOCK_COMPATIBILITY_HOLD', 'CLOCK_SOURCE_HOLD',
                     'CLOCK_UNKNOWN_NO_RETRY', 'CLOCK_STOPPED_NO_RETRY'))
SUSPENDED = frozenset(('CLOCK_UNKNOWN_NO_RETRY', 'CLOCK_COMPATIBILITY_HOLD',
                       'CLOCK_TARGET_REVERIFY_HOLD', 'CLOCK_STOPPED_NO_RETRY'))


class LinkClockPublisher:
    def __init__(self, verified_host, transport_factory, *, clock=time.monotonic):
        # An explicit owner assertion, NOT an automatic device-identification probe.
        self.verified_host = validate_host(verified_host)
        self.transport_factory = transport_factory
        self.clock = clock
        self.next_due = 0.0
        self.state = 'CLOCK_WAITING_METRICS'
        self.last_result = None
        self.attempts = self.accepted = 0
        self.history = deque(maxlen=16)

    def retarget(self):
        # Even returning to the old IP needs a new explicit owner assertion.
        self.next_due = 0.0
        self.state = 'CLOCK_TARGET_REVERIFY_HOLD'

    def disconnected(self):
        self.next_due = 0.0
        if self.state not in SUSPENDED:
            self.state = 'CLOCK_WAITING_METRICS'

    def after_metrics(self, host, next_metric_due, *, stop=None):
        """Called inline only after a fresh accepted metric; never move its due time.

        Return whether the Digest nonce might have changed, so LINK can discard
        its telemetry opener before the next normally scheduled metric exchange.
        """
        if host != self.verified_host:
            self.retarget()
        if self.state in SUSPENDED or (stop is not None and stop.is_set()):
            return False
        started = self.clock()
        if started < self.next_due or next_metric_due - started < CLOCK_SLOT_S:
            return False
        try:
            # Fresh transport for every operation: never retain a boot/challenge.
            transport = self.transport_factory(host)
            if next_metric_due - self.clock() < CLOCK_SLOT_S:
                return False
            result = publish_clock(host, transport, authorize_clock_sync=True,
                                   cancelled=stop.is_set if stop is not None else None)
        except Exception:
            # Do not expose arbitrary exceptions or assume a POST was not sent.
            result = 'CLOCK_UNKNOWN_NO_RETRY'
        if result not in RESULTS:
            result = 'CLOCK_UNKNOWN_NO_RETRY'
        completed = self.clock()
        self.next_due = completed + CLOCK_INTERVAL_S
        self.state = self.last_result = result
        self.attempts += 1
        self.accepted += result == 'CLOCK_SAMPLE_ACCEPTED'
        self.history.append(dict(result=result,
                                 duration_ms=round(max(0, completed - started) * 1000, 3)))
        return result != 'CLOCK_COORDINATION_HOLD'

    def snapshot(self):
        return dict(enabled=True, state=self.state, last_result=self.last_result,
                    interval_s=CLOCK_INTERVAL_S, attempts=self.attempts,
                    accepted=self.accepted, history=list(self.history),
                    source='HOST_CLOCK_EXCHANGE_ONLY')
