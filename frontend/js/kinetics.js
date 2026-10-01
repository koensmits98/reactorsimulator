// Kinetics widget: collects parameters, calls the backend, plots the power.
// All physics happens on the server; this file only draws.

const BETA_PCM = 650; // 1 dollar, for the label next to the slider only
const SCRAM_PCM = -5000;

const $ = (id) => document.getElementById(id);
let plot = null;
let lastRun = null;
let presets = [];

function setStatus(text, isError = false) {
  $("status").textContent = text;
  $("status").className = isError ? "error" : "";
}

function updateRhoLabel() {
  const pcm = Number($("rho").value);
  $("rho-label").textContent = `${pcm} pcm (${(pcm / BETA_PCM).toFixed(2)} $)`;
}

function buildRequest(withScram) {
  const reactivity = [
    { time_s: 0, value: 0, unit: "pcm" },
    { time_s: Number($("t-step").value), value: Number($("rho").value), unit: "pcm" },
  ];
  if (withScram) {
    reactivity.push({ time_s: Number($("t-scram").value), value: SCRAM_PCM, unit: "pcm" });
  }
  return { initial_power: 1.0, reactivity, end_time: Number($("t-end").value) };
}

async function readError(response) {
  // FastAPI returns 422 with a list of {loc, msg}; show it in a readable form.
  try {
    const body = await response.json();
    if (Array.isArray(body.detail)) {
      return body.detail.map((d) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ");
    }
    return body.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

async function runSimulation(request) {
  setStatus("Calculating...");
  for (const button of document.querySelectorAll("button")) button.disabled = true;
  try {
    const response = await fetch("/api/simulations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      setStatus(await readError(response), true);
      return;
    }
    const run = await response.json();
    history.replaceState(null, "", `#${run.id}`);
    show(run);
  } catch {
    setStatus("Could not reach the server.", true);
  } finally {
    for (const button of document.querySelectorAll("button")) button.disabled = false;
  }
}

function show(run) {
  lastRun = run;
  const s = run.summary;
  let text = `Peak power ${s.peak_power.toPrecision(3)}, final power ${s.final_power.toPrecision(3)} (initial 1).`;
  if (s.terminated_early) {
    text += ` Stopped at t = ${run.times.at(-1).toPrecision(4)} s: power exceeded 10^9 times the start.`;
  }
  setStatus(text);
  draw();
}

function draw() {
  if (!lastRun) return;
  if (plot) plot.destroy();
  const log = $("log").checked;
  const width = $("plot").clientWidth;
  plot = new uPlot(
    {
      width,
      height: 320,
      scales: { x: { time: false }, y: { distr: log ? 3 : 1 } },
      axes: [{ label: "time (s)" }, { label: "relative power", size: 70 }],
      series: [{}, { label: "power", stroke: "#0b6bcb", width: 2 }],
    },
    [lastRun.times, lastRun.power],
    $("plot"),
  );
}

function applyPreset(preset) {
  $("preset-text").textContent = preset ? preset.description : "";
  if (!preset) return;
  // The controls cannot express every preset exactly, so run the preset itself.
  runSimulation(preset.parameters);
}

async function init() {
  updateRhoLabel();
  $("rho").addEventListener("input", updateRhoLabel);
  $("run").addEventListener("click", () => runSimulation(buildRequest(false)));
  $("run-scram").addEventListener("click", () => runSimulation(buildRequest(true)));
  $("log").addEventListener("change", draw);
  window.addEventListener("resize", draw);
  $("preset").addEventListener("change", () => {
    applyPreset(presets.find((p) => String(p.id) === $("preset").value));
  });

  try {
    presets = await (await fetch("/api/presets")).json();
    for (const p of presets) {
      $("preset").add(new Option(p.name, p.id));
    }
  } catch {
    setStatus("Could not load the scenarios.", true);
  }

  // A shared link looks like kinetics.html#<run id>.
  const id = location.hash.slice(1);
  if (id) {
    const response = await fetch(`/api/simulations/${encodeURIComponent(id)}`);
    if (response.ok) show(await response.json());
    else setStatus("That shared run was not found.", true);
  } else {
    runSimulation(buildRequest(false));
  }
}

init();
