# Advanced Tuning: Cluster Timing and Propagation

This guide explains the cluster-level controls under `cluster` in your network config, how they interact, the hard constraints between them, and safe tuning patterns.

!!! warning "here be dragons"
    Most deployments should keep the defaults. Tune only when you have measurable symptoms and a way to validate improvements.


## How the pieces fit together

- `rate_limits.update` governs how quickly user-facing state (node/monitor statuses) is propagated. It should be less than or equal to the minimum of your `node_config[].poll_rate` and `monitors[].interval` so changes aren’t rate-limited below the sampling cadence.
- `rate_limits.priority_update` governs internal/system table (leader election, clock table, node status table) updates. Lower values yield faster leader elections and higher clock table fidelity; higher values slow elections and reduce clock table accuracy by roughly ±`priority_update`.
- `clock_pulse_interval` is the metronome for measuring propagation delay and clock deltas that later drives node status table updates in which the leader election system runs off. It also sets the baseline for offline detection: a node is considered offline if its most recent clock table entry is approximately as old as `clock_pulse_interval * 2 + propagation_delay`. keep in mind clock pulses are expensive operations that require a response from every online node ASAP.  this is responsible for the highest churn.
- `avg_clock_pulses` averages the measured propagation delay over a rolling window of pulses to stabilize clock delta estimates, especially when `priority_update` imposes coarser update granularity.

Hard constraint: always ensure `rate_limits.priority_update < clock_pulse_interval/2` so system-table updates can arrive at least once per clock cycle.

## Trade-offs and symptoms

- `rate_limits.update`
  - Lower: fresher user data and statuses; potentially more churn. Safe to reduce within reason.
  - Higher: fewer updates; risk of stale statuses if it exceeds the fastest polling interval.
- `rate_limits.priority_update`
  - Lower: quicker leader elections; tighter clock deltas (better accuracy); more frequent system-table writes and significantly higher churn.
  - Higher: slower leader elections; clock table accuracy reduces to about ±`priority_update`; this is okay as long as a new leader cannot be elected in this error timeframe
- `clock_pulse_interval`
  - Lower: faster propagation-delay measurement and faster offline detection; higher wakeup/CPU overhead.
  - Higher: slower measurement and offline detection (offline threshold ≈ `2 * clock_pulse_interval + propagation_delay`). Ensure it remains greater than `priority_update*2`.
- `avg_clock_pulses`
  - Lower: more reactive propagation-delay averages but noisier clock deltas.
  - Higher: smoother and more stable deltas, but slower to reflect changes.

> Warning
> Changing cluster timing inconsistently across nodes can destabilize or crash the cluster. Apply changes to every node.

## Recommended ranges (starting points)

Use these as a starting point and adjust based on measurements:

- `rate_limits.update`: 3–10 seconds, but always ≤ min(`poll_rate`, monitor `interval`).
- `rate_limits.priority_update`: 0.25–2 seconds, and strictly < `clock_pulse_interval`.
- `clock_pulse_interval`: 5–20 seconds, chosen with your desired offline detection latency in mind.
- `avg_clock_pulses`: 20–60 pulses.

## Tuning playbooks

.
- Reduce CPU/IO overhead during
  - Raise `clock_pulse_interval` (e.g., 5 → 6) and/or raise `rate_limits.priority_update` (e.g., 1 → 2). note: be conservative on the `rate_limits.priority_update` increases
  - If decisions flap, consider raising `avg_clock_pulses`.
- Reduce false “offline” oscillations
  - Revisit per-node `poll_rate`/`retry` (in `node_config[]`) and per-monitor `interval`/`retry` to make status transitions less jumpy.

## Safety checklist

- Roll out to all nodes at once (or stage a temporary maintenance window). Mixed cluster timing is unsafe.
- Prefer testing on a staging or small-scope network first.
- Observe logs for timing messages and look for increased warning/error rates.
- Monitor CPU, memory, and network egress before/after changes.

## Rollout strategy (for Git-based configs)

1. Commit the change in the network config repo.
2. Confirm every node successfully pulls the new revision.
3. Watch telemetry and logs for at least a few clocks (minutes) before further changes.

## Verification

- Check that leader elections complete within the expected window after changes; if not, consider lowering `priority_update`.
- Inspect the clock table: clock delta error should be roughly within ±`priority_update` after smoothing.
- Look for lines like “Starting ... thread at interval” in logs matching your expected intervals.
- Ensure webhook notifications (if enabled) don’t surge or flap after changes.

