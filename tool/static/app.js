const form = document.querySelector("#audit-form");
const runButton = document.querySelector("#run-button");
const runLabel = document.querySelector("#run-label");
const emptyState = document.querySelector("#empty-state");
const loadingState = document.querySelector("#loading-state");
const loadingTitle = document.querySelector("#loading-title");
const loadingStep = document.querySelector("#loading-step");
const resultState = document.querySelector("#result-state");
const errorState = document.querySelector("#error-state");
const errorMessage = document.querySelector("#error-message");
const openReport = document.querySelector("#open-report");
const downloadReport = document.querySelector("#download-report");
const openSpecialist = document.querySelector("#open-specialist");
const newAudit = document.querySelector("#new-audit");

const loadingMessages = [
  ["Collecting evidence", "Checking public routes, metadata, offers, forms, schema, and brand cues."],
  ["Classifying the bottleneck", "Scoring only observed categories and preserving missing evidence."],
  ["Building the report", "Applying detected brand cues and assembling the seven-day plan."],
];

let loadingTimer = null;

function selectedValue(name) {
  return form.querySelector(`input[name="${name}"]:checked`)?.value;
}

function setState(state) {
  emptyState.hidden = state !== "empty";
  loadingState.setAttribute("aria-hidden", state === "loading" ? "false" : "true");
  resultState.setAttribute("aria-hidden", state === "result" ? "false" : "true");
  errorState.setAttribute("aria-hidden", state === "error" ? "false" : "true");
}

function setButtonState(state, label) {
  runButton.dataset.state = state;
  runButton.disabled = state === "loading";
  runLabel.textContent = label;
}

function beginLoadingMessages() {
  let index = 0;
  loadingTitle.textContent = loadingMessages[index][0];
  loadingStep.textContent = loadingMessages[index][1];
  loadingTimer = window.setInterval(() => {
    index = (index + 1) % loadingMessages.length;
    loadingTitle.textContent = loadingMessages[index][0];
    loadingStep.textContent = loadingMessages[index][1];
  }, 2600);
}

function stopLoadingMessages() {
  if (loadingTimer) {
    window.clearInterval(loadingTimer);
    loadingTimer = null;
  }
}

function updateRunLabel() {
  const mode = selectedValue("mode");
  const labels = {
    conversion: "Run Conversion Audit",
    visibility: "Run Visibility Audit",
    full: "Run Full Audit",
  };
  if (!runButton.disabled) {
    runLabel.textContent = labels[mode] || labels.full;
  }
}

form.addEventListener("change", updateRunLabel);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    url: form.elements.url.value.trim(),
    mode: selectedValue("mode"),
    intent: form.elements.intent.value.trim(),
  };

  setState("loading");
  setButtonState("loading", "Running audit");
  beginLoadingMessages();

  try {
    const response = await fetch("/api/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The audit failed.");
    }

    openReport.href = data.report_url;
    downloadReport.href = data.download_url;
    openSpecialist.href = data.specialist_url;
    if (data.index_url) {
      var indexLink = document.getElementById("open-index") || (function() {
        var a = document.createElement("a");
        a.id = "open-index";
        a.className = "action-button action-button--primary";
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = "Open overview";
        document.querySelector(".result-actions").insertBefore(a, document.querySelector(".result-actions").firstChild);
        return a;
      })();
      indexLink.href = data.index_url;
    }
    document.querySelector("#result-title").textContent = `${data.brand} audit complete`;
    document.querySelector("#result-subtitle").textContent = `${data.mode} audit · ${data.url}`;
    document.querySelector("#conversion-score").textContent = payload.mode === "visibility" ? "N/A" : `${data.conversion_score}/100`;
    document.querySelector("#visibility-score").textContent = payload.mode === "conversion" ? "N/A" : `${data.visibility_score}/100`;
    document.querySelector("#root-layer").textContent = payload.mode === "visibility" ? "N/A" : data.root_layer;
    document.querySelector("#priority-count").textContent = data.priority_count;
    setState("result");
    setButtonState("success", "Audit complete");

    const history = JSON.parse(window.localStorage.getItem("websiteAuditHistory") || "[]");
    history.unshift({
      createdAt: new Date().toISOString(),
      brand: data.brand,
      url: data.url,
      mode: data.mode,
      reportUrl: data.report_url,
    });
    window.localStorage.setItem("websiteAuditHistory", JSON.stringify(history.slice(0, 10)));

  } catch (error) {
    errorMessage.textContent = error.message;
    setState("error");
    setButtonState("error", "Try again");
  } finally {
    stopLoadingMessages();
    if (runButton.dataset.state === "loading") {
      setButtonState("default", "Run audit");
    }
  }
});

newAudit.addEventListener("click", () => {
  setState("empty");
  setButtonState("default", "");
  updateRunLabel();
  form.elements.url.focus();
});

updateRunLabel();
