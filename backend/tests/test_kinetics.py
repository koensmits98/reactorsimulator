"""Physics tests: each one checks a known analytical result."""

import numpy as np
import pytest

from app.physics.kinetics import (
    BETA_TOTAL,
    DECAY_CONSTANTS,
    KineticsParams,
    dollars_to_absolute,
    inhour_period_root,
    pcm_to_absolute,
    simulate,
)


def test_group_fractions_sum_to_one():
    from app.physics.kinetics import GROUP_FRACTIONS

    assert GROUP_FRACTIONS.sum() == pytest.approx(1.0)


def test_unit_conversions():
    assert pcm_to_absolute(100) == pytest.approx(1e-3)
    assert dollars_to_absolute(1.0) == pytest.approx(BETA_TOTAL)


def test_critical_reactor_stays_constant():
    res = simulate(power0=3.0, steps=[(0, 0.0)], t_end=100)
    assert res.power == pytest.approx(3.0, rel=1e-6)


def test_precursors_start_in_equilibrium():
    p = KineticsParams()
    res = simulate(power0=1.0, steps=[(0, 0.0)], t_end=10)
    expected = p.beta_groups / (p.generation_time * p.decay_constants)
    assert res.precursors[:, 0] == pytest.approx(expected)


@pytest.mark.parametrize(
    "rho, t_end, window",
    [
        (pcm_to_absolute(50), 400, (200, 400)),
        (pcm_to_absolute(-50), 1000, (600, 1000)),
        (0.003, 60, (40, 55)),
    ],
)
def test_stable_period_matches_inhour_equation(rho, t_end, window):
    omega = inhour_period_root(rho)
    t = np.linspace(0, t_end, 40 * t_end + 1)
    res = simulate(1.0, [(0, rho)], t_end=t_end, t_eval=t)
    # Fit the growth rate late in the run, after the faster modes have died out.
    late = (t > window[0]) & (t < window[1])
    fitted = np.polyfit(t[late], np.log(res.power[late]), 1)[0]
    assert fitted == pytest.approx(omega, rel=1e-3)


def test_inhour_known_value():
    # For small positive rho the stable period is close to (beta - rho) / (lambda_eff * rho).
    # With +100 pcm in a U-235 reactor the period is on the order of 40-60 s.
    period = 1 / inhour_period_root(pcm_to_absolute(100))
    assert 30 < period < 80


@pytest.mark.parametrize("rho_over_beta", [0.1, 0.3, 0.5])
def test_prompt_jump(rho_over_beta):
    rho = rho_over_beta * BETA_TOTAL
    # Prompt time constant is Lambda / (beta - rho); after 3 time constants the jump has
    # happened but the delayed neutrons have barely started to add power.
    tau = 1e-4 / (BETA_TOTAL - rho)
    t = np.array([0.0, 3 * tau])
    res = simulate(1.0, [(0, rho)], t_end=1.0, t_eval=t)
    jump = res.power[1] / res.power[0]
    assert jump == pytest.approx(BETA_TOTAL / (BETA_TOTAL - rho), rel=0.03)


def test_subcritical_with_source_steady_state():
    rho = pcm_to_absolute(-1000)
    S = 5.0
    params = KineticsParams(source=S)
    p_ss = -S * params.generation_time / rho
    # Starting exactly at the steady state, nothing moves.
    res = simulate(p_ss, [(0, rho)], t_end=200, params=params)
    assert res.power == pytest.approx(p_ss, rel=1e-6)
    # Starting elsewhere, the power converges to it (slowly: the delayed groups set the pace).
    res = simulate(0.5 * p_ss, [(0, rho)], t_end=600, params=params)
    assert res.power[-1] == pytest.approx(p_ss, rel=0.02)


def test_scram_prompt_drop_then_longest_group_decay():
    rho = pcm_to_absolute(-5000)
    t = np.concatenate(([0.0, 0.01, 0.1, 1.0], np.linspace(500, 900, 401)))
    res = simulate(1.0, [(0, rho)], t_end=900, t_eval=t)
    # Prompt drop: P1/P0 close to beta / (beta - rho).
    assert res.power[3] / 1.0 < 0.2
    assert res.power[3] == pytest.approx(BETA_TOTAL / (BETA_TOTAL - rho), rel=0.25)
    # Long-time decay constant approaches the longest-lived group, period about 80 s.
    late = t >= 500
    rate = np.polyfit(t[late], np.log(res.power[late]), 1)[0]
    assert rate == pytest.approx(-DECAY_CONSTANTS[0], rel=0.05)
    assert 1 / -rate == pytest.approx(80, rel=0.1)


def test_piecewise_history_is_continuous_across_a_step():
    steps = [(0, 0.0), (10, pcm_to_absolute(50)), (20, 0.0)]
    t = np.array([0.0, 9.999999, 10.0, 10.000001, 20.0])
    res = simulate(1.0, steps, t_end=30, t_eval=t)
    assert res.power[1] == pytest.approx(1.0, rel=1e-5)
    # Power is continuous across a reactivity change (only its slope jumps).
    assert res.power[2] == pytest.approx(res.power[1], rel=1e-5)
    assert np.all(np.diff(res.times) > 0)


def test_runaway_is_stopped_instead_of_overflowing():
    res = simulate(1.0, [(0, 0.05)], t_end=600)  # far above prompt critical
    assert res.terminated_early
    assert res.times[-1] < 600
    assert np.all(np.isfinite(res.power))


@pytest.mark.parametrize(
    "steps, t_end",
    [([], 10), ([(1, 0.0)], 10), ([(0, 0.0), (5, 0.0), (5, 0.0)], 10), ([(0, 0.0)], 0)],
)
def test_invalid_histories_are_rejected(steps, t_end):
    with pytest.raises(ValueError):
        simulate(1.0, steps, t_end=t_end)
