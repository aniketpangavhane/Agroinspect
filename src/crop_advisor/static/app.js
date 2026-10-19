const form = document.querySelector("#recommendation-form");
const conditions = document.querySelector("#conditions");
const formStatus = document.querySelector("#form-status");
const submitButton = document.querySelector("#submit-button");
const resultCard = document.querySelector("#result-card");

function setStatus(message, state = "info") {
  formStatus.textContent = message;
  formStatus.dataset.state = state;
}

function appendOptions(select, values, placeholder) {
  select.replaceChildren(new Option(placeholder, ""));
  for (const value of values) {
    select.add(new Option(value, value));
  }
}

async function loadOptions() {
  try {
    const response = await fetch("/v1/options", {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(response.status === 503
        ? "The model is not ready yet. Train the prototype model, then reload this page."
        : "Could not load the supported input choices. Reload the page to try again.");
    }
    const options = await response.json();
    appendOptions(document.querySelector("#district"), options.districts, "Choose a supported district");
    appendOptions(document.querySelector("#soil_color"), options.soil_colors, "Choose a soil colour");
    conditions.disabled = false;
    setStatus("Supported choices loaded. Fields marked required must be completed.");
  } catch (error) {
    setStatus(error.message || "Could not load the supported input choices.", "error");
  }
}

function renderResult(result) {
  document.querySelector("#best-crop").textContent = result.best_suitable_crop;
  const top = result.recommendations[0];
  document.querySelector("#top-score").textContent = top
    ? `Top model score: ${(top.probability * 100).toFixed(1)}%`
    : "";

  const alternatives = document.querySelector("#alternatives");
  alternatives.replaceChildren();
  for (const candidate of result.recommendations.slice(1)) {
    const item = document.createElement("li");
    item.append(document.createTextNode(candidate.crop + " "));
    const score = document.createElement("span");
    score.className = "alternative-score";
    score.textContent = `(${(candidate.probability * 100).toFixed(1)}% model score)`;
    item.append(score);
    alternatives.append(item);
  }

  const warnings = document.querySelector("#warnings");
  warnings.replaceChildren();
  for (const message of result.warnings) {
    const item = document.createElement("li");
    item.textContent = message;
    warnings.append(item);
  }
  document.querySelector("#warnings-wrap").hidden = result.warnings.length === 0;
  resultCard.hidden = false;
  document.querySelector("#result-title").focus({ preventScroll: true });
  resultCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const formValues = Object.fromEntries(new FormData(form).entries());
  const numericFields = ["nitrogen", "phosphorus", "potassium", "ph", "rainfall", "temperature"];
  for (const field of numericFields) formValues[field] = Number(formValues[field]);
  formValues.top_k = 3;

  submitButton.disabled = true;
  setStatus("Getting the prototype ranking…");
  try {
    const response = await fetch("/v1/recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(formValues),
      cache: "no-store",
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = Array.isArray(result.detail)
        ? result.detail.map((item) => item.msg).join(" ")
        : result.detail;
      throw new Error(detail || "The request could not be completed. Check your values and try again.");
    }
    renderResult(result);
    setStatus("Ranking received. Read the result with the limitations in mind.");
  } catch (error) {
    setStatus(error.message || "The recommendation request failed. Please try again.", "error");
  } finally {
    submitButton.disabled = false;
  }
});

loadOptions();
