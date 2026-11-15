(() => {
  const $ = (id) => document.getElementById(id);
  let experiments = [];
  let activeExperiment = null;
  let activeAnalysis = null;
  let activeRecordCounts = null;
  let growthChart = null;

  async function request(url, options = {}) {
    const response = await fetch(earthSignalApiUrl(url), {
      cache: "no-store",
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {})
      }
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status}).`);
    return payload;
  }

  function showStatus(id, message, isError = false) {
    const element = $(id);
    element.textContent = message;
    element.classList.toggle("error", isError);
  }

  function numberValue(id) {
    const value = $(id).value.trim();
    if (!value) return null;
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error(`${$(id).labels[0].textContent} must be a number.`);
    return number;
  }

  function addCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
    row.append(cell);
  }

  function renderTable(containerId, headers, rows, emptyMessage) {
    const container = $(containerId);
    container.replaceChildren();
    if (!rows.length) {
      container.textContent = emptyMessage;
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "table-scroll";
    const table = document.createElement("table");
    const head = document.createElement("thead");
    const headerRow = document.createElement("tr");
    headers.forEach(header => {
      const cell = document.createElement("th");
      cell.textContent = header;
      headerRow.append(cell);
    });
    head.append(headerRow);
    const body = document.createElement("tbody");
    rows.forEach(values => {
      const row = document.createElement("tr");
      values.forEach(value => addCell(row, value));
      body.append(row);
    });
    table.append(head, body);
    wrapper.append(table);
    container.append(wrapper);
  }

  function renderExperimentSummary(experiment) {
    const summary = $("experiment-summary");
    summary.replaceChildren();
    const title = document.createElement("h3");
    title.textContent = experiment.name;
    const details = document.createElement("p");
    details.textContent =
      `${experiment.crop}${experiment.variety ? ` · ${experiment.variety}` : ""} · ${experiment.location} · ` +
      `${experiment.start_date} to ${experiment.end_date || "in progress"}`;
    const objective = document.createElement("p");
    objective.textContent = experiment.research_objective;
    const groups = document.createElement("div");
    groups.className = "experiment-group-chips";
    experiment.groups.forEach(group => {
      const chip = document.createElement("span");
      chip.className = "pill";
      chip.textContent = `${group.name}: ${group.treatment}`;
      groups.append(chip);
    });
    summary.append(title, details, objective, groups);
  }

  function fillGroupOptions(experiment) {
    ["reading-group", "observation-group", "harvest-group"].forEach(id => {
      const select = $(id);
      select.replaceChildren();
      experiment.groups.forEach(group => {
        const option = document.createElement("option");
        option.value = String(group.id);
        option.textContent = group.name;
        select.append(option);
      });
    });
    const habitatGroup = $("habitat-group");
    habitatGroup.replaceChildren();
    const sharedOption = document.createElement("option");
    sharedOption.value = "";
    sharedOption.textContent = "Not assigned";
    habitatGroup.append(sharedOption);
    experiment.groups.forEach(group => {
      const option = document.createElement("option");
      option.value = String(group.id);
      option.textContent = group.name;
      habitatGroup.append(option);
    });
  }

  function renderAnalysis(analysis) {
    const target = $("experiment-analysis-results");
    target.replaceChildren();
    if (!analysis.groups.length) {
      target.textContent = "Create a comparison group to begin recording results.";
      return;
    }
    analysis.groups.forEach(group => {
      const card = document.createElement("article");
      card.className = "experiment-result-card";
      const heading = document.createElement("h4");
      heading.textContent = group.group_name;
      const treatment = document.createElement("p");
      treatment.textContent = group.treatment;
      const metrics = group.measurements;
      const growth = group.growth;
      const list = document.createElement("dl");
      [
        ["Water recorded", metrics.water_added_l === null ? "Not recorded" : `${metrics.water_added_l} L`],
        ["Fresh harvest", metrics.fresh_mass_g === null ? "Not recorded" : `${metrics.fresh_mass_g} g`],
        ["Dry harvest", metrics.dry_mass_g === null ? "Not measured" : `${metrics.dry_mass_g} g`],
        ["Fresh yield per plant", metrics.fresh_yield_g_per_plant === null ? "Not available" : `${metrics.fresh_yield_g_per_plant} g/plant`],
        ["Fresh-mass WUE", metrics.fresh_water_use_efficiency_g_per_l === null ? "Not available" : `${metrics.fresh_water_use_efficiency_g_per_l} g/L`],
        ["Dry-mass WUE", metrics.dry_water_use_efficiency_g_per_l === null ? "Not available" : `${metrics.dry_water_use_efficiency_g_per_l} g/L`],
        ["Mean height change", growth.mean_height_change_cm_per_day === null ? "Need repeat measurements" : `${growth.mean_height_change_cm_per_day} cm/day`]
      ].forEach(([label, value]) => {
        const term = document.createElement("dt");
        const description = document.createElement("dd");
        term.textContent = label;
        description.textContent = value;
        list.append(term, description);
      });
      card.append(heading, treatment, list);
      target.append(card);
    });
  }

  function renderSpaceCropComparison() {
    const body = $("space-review-comparison");
    body.replaceChildren();
    if (!activeExperiment || !activeAnalysis) {
      showStatus(
        "space-review-status",
        "Select an Earth experiment above to view its recorded values beside the NASA research context."
      );
      return;
    }

    const groupValues = (readValue, unit, unavailable) => activeAnalysis.groups
      .map(group => {
        const value = readValue(group);
        return `${group.group_name}: ${value === null || value === undefined ? unavailable : `${value} ${unit}`}`;
      })
      .join("; ");
    const rows = [
      ["Crop", "‘Outredgeous’ red romaine lettuce.", `${activeExperiment.crop}${activeExperiment.variety ? ` · ${activeExperiment.variety}` : ""}`],
      ["Growing location", "Veggie plant-growth system aboard the International Space Station.", activeExperiment.location],
      ["Growth period", "33 days for the VEG-01 lettuce test crop.", `${activeExperiment.start_date} to ${activeExperiment.end_date || "in progress"}`],
      ["Water", "NASA's summary reports insufficient and excess watering as challenges; a comparable total is not stated.", groupValues(group => group.measurements.water_added_l, "L", "not recorded")],
      ["Plant-height change", "Not reported in the cited NASA summary.", groupValues(group => group.growth.mean_height_change_cm_per_day, "cm/day", "not available")],
      ["Harvest mass", "Not reported in the cited NASA summary; returned samples were analyzed.", groupValues(group => group.measurements.fresh_mass_g, "g fresh mass", "not recorded")]
    ];

    rows.forEach(values => {
      const row = document.createElement("tr");
      values.forEach(value => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      body.append(row);
    });
    showStatus(
      "space-review-status",
      `Showing NASA's published context beside measurements recorded for “${activeExperiment.name}”. The studies use different environments and methods.`
    );
  }

  function renderGrowthChart(observations) {
    const status = $("experiment-growth-status");
    status.classList.remove("error");
    const points = observations.filter(row => row.height_cm !== null && row.height_cm !== undefined);
    if (growthChart) {
      growthChart.destroy();
      growthChart = null;
    }
    if (!points.length) {
      status.textContent = "No plant-height observations recorded yet.";
      return;
    }
    if (typeof Chart === "undefined") {
      status.textContent = "The chart library is unavailable; the recorded height table is still available.";
      status.classList.add("error");
      return;
    }

    const dailyByGroup = new Map();
    const dates = new Set();
    points.forEach(point => {
      const day = point.observed_at.slice(0, 10);
      dates.add(day);
      if (!dailyByGroup.has(point.group_id)) dailyByGroup.set(point.group_id, new Map());
      const dayValues = dailyByGroup.get(point.group_id);
      if (!dayValues.has(day)) dayValues.set(day, []);
      dayValues.get(day).push(Number(point.height_cm));
    });
    const labels = Array.from(dates).sort();
    const palette = ["#24765b", "#c17a32", "#4d70a6", "#89568e", "#4c8c91"];
    const datasets = activeExperiment.groups.map((group, index) => {
      const groupValues = dailyByGroup.get(group.id) || new Map();
      return {
        label: group.name,
        data: labels.map(day => {
          const values = groupValues.get(day);
          return values ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
        }),
        borderColor: palette[index % palette.length],
        backgroundColor: palette[index % palette.length],
        pointRadius: 3,
        tension: 0.15,
        spanGaps: false
      };
    }).filter(dataset => dataset.data.some(value => value !== null));
    growthChart = new Chart($("experiment-growth-chart"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        interaction: { intersect: false, mode: "index" },
        plugins: { tooltip: { callbacks: { label: context => `${context.dataset.label}: ${context.parsed.y.toFixed(2)} cm` } } },
        scales: {
          x: { title: { display: true, text: "Observation date (UTC)" } },
          y: { title: { display: true, text: "Mean recorded height (cm)" }, beginAtZero: true }
        }
      }
    });
    status.classList.remove("error");
    status.textContent = `Showing daily mean heights from ${points.length} recorded plant observation${points.length === 1 ? "" : "s"}.`;
  }

  async function loadExperimentRecords(experimentId) {
    const [readings, observations, harvests, analysis] = await Promise.all([
      request(`/api/experiments/${experimentId}/readings?limit=20`),
      request(`/api/experiments/${experimentId}/observations?limit=20`),
      request(`/api/experiments/${experimentId}/harvests?limit=20`),
      request(`/api/analysis/experiments/${experimentId}`)
    ]);
    activeAnalysis = analysis;
    activeRecordCounts = {
      readings: readings.readings.length,
      observations: observations.observations.length,
      harvests: harvests.harvests.length
    };
    renderTable(
      "experiment-reading-history",
      ["Time (UTC)", "Group", "Source", "Air °C", "RH %", "Light lux", "Moisture %", "Water L"],
      readings.readings.map(row => [
        row.recorded_at,
        activeExperiment.groups.find(group => group.id === row.group_id)?.name || "Shared",
        `${row.source_type}: ${row.source_id}`,
        row.air_temperature_c,
        row.relative_humidity_pct,
        row.light_lux,
        row.medium_moisture_pct,
        row.water_added_l
      ]),
      "No environmental readings recorded."
    );
    renderTable(
      "plant-observation-history",
      ["Date (UTC)", "Group", "Plant", "Height cm", "Leaves", "Visible stress"],
      observations.observations.map(row => [
        row.observed_at,
        activeExperiment.groups.find(group => group.id === row.group_id)?.name || "—",
        row.plant_id,
        row.height_cm,
        row.leaf_count,
        row.visible_stress
      ]),
      "No plant observations recorded."
    );
    renderTable(
      "harvest-history",
      ["Date (UTC)", "Group", "Plants", "Fresh mass g", "Dry mass g"],
      harvests.harvests.map(row => [
        row.harvested_at,
        activeExperiment.groups.find(group => group.id === row.group_id)?.name || "—",
        row.plant_count,
        row.fresh_mass_g,
        row.dry_mass_g
      ]),
      "No harvest records yet. Leave dry mass blank unless it was measured."
    );
    renderGrowthChart(observations.observations);
    renderAnalysis(analysis);
    renderSpaceCropComparison();
    $("download-experiment-report").disabled = false;
  }

  async function selectExperiment(experimentId) {
    const detail = $("experiment-detail");
    if (!experimentId) {
      activeExperiment = null;
      activeAnalysis = null;
      activeRecordCounts = null;
      detail.hidden = true;
      $("download-experiment-report").disabled = true;
      renderGrowthChart([]);
      renderSpaceCropComparison();
      showStatus("experiment-workspace-status", "Create an experiment to start recording observations.");
      return;
    }
    try {
      const experiment = await request(`/api/experiments/${experimentId}`);
      activeExperiment = experiment;
      renderExperimentSummary(experiment);
      fillGroupOptions(experiment);
      await loadExperimentRecords(experimentId);
      detail.hidden = false;
      showStatus("experiment-workspace-status", "Experiment loaded. Record actual measurements; blank values remain missing.");
    } catch (error) {
      showStatus("experiment-workspace-status", error.message, true);
    }
  }

  async function loadExperiments(preferredId = null) {
    try {
      experiments = await request("/api/experiments");
      const select = $("experiment-select");
      select.replaceChildren();
      if (!experiments.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "No experiments yet";
        select.append(option);
        await selectExperiment(null);
        return;
      }
      experiments.forEach(experiment => {
        const option = document.createElement("option");
        option.value = String(experiment.id);
        option.textContent = `${experiment.name} · ${experiment.crop}`;
        select.append(option);
      });
      const targetId = preferredId || Number(select.value) || experiments[0].id;
      select.value = String(targetId);
      await selectExperiment(select.value);
    } catch (error) {
      showStatus("experiment-workspace-status", error.message, true);
    }
  }

  async function createExperiment(event) {
    event.preventDefault();
    showStatus("experiment-create-status", "Creating experiment…");
    const endDate = $("experiment-end").value;
    try {
      const created = await request("/api/experiments", {
        method: "POST",
        body: JSON.stringify({
          name: $("experiment-name").value.trim(),
          crop: $("experiment-crop").value.trim(),
          variety: $("experiment-variety").value.trim() || null,
          location: $("experiment-location").value.trim(),
          start_date: $("experiment-start").value,
          end_date: endDate || null,
          research_objective: $("experiment-objective").value.trim(),
          groups: [
            {
              name: $("group-one-name").value.trim(),
              treatment: $("group-one-treatment").value.trim(),
              watering_plan: $("group-one-water").value.trim() || null
            },
            {
              name: $("group-two-name").value.trim(),
              treatment: $("group-two-treatment").value.trim(),
              watering_plan: $("group-two-water").value.trim() || null
            }
          ]
        })
      });
      $("experiment-form").reset();
      $("group-one-name").value = "Control";
      $("group-one-treatment").value = "Consistent, adequate watering";
      $("group-two-name").value = "Reduced water";
      $("group-two-treatment").value = "Reduced measured water supply";
      showStatus("experiment-create-status", "Experiment created. Start recording measurements when the study begins.");
      await loadExperiments(created.id);
    } catch (error) {
      showStatus("experiment-create-status", error.message, true);
    }
  }

  async function addEnvironmentalReading(event) {
    event.preventDefault();
    if (!activeExperiment) return;
    try {
      await request(`/api/experiments/${activeExperiment.id}/readings`, {
        method: "POST",
        body: JSON.stringify({
          group_id: Number($("reading-group").value),
          source_type: "manual",
          source_id: $("reading-source").value.trim(),
          recorded_at: new Date().toISOString(),
          air_temperature_c: numberValue("reading-temperature"),
          relative_humidity_pct: numberValue("reading-humidity"),
          light_lux: numberValue("reading-light"),
          medium_moisture_pct: numberValue("reading-moisture"),
          water_added_l: numberValue("reading-water"),
          notes: $("reading-notes").value.trim() || null
        })
      });
      $("experiment-reading-form").reset();
      $("reading-source").value = "manual-log";
      await loadExperimentRecords(activeExperiment.id);
      showStatus("experiment-workspace-status", "Environmental measurement saved with a timestamp.");
    } catch (error) {
      showStatus("experiment-workspace-status", error.message, true);
    }
  }

  async function addPlantObservation(event) {
    event.preventDefault();
    if (!activeExperiment) return;
    try {
      await request(`/api/experiments/${activeExperiment.id}/observations`, {
        method: "POST",
        body: JSON.stringify({
          group_id: Number($("observation-group").value),
          plant_id: $("plant-id").value.trim(),
          observed_at: new Date().toISOString(),
          height_cm: numberValue("plant-height"),
          leaf_count: numberValue("plant-leaves"),
          visible_stress: $("plant-stress").value.trim() || null,
          notes: $("plant-notes").value.trim() || null,
          image_reference: $("plant-image").value.trim() || null
        })
      });
      $("plant-observation-form").reset();
      await loadExperimentRecords(activeExperiment.id);
      showStatus("experiment-workspace-status", "Plant observation saved.");
    } catch (error) {
      showStatus("experiment-workspace-status", error.message, true);
    }
  }

  async function addHarvest(event) {
    event.preventDefault();
    if (!activeExperiment) return;
    try {
      await request(`/api/experiments/${activeExperiment.id}/harvests`, {
        method: "POST",
        body: JSON.stringify({
          group_id: Number($("harvest-group").value),
          harvested_at: new Date().toISOString(),
          plant_count: Number($("harvest-count").value),
          fresh_mass_g: numberValue("harvest-fresh-mass"),
          dry_mass_g: numberValue("harvest-dry-mass"),
          notes: $("harvest-notes").value.trim() || null
        })
      });
      $("harvest-form").reset();
      await loadExperimentRecords(activeExperiment.id);
      showStatus("experiment-workspace-status", "Harvest data saved. Analysis uses the measured mass and group water records.");
    } catch (error) {
      showStatus("experiment-workspace-status", error.message, true);
    }
  }

  async function addHabitatReading(event) {
    event.preventDefault();
    try {
      const body = {
        device_id: $("habitat-device").value.trim(),
        experiment_id: activeExperiment?.id || null,
        group_id: $("habitat-group").value ? Number($("habitat-group").value) : null,
        source_type: "manual",
        recorded_at: new Date().toISOString(),
        air_temperature_c: numberValue("habitat-temperature"),
        relative_humidity_pct: numberValue("habitat-humidity"),
        light_lux: numberValue("habitat-light"),
        medium_moisture_pct: numberValue("habitat-moisture"),
        water_added_l: numberValue("habitat-water"),
        reservoir_level_l: numberValue("habitat-reservoir"),
        co2_ppm: numberValue("habitat-co2"),
        nutrient_ph: numberValue("habitat-ph"),
        nutrient_ec_ms_cm: numberValue("habitat-ec")
      };
      await request("/api/habitat/readings", { method: "POST", body: JSON.stringify(body) });
      $("habitat-reading-form").reset();
      $("habitat-device").value = body.device_id;
      await loadLatestHabitat(body.device_id);
      showStatus("habitat-status", "Habitat measurements saved.");
    } catch (error) {
      showStatus("habitat-status", error.message, true);
    }
  }

  async function loadLatestHabitat(deviceId) {
    if (!deviceId) return;
    try {
      const data = await request(`/api/habitat/latest?device_id=${encodeURIComponent(deviceId)}`);
      const reading = data.reading;
      if (!reading) {
        $("habitat-latest").textContent = "No habitat readings for this source yet.";
        return;
      }
      const values = [
        ["Recorded (UTC)", reading.recorded_at],
        ["Air temperature", reading.air_temperature_c === null ? null : `${reading.air_temperature_c} °C`],
        ["Relative humidity", reading.relative_humidity_pct === null ? null : `${reading.relative_humidity_pct} %`],
        ["Light", reading.light_lux === null ? null : `${reading.light_lux} lux`],
        ["Medium moisture", reading.medium_moisture_pct === null ? null : `${reading.medium_moisture_pct} %`],
        ["Water added", reading.water_added_l === null ? null : `${reading.water_added_l} L`],
        ["Reservoir", reading.reservoir_level_l === null ? null : `${reading.reservoir_level_l} L`],
        ["CO₂", reading.co2_ppm === null ? null : `${reading.co2_ppm} ppm`],
        ["Nutrient pH", reading.nutrient_ph],
        ["Nutrient EC", reading.nutrient_ec_ms_cm === null ? null : `${reading.nutrient_ec_ms_cm} mS/cm`]
      ];
      const list = document.createElement("dl");
      list.className = "habitat-latest-list";
      values.forEach(([label, value]) => {
        const term = document.createElement("dt");
        const description = document.createElement("dd");
        term.textContent = label;
        description.textContent = value === null ? "Not measured" : String(value);
        list.append(term, description);
      });
      $("habitat-latest").replaceChildren(list);
    } catch (error) {
      showStatus("habitat-status", error.message, true);
    }
  }

  async function loadCropProfiles() {
    try {
      const profiles = await request("/api/crops");
      const container = $("crop-profile-list");
      container.replaceChildren();
      if (!profiles.length) {
        container.textContent = "No crop profiles saved. The app does not ship unsourced nutrition values.";
        return;
      }
      profiles.forEach(profile => {
        const card = document.createElement("article");
        card.className = "crop-profile-card";
        const title = document.createElement("h3");
        title.textContent = profile.name;
        const scientificName = document.createElement("p");
        scientificName.textContent = profile.scientific_name || "Scientific name not recorded";
        const description = document.createElement("p");
        description.textContent = profile.description || "No description recorded.";
        const nutrition = document.createElement("pre");
        nutrition.textContent = Object.keys(profile.nutrition).length
          ? JSON.stringify(profile.nutrition, null, 2)
          : "No nutrition values recorded.";
        const references = document.createElement("ul");
        profile.references.forEach(reference => {
          const item = document.createElement("li");
          item.textContent = `${reference.title || "Reference"} — ${reference.url || "URL not supplied"}`;
          references.append(item);
        });
        card.append(title, scientificName, description, nutrition, references);
        container.append(card);
      });
    } catch (error) {
      showStatus("crop-profile-status", error.message, true);
    }
  }

  async function addCropProfile(event) {
    event.preventDefault();
    try {
      const nutritionText = $("crop-profile-nutrition").value.trim();
      const referencesText = $("crop-profile-references").value.trim();
      const nutrition = nutritionText ? JSON.parse(nutritionText) : {};
      const references = referencesText ? JSON.parse(referencesText) : [];
      if (!nutrition || Array.isArray(nutrition) || typeof nutrition !== "object") {
        throw new Error("Nutrition must be a JSON object.");
      }
      if (!Array.isArray(references)) throw new Error("References must be a JSON array.");
      await request("/api/crops", {
        method: "POST",
        body: JSON.stringify({
          name: $("crop-profile-name").value.trim(),
          scientific_name: $("crop-profile-scientific").value.trim() || null,
          description: $("crop-profile-description").value.trim() || null,
          nutrition,
          references
        })
      });
      $("crop-profile-form").reset();
      showStatus("crop-profile-status", "Crop profile saved with its supplied source references.");
      await loadCropProfiles();
    } catch (error) {
      showStatus("crop-profile-status", error.message, true);
    }
  }

  function reportValue(value, unit = "") {
    return value === null || value === undefined ? "not available" : `${value}${unit ? ` ${unit}` : ""}`;
  }

  function downloadExperimentReport() {
    if (!activeExperiment || !activeAnalysis || !activeRecordCounts) return;
    const lines = [
      "EARTHSIGNAL — CONTROLLED GROWING EXPERIMENT REPORT",
      `Generated (UTC): ${new Date().toISOString()}`,
      "",
      "EXPERIMENT",
      `Name: ${activeExperiment.name}`,
      `Crop and variety: ${activeExperiment.crop}${activeExperiment.variety ? ` · ${activeExperiment.variety}` : ""}`,
      `Location: ${activeExperiment.location}`,
      `Period: ${activeExperiment.start_date} to ${activeExperiment.end_date || "in progress"}`,
      `Objective: ${activeExperiment.research_objective}`,
      `Records loaded: ${activeRecordCounts.readings} environmental, ${activeRecordCounts.observations} plant, ${activeRecordCounts.harvests} harvest`,
      "",
      "GROUP RESULTS"
    ];
    activeAnalysis.groups.forEach(group => {
      const values = group.measurements;
      lines.push(
        `${group.group_name} — ${group.treatment}`,
        `  Recorded water: ${reportValue(values.water_added_l, "L")}`,
        `  Fresh harvest: ${reportValue(values.fresh_mass_g, "g")}`,
        `  Dry harvest: ${reportValue(values.dry_mass_g, "g")}`,
        `  Fresh yield per plant: ${reportValue(values.fresh_yield_g_per_plant, "g/plant")}`,
        `  Fresh-mass WUE: ${reportValue(values.fresh_water_use_efficiency_g_per_l, "g/L")}`,
        `  Dry-mass WUE: ${reportValue(values.dry_water_use_efficiency_g_per_l, "g/L")}`,
        `  Mean height change: ${reportValue(group.growth.mean_height_change_cm_per_day, "cm/day")}`
      );
    });
    lines.push("", "METHODS AND LIMITATIONS", ...activeAnalysis.limitations.map(item => `- ${item}`));
    lines.push(
      "- Only entered measurements are included; missing values are not treated as zero.",
      "- Results describe an Earth-based growing study and do not reproduce microgravity or spacecraft life-support conditions.",
      "- Nutrition is not measured by environmental sensors and must be supported by a separate cited source.",
      "",
      "SPACE-CROP RESEARCH CONTEXT",
      "NASA's VEG-01 record describes Outredgeous red romaine lettuce grown in the Veggie system aboard the ISS for 33 days. NASA's summary reports watering challenges but does not state directly comparable height, leaf-count, or harvest-mass values.",
      "Reference: https://ntrs.nasa.gov/citations/20160004060",
      "EarthSignal's Earth-based observations are separate evidence and are not directly comparable to ISS growing conditions."
    );
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `earthsignal-experiment-${activeExperiment.id}-report.txt`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  $("experiment-form").addEventListener("submit", createExperiment);
  $("experiment-select").addEventListener("change", event => selectExperiment(event.target.value));
  $("refresh-experiments").addEventListener("click", () => loadExperiments(activeExperiment?.id));
  $("experiment-reading-form").addEventListener("submit", addEnvironmentalReading);
  $("plant-observation-form").addEventListener("submit", addPlantObservation);
  $("harvest-form").addEventListener("submit", addHarvest);
  $("habitat-reading-form").addEventListener("submit", addHabitatReading);
  $("crop-profile-form").addEventListener("submit", addCropProfile);
  $("download-experiment-report").addEventListener("click", downloadExperimentReport);
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", () => {
      if (link.dataset.page === "experiments") loadExperiments(activeExperiment?.id);
    });
  });
  loadExperiments();
  loadCropProfiles();
  loadLatestHabitat($("habitat-device").value);
  setInterval(() => {
    if (!$("experiments-page").hidden) loadLatestHabitat($("habitat-device").value.trim());
  }, 10000);
})();
