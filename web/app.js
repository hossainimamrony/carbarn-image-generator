const form = document.querySelector("#settingsForm");
const logOutput = document.querySelector("#logOutput");
const runStatus = document.querySelector("#runStatus");
const modeLabel = document.querySelector("#modeLabel");
const outputLabel = document.querySelector("#outputLabel");
const startButtons = [
  document.querySelector("#startBgRun"),
  document.querySelector("#startPerfectRun"),
  document.querySelector("#startPipelineRun"),
];
const stopButton = document.querySelector("#stopRun");
const saveButton = document.querySelector("#saveSettings");
const openCanvaOutputButton = document.querySelector("#openCanvaOutput");
const openGeminiOutputButton = document.querySelector("#openGeminiOutput");
const pauseFlowButton = document.querySelector("#pauseFlow");
const resumeFlowButton = document.querySelector("#resumeFlow");
const clearLogButton = document.querySelector("#clearLog");
const flowPromptInput = form.elements.flow_prompt;

let latestLogText = "";
let promptSaveTimer = null;

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
  } else if (settings.download_google_photos) {
    modeLabel.textContent = "Google Photos batch";
  } else {
    modeLabel.textContent = "Existing folder";
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

async function saveFlowPrompt() {
  await api("/api/flow-prompt", {
    method: "POST",
    body: JSON.stringify({ flow_prompt: flowPromptInput.value }),
  });
}

function queuePromptSave() {
  window.clearTimeout(promptSaveTimer);
  promptSaveTimer = window.setTimeout(() => {
    saveFlowPrompt().catch((error) =>
      appendClientLog(`Prompt save failed: ${error.message}\n`),
    );
  }, 700);
}

async function startRun(path) {
  await saveFlowPrompt();
  latestLogText = "";
  logOutput.textContent = "";
  await api(path, {
    method: "POST",
    body: JSON.stringify(readForm()),
  });
  await refreshStatus();
}

async function stopRun() {
  await api("/api/stop", { method: "POST", body: "{}" });
  await refreshStatus();
}

async function pauseFlow() {
  await saveFlowPrompt();
  await api("/api/flow-pause", { method: "POST", body: "{}" });
  await refreshStatus();
}

async function resumeFlow() {
  await saveFlowPrompt();
  await api("/api/flow-resume", { method: "POST", body: "{}" });
  await refreshStatus();
}

async function openOutput(target) {
  await saveSettings();
  const suffix = target === "perfect" ? "?target=perfect" : "?target=canva";
  await api(`/api/open-output${suffix}`);
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

  for (const button of startButtons) {
    button.disabled = payload.running;
  }
  stopButton.disabled = !payload.running;
  pauseFlowButton.disabled = !payload.running || payload.flow_paused;
  resumeFlowButton.disabled = !payload.running || !payload.flow_paused;
  runStatus.textContent = payload.running
    ? payload.flow_paused
      ? "Paused"
      : "Running"
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

document.querySelector("#startBgRun").addEventListener("click", () => {
  startRun("/api/start-bg").catch((error) =>
    appendClientLog(`Canva failed to start: ${error.message}\n`),
  );
});

document.querySelector("#startPerfectRun").addEventListener("click", () => {
  startRun("/api/start-perfect").catch((error) =>
    appendClientLog(`Flow failed to start: ${error.message}\n`),
  );
});

document.querySelector("#startPipelineRun").addEventListener("click", () => {
  startRun("/api/start-pipeline").catch((error) =>
    appendClientLog(`Pipeline failed to start: ${error.message}\n`),
  );
});

pauseFlowButton.addEventListener("click", () => {
  pauseFlow().catch((error) => appendClientLog(`Pause failed: ${error.message}\n`));
});

resumeFlowButton.addEventListener("click", () => {
  resumeFlow().catch((error) => appendClientLog(`Resume failed: ${error.message}\n`));
});

stopButton.addEventListener("click", () => {
  stopRun().catch((error) => appendClientLog(`Stop failed: ${error.message}\n`));
});

openCanvaOutputButton.addEventListener("click", () => {
  openOutput("canva").catch((error) =>
    appendClientLog(`Open Canva output failed: ${error.message}\n`),
  );
});

openGeminiOutputButton.addEventListener("click", () => {
  openOutput("perfect").catch((error) =>
    appendClientLog(`Open Gemini output failed: ${error.message}\n`),
  );
});

clearLogButton.addEventListener("click", () => {
  latestLogText = "";
  logOutput.textContent = "";
});

flowPromptInput.addEventListener("input", queuePromptSave);

loadDefaults().catch((error) => appendClientLog(`Load failed: ${error.message}\n`));
setInterval(() => {
  refreshStatus().catch(() => {});
}, 1000);
