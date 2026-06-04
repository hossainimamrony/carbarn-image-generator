const form = document.querySelector("#settingsForm");
const logOutput = document.querySelector("#logOutput");
const runStatus = document.querySelector("#runStatus");
const modeLabel = document.querySelector("#modeLabel");
const outputLabel = document.querySelector("#outputLabel");
const startButton = document.querySelector("#startRun");
const stopButton = document.querySelector("#stopRun");
const saveButton = document.querySelector("#saveSettings");
const openOutputButton = document.querySelector("#openOutput");
const clearLogButton = document.querySelector("#clearLog");

let latestLogText = "";

function readForm() {
  const data = {};
  const fields = new FormData(form);

  for (const [key, value] of fields.entries()) {
    data[key] = value;
  }

  for (const checkbox of form.querySelectorAll('input[type="checkbox"]')) {
    data[checkbox.name] = checkbox.checked;
  }

  return data;
}

function writeForm(settings) {
  for (const [key, value] of Object.entries(settings)) {
    const input = form.elements[key];
    if (!input) {
      continue;
    }
    if (input.type === "checkbox") {
      input.checked = Boolean(value);
    } else {
      input.value = value ?? "";
    }
  }
  updateLabels();
}

function updateLabels() {
  const settings = readForm();
  if (settings.single_image) {
    modeLabel.textContent = "Single image";
  } else if (settings.skip_google_download) {
    modeLabel.textContent = "Existing folder";
  } else {
    modeLabel.textContent = "Google Photos batch";
  }
  outputLabel.textContent = settings.output_dir || "Not set";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}

async function loadDefaults() {
  const payload = await api("/api/defaults");
  writeForm(payload.settings || payload.defaults);
}

async function saveSettings() {
  await api("/api/settings", {
    method: "POST",
    body: JSON.stringify(readForm()),
  });
  appendClientLog("Settings saved.\n");
}

async function startRun() {
  latestLogText = "";
  logOutput.textContent = "";
  await api("/api/start", {
    method: "POST",
    body: JSON.stringify(readForm()),
  });
  await refreshStatus();
}

async function stopRun() {
  await api("/api/stop", { method: "POST", body: "{}" });
  await refreshStatus();
}

async function openOutput() {
  await saveSettings();
  await api("/api/open-output");
}

function appendClientLog(text) {
  latestLogText += text;
  logOutput.textContent = latestLogText;
  logOutput.scrollTop = logOutput.scrollHeight;
}

async function refreshStatus() {
  const payload = await api("/api/status");
  const logs = (payload.logs || []).join("");

  if (logs !== latestLogText) {
    latestLogText = logs;
    logOutput.textContent = latestLogText;
    logOutput.scrollTop = logOutput.scrollHeight;
  }

  startButton.disabled = payload.running;
  stopButton.disabled = !payload.running;
  runStatus.textContent = payload.running
    ? "Running"
    : payload.return_code === 0
      ? "Finished"
      : payload.return_code === null
        ? "Idle"
        : `Exited ${payload.return_code}`;
}

for (const input of form.elements) {
  input.addEventListener("input", updateLabels);
  input.addEventListener("change", updateLabels);
}

saveButton.addEventListener("click", () => {
  saveSettings().catch((error) => appendClientLog(`Save failed: ${error.message}\n`));
});

startButton.addEventListener("click", () => {
  startRun().catch((error) => appendClientLog(`Start failed: ${error.message}\n`));
});

stopButton.addEventListener("click", () => {
  stopRun().catch((error) => appendClientLog(`Stop failed: ${error.message}\n`));
});

openOutputButton.addEventListener("click", () => {
  openOutput().catch((error) => appendClientLog(`Open output failed: ${error.message}\n`));
});

clearLogButton.addEventListener("click", () => {
  latestLogText = "";
  logOutput.textContent = "";
});

loadDefaults().catch((error) => appendClientLog(`Load failed: ${error.message}\n`));
setInterval(() => {
  refreshStatus().catch(() => {});
}, 1000);
