"""Point reactor kinetics with six delayed neutron groups.

    dP/dt   = (rho - beta) / Lambda * P + sum_i lambda_i * C_i + S
    dC_i/dt = beta_i / Lambda * P - lambda_i * C_i,   i = 1..6

State vector: y = [P, C_1, ..., C_6]. Power P is in arbitrary (relative) units.
This module has no web code, so it can be tested and reused on its own.

Delayed neutron data: Keepin, Wimett and Zeigler (1957), six groups, thermal fission
of U-235 (also tabulated in Lamarsh, "Introduction to Nuclear Reactor Theory", and
Duderstadt and Hamilton, "Nuclear Reactor Analysis"). Verify against your preferred
reference before quoting numbers in published material.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

# Relative group fractions beta_i / beta and decay constants [1/s].
GROUP_FRACTIONS = np.array([0.033, 0.219, 0.196, 0.395, 0.115, 0.042])
DECAY_CONSTANTS = np.array([0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01])
BETA_TOTAL = 0.0065
BETA_GROUPS = BETA_TOTAL * GROUP_FRACTIONS  # note: fractions sum to 1.0

DEFAULT_LAMBDA = 1e-4  # prompt generation time [s], typical LWR order of magnitude

# Stop integrating if power exceeds this multiple of the initial power. A supercritical
# reactor grows exponentially and would otherwise overflow the solver on long runs.
MAX_POWER_FACTOR = 1e9


@dataclass(frozen=True)
class KineticsParams:
    beta_groups: np.ndarray = field(default_factory=lambda: BETA_GROUPS)
    decay_constants: np.ndarray = field(default_factory=lambda: DECAY_CONSTANTS)
    generation_time: float = DEFAULT_LAMBDA  # Lambda [s]
    source: float = 0.0  # external source S, in the same units as dP/dt

    @property
    def beta(self) -> float:
        return float(self.beta_groups.sum())


@dataclass
class KineticsResult:
    times: np.ndarray  # shape (n,)
    power: np.ndarray  # shape (n,)
    precursors: np.ndarray  # shape (6, n)
    terminated_early: bool  # True if the power limit was hit before t_end


def pcm_to_absolute(rho_pcm: float) -> float:
    """1 pcm = 1e-5 of delta-k/k."""
    return rho_pcm * 1e-5


def dollars_to_absolute(rho_dollars: float, beta: float = BETA_TOTAL) -> float:
    return rho_dollars * beta


def equilibrium_state(power: float, params: KineticsParams) -> np.ndarray:
    """Precursors in equilibrium with a given power: C_i = beta_i P / (Lambda lambda_i)."""
    c = params.beta_groups * power / (params.generation_time * params.decay_constants)
    return np.concatenate(([power], c))


def _rhs(_t, y, rho, p: KineticsParams):
    power, c = y[0], y[1:]
    dp = (rho - p.beta) / p.generation_time * power + p.decay_constants @ c + p.source
    dc = p.beta_groups / p.generation_time * power - p.decay_constants * c
    return np.concatenate(([dp], dc))


def _jacobian(_t, _y, rho, p: KineticsParams):
    # The system is linear in y, so the Jacobian is constant within a segment.
    n = len(p.decay_constants)
    jac = np.zeros((n + 1, n + 1))
    jac[0, 0] = (rho - p.beta) / p.generation_time
    jac[0, 1:] = p.decay_constants
    jac[1:, 0] = p.beta_groups / p.generation_time
    jac[1:, 1:] = -np.diag(p.decay_constants)
    return jac


def advance(
    y0: np.ndarray,
    rho: float,
    t0: float,
    t1: float,
    params: KineticsParams,
    t_eval: np.ndarray | None = None,
    power_limit: float = np.inf,
):
    """Integrate one segment of constant reactivity from t0 to t1 with the implicit Radau method.

    The equations are stiff (the prompt time scale Lambda/beta is ~1e-2 s, the longest
    delayed group is ~80 s), so an explicit method would need tiny steps.
    """

    def too_much_power(_t, y, *_args):
        return power_limit - y[0]

    too_much_power.terminal = True

    return solve_ivp(
        _rhs,
        (t0, t1),
        y0,
        method="Radau",
        jac=_jacobian,
        args=(rho, params),
        t_eval=t_eval,
        events=too_much_power,
        rtol=1e-8,
        atol=1e-12,
    )


def sample_times(t_end: float, step_times: list[float], max_points: int) -> np.ndarray:
    """Output times: an even grid plus a dense (logarithmic) burst right after each reactivity step.

    The prompt jump happens within milliseconds, which an even grid over minutes would miss.
    The result never has more than max_points entries.
    """
    burst = np.geomspace(1e-3, 1.0, 12)
    n_extra = len(step_times) * len(burst)
    grid = np.linspace(0, t_end, max(max_points - n_extra, 2))
    extra = [t + burst for t in step_times if t > 0]
    return np.unique(np.concatenate([grid, *extra]))


def simulate(
    power0: float,
    steps: list[tuple[float, float]],
    t_end: float,
    params: KineticsParams | None = None,
    t_eval: np.ndarray | None = None,
) -> KineticsResult:
    """Run the reactor from equilibrium at power0 through a piecewise constant reactivity history.

    steps: list of (time [s], absolute reactivity), sorted by time, first time must be 0.
    t_eval: times at which to return the solution (default: 1000 evenly spaced points).

    Each segment between reactivity changes is integrated separately, so the solver
    never sees a discontinuity in the right-hand side.
    """
    params = params or KineticsParams()
    if not steps or steps[0][0] != 0:
        raise ValueError("reactivity history must start at t = 0")
    if any(b[0] <= a[0] for a, b in zip(steps, steps[1:], strict=False)):
        raise ValueError("step times must be strictly increasing")
    if steps[-1][0] >= t_end:
        raise ValueError("all steps must happen before t_end")

    if t_eval is None:
        t_eval = np.linspace(0, t_end, 1000)
    # Always evaluate at t = 0, at every reactivity change and at t_end, so each segment
    # ends on an exact solution point that the next segment can start from.
    seg_starts = [t for t, _ in steps]
    seg_ends = seg_starts[1:] + [t_end]
    t_eval = np.unique(np.concatenate((t_eval, [0.0], seg_starts, [t_end])))
    t_eval = t_eval[(t_eval >= 0) & (t_eval <= t_end)]

    y = equilibrium_state(power0, params)
    limit = power0 * MAX_POWER_FACTOR

    times, states = [], []
    terminated = False
    for (t0, rho), t1 in zip(steps, seg_ends, strict=True):
        # The segment's first point (t0) was already returned by the previous segment.
        lower = (t_eval >= t0) if t0 == 0 else (t_eval > t0)
        sol = advance(y, rho, t0, t1, params, t_eval[lower & (t_eval <= t1)], limit)
        if not sol.success:
            raise RuntimeError(f"ODE solver failed: {sol.message}")
        times.append(sol.t)
        states.append(sol.y)
        if sol.status == 1:  # the power limit event fired
            terminated = True
            break
        y = sol.y[:, -1]

    t_all = np.concatenate(times)
    y_all = np.concatenate(states, axis=1)
    return KineticsResult(t_all, y_all[0], y_all[1:], terminated)


def inhour_period_root(rho: float, params: KineticsParams | None = None) -> float:
    """Asymptotic growth rate omega [1/s] (the dominant root) of the inhour equation:

        rho = Lambda * omega + sum_i beta_i * omega / (omega + lambda_i)

    For rho > 0 the dominant root is positive; for rho < 0 it lies between -lambda_1 and 0
    for small |rho|, and approaches -lambda_1 for a deeply subcritical reactor.
    """
    p = params or KineticsParams()
    lam = p.decay_constants

    def f(omega):
        return p.generation_time * omega + np.sum(p.beta_groups * omega / (omega + lam)) - rho

    if rho == 0:
        return 0.0
    if rho > 0:
        # f(0) = -rho < 0 and f grows without bound, so a root exists on (0, hi).
        hi = 1.0
        while f(hi) < 0:
            hi *= 2
        return brentq(f, 0.0, hi, xtol=1e-14)
    # rho < 0: the dominant (least negative) root lies between -lambda_min and 0.
    lo = -lam.min() * (1 - 1e-12)
    return brentq(f, lo, 0.0, xtol=1e-14)
