import pytest

BODY = {
    "initial_power": 1.0,
    "reactivity": [
        {"time_s": 0, "value": 0, "unit": "pcm"},
        {"time_s": 5, "value": 50, "unit": "pcm"},
    ],
    "end_time": 60,
}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_presets_are_seeded_and_runnable(client):
    presets = client.get("/api/presets").json()
    assert [p["name"] for p in presets] == [
        "Rod withdrawal",
        "Prompt critical excursion",
        "SCRAM from full power",
    ]
    for preset in presets:
        r = client.post("/api/simulations", json=preset["parameters"])
        assert r.status_code == 201, preset["name"]


def test_create_and_retrieve_simulation(client):
    created = client.post("/api/simulations", json=BODY)
    assert created.status_code == 201
    run = created.json()
    assert len(run["times"]) == len(run["power"]) <= 600
    assert len(run["precursors"]) == 6
    assert run["times"][0] == 0 and run["times"][-1] == 60
    assert run["power"][0] == pytest.approx(1.0)
    assert run["summary"]["peak_power"] == pytest.approx(max(run["power"]))
    assert run["summary"]["final_power"] == pytest.approx(run["power"][-1])
    assert run["power"][-1] > 1.0  # positive reactivity: power rose

    fetched = client.get(f"/api/simulations/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == run


def test_unknown_run_is_404(client):
    assert client.get("/api/simulations/00000000-0000-0000-0000-000000000000").status_code == 404


def test_malformed_id_is_422(client):
    assert client.get("/api/simulations/not-a-uuid").status_code == 422


def test_dollars_and_pcm_are_equivalent(client):
    pcm = {**BODY, "reactivity": [{"time_s": 0, "value": 0}, {"time_s": 5, "value": 65}]}
    usd = {
        **BODY,
        "reactivity": [
            {"time_s": 0, "value": 0, "unit": "dollars"},
            {"time_s": 5, "value": 0.1, "unit": "dollars"},
        ],
    }
    a = client.post("/api/simulations", json=pcm).json()
    b = client.post("/api/simulations", json=usd).json()
    assert a["power"][-1] == pytest.approx(b["power"][-1], rel=1e-9)


def test_runaway_reports_early_termination(client):
    body = {**BODY, "reactivity": [{"time_s": 0, "value": 0}, {"time_s": 1, "value": 4000}]}
    run = client.post("/api/simulations", json=body).json()
    assert run["summary"]["terminated_early"] is True
    assert run["times"][-1] < 60


def with_(**changes):
    return {**BODY, **changes}


@pytest.mark.parametrize(
    "body",
    [
        with_(end_time=601),
        with_(end_time=0),
        with_(max_points=2001),
        with_(initial_power=0),
        with_(generation_time=1),
        with_(reactivity=[]),
        with_(reactivity=[{"time_s": 1, "value": 0}]),  # must start at 0
        with_(reactivity=[{"time_s": 0, "value": 0}, {"time_s": 0, "value": 1}]),
        with_(reactivity=[{"time_s": 0, "value": 0}, {"time_s": 60, "value": 1}]),  # not < end
        with_(reactivity=[{"time_s": 0, "value": 99999}]),
        with_(reactivity=[{"time_s": 0, "value": 1, "unit": "furlongs"}]),
        with_(reactivity=[{"time_s": 0, "value": 0}] * 21),
        {"end_time": 10},
    ],
)
def test_invalid_input_is_422(client, body):
    assert client.post("/api/simulations", json=body).status_code == 422
