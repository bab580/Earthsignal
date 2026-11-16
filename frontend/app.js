let currentData = null;
let chart = null;
let currentComparisons = [];
let currentRainfallEvents = null;
const selectedComparisonLocations = new Map();
let comparisonSearchResults = [];

const places = {
  "0.3476,32.5825": "Kampala",
  "2.2499,32.8998": "Lira",
  "2.7746,32.2990": "Gulu",
  "1.0821,34.1750": "Mbale",
  "-0.6067,30.6545": "Mbarara"
};

const placeCountries = {
  "0.3476,32.5825": "Uganda",
  "2.2499,32.8998": "Uganda",
  "2.7746,32.2990": "Uganda",
  "1.0821,34.1750": "Uganda",
  "-0.6067,30.6545": "Uganda"
};

const metricInfo = {
  PRECTOTCORR: { label: "daily precipitation" },
  T2M: { label: "daily air temperature" },
  NDVI: { label: "vegetation index (NDVI)" },
  LST_DAY_C: { label: "daytime land-surface temperature" }
};

const $ = (id) => document.getElementById(id);
const fmt = (v) => v === null || v === undefined ? "—" : Number(v).toFixed(2);

async function loadData() {
  const [lat, lon] = $("place").value.split(",").map(Number);
  const start = $("start").value;
  const end = $("end").value;
  const button = $("load");
  const status = $("status");

  if (!start || !end || start > end) {
    status.textContent = "Choose a valid date range. Start date must be on or before end date.";
    status.className = "status error";
    return;
  }

  button.disabled = true;
  status.className = "status";
  status.textContent = "Requesting live observations from NASA POWER…";
  $("results").hidden = true;
  currentData = null;
  currentComparisons = [];
  currentRainfallEvents = null;

  try {
    const payload = await fetchEarthData(lat, lon, start, end);
    currentData = payload;
    render(payload);
    status.textContent = "NASA POWER data loaded successfully.";
  } catch (err) {
    status.textContent = err.message;
    status.className = "status error";
  } finally {
    button.disabled = false;
  }
}

function researchLocationLabel(location) {
  return [location.name, location.admin1, location.country]
    .filter((part, index, parts) => part && parts.indexOf(part) === index)
    .join(", ");
}

async function fetchResearchLocations(query) {
  const response = await fetch(earthSignalApiUrl(`/api/weather/locations?query=${encodeURIComponent(query)}`));
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Could not search global locations.");
  return Array.isArray(payload.results) ? payload.results : [];
}

async function searchResearchLocations() {
  const query = $("research-location-query").value.trim();
  const resultsElement = $("research-location-results");
  const status = $("research-location-status");
  const button = $("research-location-search-button");
  resultsElement.replaceChildren();
  resultsElement.hidden = true;
  if (query.length < 2) {
    status.textContent = "Enter at least two characters to search for a place.";
    status.className = "location-search-status error";
    return;
  }

  button.disabled = true;
  status.className = "location-search-status";
  status.textContent = "Searching global place names…";
  try {
    const locations = await fetchResearchLocations(query);
    if (locations.length === 0) {
      status.textContent = "No matching places found. Try adding a country or nearby city.";
      return;
    }

    locations.forEach(location => {
      const option = document.createElement("button");
      option.type = "button";
      option.className = "location-search-option";
      option.textContent =
        `${researchLocationLabel(location)} (${Number(location.latitude).toFixed(4)}, ${Number(location.longitude).toFixed(4)})`;
      option.addEventListener("click", () => selectResearchLocation(location));
      resultsElement.append(option);
    });
    resultsElement.hidden = false;
    status.textContent = `${locations.length} matching places found. Select one to load real NASA POWER data for its coordinates.`;
  } catch (error) {
    status.textContent = error.message;
    status.className = "location-search-status error";
  } finally {
    button.disabled = false;
  }
}

async function searchComparisonLocations() {
  const query = $("comparison-location-query").value.trim();
  const resultsElement = $("comparison-location-results");
  const status = $("comparison-location-search-status");
  const button = $("comparison-location-search-button");
  resultsElement.replaceChildren();
  resultsElement.hidden = true;
  if (query.length < 2) {
    comparisonSearchResults = [];
    status.textContent = "Enter at least two characters to search for a comparison place.";
    status.className = "location-search-status error";
    return;
  }

  comparisonSearchResults = [];
  button.disabled = true;
  status.className = "location-search-status";
  status.textContent = "Searching global place names…";
  try {
    comparisonSearchResults = await fetchResearchLocations(query);
    if (comparisonSearchResults.length === 0) {
      status.textContent = "No matching places found. Try adding a country or nearby city.";
      return;
    }
    renderComparisonSearchResults();
    resultsElement.hidden = false;
    status.textContent = `${comparisonSearchResults.length} matching places found. Add one or more points to compare.`;
  } catch (error) {
    status.textContent = error.message;
    status.className = "location-search-status error";
  } finally {
    button.disabled = false;
  }
}

function renderComparisonSearchResults() {
  const resultsElement = $("comparison-location-results");
  resultsElement.replaceChildren();
  const primaryKey = $("place").value;
  comparisonSearchResults.forEach(location => {
    const key = `${Number(location.latitude)},${Number(location.longitude)}`;
    const alreadySelected = selectedComparisonLocations.has(key);
    const isPrimary = key === primaryKey;
    const option = document.createElement("button");
    option.type = "button";
    option.className = "location-search-option";
    option.disabled = alreadySelected || isPrimary;
    option.textContent = `${researchLocationLabel(location)} (${Number(location.latitude).toFixed(4)}, ${Number(location.longitude).toFixed(4)})${isPrimary ? " — primary location" : alreadySelected ? " — added" : " — add"}`;
    option.addEventListener("click", () => {
      if (selectedComparisonLocations.has(key) || key === $("place").value) return;
      selectedComparisonLocations.set(key, location);
      renderSelectedComparisonLocations();
      renderComparisonSearchResults();
      $("comparison-results").hidden = true;
      currentComparisons = [];
      $("comparison-status").textContent = `Added ${researchLocationLabel(location)}. Run Compare selected to load its data.`;
    });
    resultsElement.append(option);
  });
}

function renderSelectedComparisonLocations() {
  const container = $("comparison-locations");
  container.replaceChildren();
  selectedComparisonLocations.forEach((location, key) => {
    const item = document.createElement("div");
    item.className = "comparison-location-chip";
    item.setAttribute("role", "listitem");
    const name = document.createElement("span");
    name.textContent = researchLocationLabel(location);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "comparison-location-remove";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", `Remove ${researchLocationLabel(location)} from comparisons`);
    remove.addEventListener("click", () => {
      selectedComparisonLocations.delete(key);
      renderSelectedComparisonLocations();
      renderComparisonSearchResults();
      $("comparison-results").hidden = true;
      currentComparisons = [];
      $("comparison-status").textContent = "Comparison points changed. Run Compare selected to refresh the results.";
    });
    item.append(name, remove);
    container.append(item);
  });
  if (selectedComparisonLocations.size === 0) {
    const empty = document.createElement("p");
    empty.className = "comparison-empty";
    empty.textContent = "Search above and add locations to compare.";
    container.append(empty);
  }
}

function clearComparisonLocations() {
  selectedComparisonLocations.clear();
  renderSelectedComparisonLocations();
  renderComparisonSearchResults();
}

function updateComparisonSearchCountry(country) {
  const input = $("comparison-location-query");
  input.value = "";
  input.placeholder = country ? `Search a city or region in ${country}` : "e.g. Kampala, Uganda or Nairobi, Kenya";
  comparisonSearchResults = [];
  $("comparison-location-results").replaceChildren();
  $("comparison-location-results").hidden = true;
  $("comparison-location-search-status").textContent = country
    ? `Primary location is in ${country}. Search for another place to compare.`
    : "Search for a city, region or country to add comparison points.";
}

function selectResearchLocation(location) {
  const latitude = Number(location.latitude);
  const longitude = Number(location.longitude);
  const name = researchLocationLabel(location);
  const key = `${latitude},${longitude}`;
  let option = Array.from($("place").options).find(item => item.value === key);
  if (!option) {
    option = document.createElement("option");
    option.value = key;
    $("place").append(option);
  }
  option.textContent = `${name} (${latitude.toFixed(4)}, ${longitude.toFixed(4)})`;
  places[key] = name;
  placeCountries[key] = location.country || "";
  $("place").value = key;
  $("research-location-query").value = name;
  clearComparisonLocations();
  updateComparisonSearchCountry(placeCountries[key]);
  $("research-location-results").replaceChildren();
  $("research-location-results").hidden = true;
  $("research-location-status").className = "location-search-status";
  $("research-location-status").textContent = `Selected ${name}. Loading live NASA POWER observations for ${latitude.toFixed(4)}, ${longitude.toFixed(4)}…`;
  loadData();
}

async function fetchEarthData(latitude, longitude, start, end) {
  const query = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    start,
    end
  });
  const response = await fetch(earthSignalApiUrl(`/api/earth?${query}`));
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "NASA data request failed.");
  if (!payload.rainfall_events || !Array.isArray(payload.rainfall_events.high_rain_days) ||
      !Array.isArray(payload.rainfall_events.dry_spells)) {
    throw new Error("The research API needs restarting to load rainfall-event analysis. Please restart the EarthSignal backend.");
  }
  return payload;
}

function render(data) {
  $("results").hidden = false;
  $("comparison-results").hidden = true;
  $("comparison-status").textContent = "Search for global locations to compare against the selected point.";
  $("metric").value = "PRECTOTCORR";
  setModisOptionsEnabled(false);
  $("modis-status").textContent = "MODIS point data is free through NASA AppEEARS, but requires a NASA Earthdata Login configured locally.";
  $("modis-status").className = "modis-status";
  const placeName = places[`${data.location.latitude},${data.location.longitude}`] || "Selected location";
  $("place-title").textContent = placeName;
  const rain = data.summary.PRECTOTCORR;
  const temp = data.summary.T2M;
  $("rain-mean").textContent = fmt(rain.mean);
  $("temp-mean").textContent = fmt(temp.mean);
  $("rain-unit").textContent = data.parameters.PRECTOTCORR.unit;
  $("temp-unit").textContent = data.parameters.T2M.unit;
  $("records").textContent = `${rain.valid_count.toLocaleString()} / ${temp.valid_count.toLocaleString()}`;
  currentRainfallEvents = data.rainfall_events;
  renderResearchBrief(data, currentRainfallEvents);
  renderRainfallEvents(currentRainfallEvents, data.parameters.PRECTOTCORR.unit);
  const p = data.parameters;
  $("provenance").innerHTML = `
    <div><b>Source</b>${data.source}</div>
    <div><b>Coordinates</b>${data.location.latitude}, ${data.location.longitude}</div>
    <div><b>Period</b>${data.period.start} to ${data.period.end}</div>
    <div><b>Precipitation variable</b>PRECTOTCORR · ${p.PRECTOTCORR.unit}</div>
    <div><b>Temperature variable</b>T2M · ${p.T2M.unit}</div>
    <div><b>Retrieved at</b>${new Date(data.retrieved_at).toLocaleString()}</div>
    <div><b>NASA source URL</b><a href="${data.source_url}" target="_blank" rel="noopener">NASA POWER Daily API</a></div>
    <div><b>Method</b>${data.method_note}</div>`;
  drawChart();
}

function renderResearchBrief(data, events) {
  const placeName = places[`${data.location.latitude},${data.location.longitude}`] || "the selected point";
  const rain = data.summary.PRECTOTCORR;
  const temperature = data.summary.T2M;
  const rainUnit = data.parameters.PRECTOTCORR.unit;
  const temperatureUnit = data.parameters.T2M.unit;
  const rainfallSummary = rain.mean === null
    ? "No valid daily precipitation average was returned"
    : `mean daily precipitation was ${fmt(rain.mean)} ${rainUnit}`;
  const temperatureSummary = temperature.mean === null
    ? "no valid daily air-temperature average was returned"
    : `mean daily air temperature was ${fmt(temperature.mean)} ${temperatureUnit}`;
  const wetDaySummary = events.threshold === null
    ? `There were ${events.wet_day_count} positive wet days, too few to estimate a stable 95th-percentile screen`
    : `${events.high_rain_days.length} days met the high-rainfall screen (at least ${fmt(events.threshold)} ${rainUnit})`;
  const drySpellSummary = events.dry_spells.length === 0
    ? "no 14-day dry spell was identified"
    : `${events.dry_spells.length} extended dry spell${events.dry_spells.length === 1 ? " was" : "s were"} identified`;

  $("research-brief-text").textContent =
    `For ${placeName}, ${data.period.start} to ${data.period.end}, ${rainfallSummary} and ${temperatureSummary}. ${wetDaySummary}; ${drySpellSummary}. These are screening signals in a gridded dataset, not confirmation of flooding, drought impacts or their causes.`;
}

function renderRainfallEvents(events, unit) {
  const filter = $("event-filter").value;
  const candidates = [
    ...events.high_rain_days.map(event => ({
      kind: "high-rain",
      date: event.date,
      label: "High-rainfall screen",
      period: event.date,
      amount: `${fmt(event.rainfall)} ${unit}`
    })),
    ...events.dry_spells.map(event => ({
      kind: "dry-spell",
      date: event.start,
      label: "Extended dry-spell screen",
      period: `${event.start} to ${event.end} (${event.days} days)`,
      amount: "Below 1 mm/day"
    }))
  ].sort((a, b) => a.date.localeCompare(b.date));
  const visibleEvents = candidates.filter(event => filter === "all" || event.kind === filter);
  const highRainSummary = events.threshold === null
    ? `Not enough positive wet days (${events.wet_day_count}; at least 20 needed) to estimate the selected-period 95th-percentile rainfall screen`
    : `${events.high_rain_days.length} high-rainfall day${events.high_rain_days.length === 1 ? "" : "s"} at or above ${fmt(events.threshold)} ${unit}`;
  const summary = `${highRainSummary}; ${events.dry_spells.length} extended dry spell${events.dry_spells.length === 1 ? "" : "s"} found.`;

  $("event-summary").textContent = summary;
  $("event-rows").replaceChildren(...visibleEvents.map(event => {
    const row = document.createElement("tr");
    [event.label, event.period, event.amount].forEach(value => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    return row;
  }));
  $("event-empty").hidden = visibleEvents.length > 0;
}

async function compareLocations() {
  const status = $("comparison-status");
  if (!currentData) {
    status.textContent = "Load NASA POWER data for a primary location before comparing.";
    return;
  }

  const start = $("start").value;
  const end = $("end").value;
  const currentKey = `${currentData.location.latitude},${currentData.location.longitude}`;
  if ($("place").value !== currentKey || start !== currentData.period.start || end !== currentData.period.end) {
    status.textContent = "Load NASA POWER data for the selected location and dates before comparing.";
    return;
  }

  const selectedLocations = Array.from(selectedComparisonLocations.entries())
    .filter(([key]) => key !== currentKey);
  if (!selectedLocations.length) {
    status.textContent = "Search and add at least one location other than the primary point.";
    return;
  }

  const button = $("compare-locations");
  button.disabled = true;
  $("comparison-results").hidden = true;
  status.className = "comparison-status";
  status.textContent = `Loading ${selectedLocations.length} comparison point${selectedLocations.length === 1 ? "" : "s"} from NASA POWER…`;

  try {
    const additionalSites = await Promise.all(selectedLocations.map(async ([, location]) => {
      return {
        name: researchLocationLabel(location),
        data: await fetchEarthData(Number(location.latitude), Number(location.longitude), start, end)
      };
    }));
    currentComparisons = [
      { name: places[currentKey] || "Selected point", data: currentData, events: currentRainfallEvents },
      ...additionalSites.map(entry => ({
        ...entry,
        events: entry.data.rainfall_events
      }))
    ];
    renderComparisonResults();
    $("comparison-results").hidden = false;
    status.className = "comparison-status success";
    status.textContent = `Compared ${currentComparisons.length} point samples for ${start} to ${end}.`;
  } catch (error) {
    currentComparisons = [];
    status.className = "comparison-status error";
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function renderComparisonResults() {
  const entries = currentComparisons;
  const rows = entries.map(entry => {
    const row = document.createElement("tr");
    const values = [
      entry.name,
      `${fmt(entry.data.summary.PRECTOTCORR.mean)} ${entry.data.parameters.PRECTOTCORR.unit}`,
      `${fmt(entry.data.summary.T2M.mean)} ${entry.data.parameters.T2M.unit}`,
      `${entry.data.summary.PRECTOTCORR.valid_count.toLocaleString()} / ${entry.data.summary.T2M.valid_count.toLocaleString()}`,
      `${entry.data.location.latitude}, ${entry.data.location.longitude}`
    ];
    values.forEach(value => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    return row;
  });
  $("comparison-rows").replaceChildren(...rows);

  const wettest = entries
    .filter(entry => entry.data.summary.PRECTOTCORR.mean !== null)
    .reduce((best, entry) =>
      !best || entry.data.summary.PRECTOTCORR.mean > best.data.summary.PRECTOTCORR.mean ? entry : best, null);
  const warmest = entries
    .filter(entry => entry.data.summary.T2M.mean !== null)
    .reduce((best, entry) =>
      !best || entry.data.summary.T2M.mean > best.data.summary.T2M.mean ? entry : best, null);
  const statements = [];
  if (wettest) {
    statements.push(`${wettest.name} had the highest mean daily precipitation (${fmt(wettest.data.summary.PRECTOTCORR.mean)} ${wettest.data.parameters.PRECTOTCORR.unit})`);
  }
  if (warmest) {
    statements.push(`${warmest.name} had the highest mean daily air temperature (${fmt(warmest.data.summary.T2M.mean)} ${warmest.data.parameters.T2M.unit})`);
  }
  $("comparison-summary").textContent = statements.length
    ? `${statements.join("; ")} among the selected points.`
    : "No valid comparison averages were returned for these points.";
}

function renderModisProvenance(data) {
  const container = $("provenance");
  container.querySelectorAll("[data-modis-provenance]").forEach(item => item.remove());
  if (!data) return;

  const validNdvi = data.observations.filter(row => row.NDVI !== null).length;
  const validLst = data.observations.filter(row => row.LST_DAY_C !== null).length;
  const items = [
    ["Additional source", data.source],
    ["MODIS products", `${data.products.NDVI.product} · NDVI (250 m, 16-day); ${data.products.LST_DAY_C.product} · daytime LST (1 km, 8-day)`],
    ["Quality-screened samples", `NDVI: ${validNdvi}; land-surface temperature: ${validLst}`],
    ["MODIS retrieved at", new Date(data.retrieved_at).toLocaleString()],
    ["MODIS method", data.method_note]
  ];

  items.forEach(([label, value]) => {
    const item = document.createElement("div");
    const title = document.createElement("b");
    title.textContent = label;
    item.dataset.modisProvenance = "true";
    item.append(title, document.createTextNode(value));
    container.append(item);
  });
}

function drawChart() {
  if (!currentData) return;
  const metric = $("metric").value;
  const rows = currentData.observations.filter(r => r[metric] !== null && r[metric] !== undefined);
  const labels = rows.map(r => r.date);
  const values = rows.map(r => r[metric]);
  const unit = currentData.parameters[metric].unit;
  const label = metricInfo[metric].label;
  renderInterpretation(rows, metric, unit, label);
  renderHistoricalSignals(metric);
  if (chart) chart.destroy();
  chart = new Chart($("chart"), {
    type: "line",
    data: { labels, datasets: [{ label, data: values, borderColor: "#24765b", backgroundColor: "rgba(36,118,91,.10)", pointRadius: 0, borderWidth: 1.5, fill: true, tension: .15 }] },
    options: {
      responsive: true,
      interaction: { intersect: false, mode: "index" },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y} ${unit}` } } },
      scales: { x: { ticks: { maxTicksLimit: 8, maxRotation: 0 } }, y: { title: { display: true, text: unit } } }
    }
  });
}

function renderInterpretation(rows, metric, unit, label) {
  const summary = $("interpretation-summary");
  const details = $("interpretation-details");
  const sorted = rows
    .filter(row => Number.isFinite(Number(row[metric])) && Number.isFinite(Date.parse(row.date)))
    .slice()
    .sort((a, b) => a.date.localeCompare(b.date));

  if (!sorted.length) {
    summary.textContent = `No valid ${label} observations were returned for this selection.`;
    details.replaceChildren();
    return;
  }

  const values = sorted.map(row => Number(row[metric]));
  const mean = values.reduce((total, value) => total + value, 0) / values.length;
  const minRow = sorted.reduce((best, row) => Number(row[metric]) < Number(best[metric]) ? row : best);
  const maxRow = sorted.reduce((best, row) => Number(row[metric]) > Number(best[metric]) ? row : best);
  const firstTime = Date.parse(sorted[0].date);
  const lastTime = Date.parse(sorted[sorted.length - 1].date);
  const monthGroups = Array.from({ length: 12 }, () => []);
  sorted.forEach(row => {
    const month = new Date(`${row.date}T00:00:00Z`).getUTCMonth();
    monthGroups[month].push(Number(row[metric]));
  });
  const monthAverages = monthGroups
    .map((monthValues, month) => ({
      month,
      average: monthValues.length ? monthValues.reduce((total, value) => total + value, 0) / monthValues.length : null
    }))
    .filter(item => item.average !== null);
  const monthName = month => new Intl.DateTimeFormat("en", { month: "long", timeZone: "UTC" })
    .format(new Date(Date.UTC(2020, month, 1)));
  const hasMonthlyPattern = lastTime - firstTime >= 300 * 24 * 60 * 60 * 1000 && monthAverages.length >= 10;

  let insights;
  if (metric === "PRECTOTCORR") {
    const underOne = values.filter(value => value < 1).length;
    const percentage = Math.round(underOne / values.length * 100);
    const wettestMonth = monthAverages.reduce((best, item) => item.average > best.average ? item : best);
    const driestMonth = monthAverages.reduce((best, item) => item.average < best.average ? item : best);
    summary.textContent = `At ${$("place-title").textContent}, rainfall was uneven from ${sorted[0].date} to ${sorted[sorted.length - 1].date}. ${underOne.toLocaleString()} of ${values.length.toLocaleString()} days (${percentage}%) had less than 1 mm, meaning very little or no rain. Other days had much more, with a peak of ${fmt(maxRow[metric])} ${unit} on ${maxRow.date}. The period average was ${fmt(mean)} ${unit}; it does not mean that amount fell steadily each day.`;
    insights = [
      { label: "Very little or no rain (<1 mm)", text: `${underOne.toLocaleString()} of ${values.length.toLocaleString()} days (${percentage}%)` },
      { label: "Largest one-day amount", text: `${fmt(maxRow[metric])} ${unit} on ${maxRow.date}` },
      {
        label: "Month-to-month pattern",
        text: hasMonthlyPattern
          ? `Average daily rainfall was highest in ${monthName(wettestMonth.month)} and lowest in ${monthName(driestMonth.month)}.`
          : "Select a date range of about a year or more to compare months."
      }
    ];
  } else if (metric === "T2M") {
    const warmestMonth = monthAverages.reduce((best, item) => item.average > best.average ? item : best);
    const coolestMonth = monthAverages.reduce((best, item) => item.average < best.average ? item : best);
    summary.textContent = `At ${$("place-title").textContent}, daily air temperature averaged ${fmt(mean)} ${unit} from ${sorted[0].date} to ${sorted[sorted.length - 1].date}. Individual readings ranged from ${fmt(minRow[metric])} ${unit} to ${fmt(maxRow[metric])}.`;
    if (hasMonthlyPattern) {
      summary.textContent += ` In these observations, the monthly average was highest in ${monthName(warmestMonth.month)} and lowest in ${monthName(coolestMonth.month)}.`;
    }
    insights = [
      { label: "Average across selected days", text: `${fmt(mean)} ${unit}` },
      { label: "Lowest reading", text: `${fmt(minRow[metric])} ${unit} on ${minRow.date}` },
      { label: "Highest reading", text: `${fmt(maxRow[metric])} ${unit} on ${maxRow.date}` },
      {
        label: "Month-to-month pattern",
        text: hasMonthlyPattern
          ? `Average temperature was highest in ${monthName(warmestMonth.month)} and lowest in ${monthName(coolestMonth.month)}.`
          : "Select a date range of about a year or more to compare months."
      }
    ];
  } else {
    const metricName = metricInfo[metric].label;
    summary.textContent = `At ${$("place-title").textContent}, the ${metricName} ranged from ${fmt(minRow[metric])} to ${fmt(maxRow[metric])} ${unit} between ${sorted[0].date} and ${sorted[sorted.length - 1].date}. The average was ${fmt(mean)} ${unit}.`;
    if (metric === "NDVI") {
      summary.textContent += " NDVI is a vegetation index: lower or falling values can indicate less green vegetation, but do not by themselves identify the cause or confirm crop damage.";
    } else {
      summary.textContent += " This measures the land surface, not the air or soil temperature.";
    }
    insights = [
      { label: "Average across selected observations", text: `${fmt(mean)} ${unit}` },
      { label: "Lowest reading", text: `${fmt(minRow[metric])} ${unit} on ${minRow.date}` },
      { label: "Highest reading", text: `${fmt(maxRow[metric])} ${unit} on ${maxRow.date}` }
    ];
  }

  details.replaceChildren(...insights.map(insight => {
    const item = document.createElement("div");
    const title = document.createElement("b");
    const text = document.createElement("span");
    title.textContent = insight.label;
    text.textContent = insight.text;
    item.append(title, text);
    return item;
  }));
}

function setModisOptionsEnabled(enabled) {
  ["NDVI", "LST_DAY_C"].forEach(value => {
    const option = Array.from($("metric").options).find(item => item.value === value);
    if (option) option.disabled = !enabled;
  });
}

async function loadModis() {
  if (!currentData) return;
  const button = $("load-modis");
  const status = $("modis-status");
  const { latitude, longitude } = currentData.location;
  const { start, end } = currentData.period;
  button.disabled = true;
  status.className = "modis-status";
  status.textContent = "Requesting quality-screened MODIS vegetation and land-surface temperature samples from NASA AppEEARS…";

  try {
    const query = new URLSearchParams({
      latitude: String(latitude),
      longitude: String(longitude),
      start,
      end
    });
    const response = await fetch(earthSignalApiUrl(`/api/modis?${query}`));
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "NASA MODIS request failed.");

    const observationsByDate = new Map(currentData.observations.map(row => [row.date, { ...row }]));
    payload.observations.forEach(sample => {
      const row = observationsByDate.get(sample.date) || { date: sample.date };
      row.NDVI = sample.NDVI;
      row.LST_DAY_C = sample.LST_DAY_C;
      observationsByDate.set(sample.date, row);
    });
    currentData.observations = Array.from(observationsByDate.values()).sort((a, b) => a.date.localeCompare(b.date));
    currentData.parameters = { ...currentData.parameters, ...payload.parameters };
    currentData.analysis = { ...currentData.analysis, ...payload.analysis };
    currentData.modis = payload;
    renderModisProvenance(payload);
    setModisOptionsEnabled(true);
    const validNdvi = payload.observations.filter(row => row.NDVI !== null).length;
    const validLst = payload.observations.filter(row => row.LST_DAY_C !== null).length;
    status.className = "modis-status success";
    status.textContent = `Loaded NASA MODIS data: ${validNdvi} quality-screened vegetation values and ${validLst} land-surface temperature values.`;
    drawChart();
  } catch (error) {
    status.className = "modis-status error";
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function renderHistoricalSignals(metric) {
  const container = $("analysis-signals");
  const analysis = currentData.analysis && currentData.analysis[metric];
  if (!analysis) {
    container.textContent = "No historical analysis is available for this indicator.";
    return;
  }

  const unit = currentData.parameters[metric].unit;
  const anomaly = analysis.latest_month_anomaly;
  const trend = analysis.trend;
  const monthName = month => new Intl.DateTimeFormat("en", { month: "long", timeZone: "UTC" })
    .format(new Date(Date.UTC(2020, month - 1, 1)));
  const signals = [];

  if (anomaly.status === "insufficient_history") {
    signals.push({
      label: "Latest seasonal comparison",
      text: `Not enough earlier complete data for the same month. At least ${anomaly.required_baseline_years || 3} previous years are needed; ${anomaly.baseline_years || 0} available.`
    });
  } else {
    const relation = anomaly.difference > 0 ? "above" : anomaly.difference < 0 ? "below" : "equal to";
    const flag = anomaly.status === "unusual" ? "Unusual compared with earlier years" : "Within the historical baseline range";
    signals.push({
      label: `${monthName(anomaly.month)} ${anomaly.year}: ${flag}`,
      text: `This month's average was ${fmt(anomaly.observed)} ${unit}, ${relation} the earlier same-month median of ${fmt(anomaly.baseline_median)} ${unit} (${anomaly.baseline_years} comparison years).`
    });
  }

  if (trend.status === "insufficient_history") {
    signals.push({
      label: "Long-term trend",
      text: `Not tested: ${trend.sample_years} complete years available; at least ${trend.required_years} are required.`
    });
  } else if (trend.status === "increasing" || trend.status === "decreasing") {
    signals.push({
      label: `Statistically significant ${trend.status} trend`,
      text: `About ${fmt(Math.abs(trend.sen_slope_per_year))} ${unit} per year (Mann–Kendall p=${trend.p_value}, ${trend.sample_years} complete years). This is historical evidence, not a forecast.`
    });
  } else {
    signals.push({
      label: "No statistically significant trend detected",
      text: `The data do not provide strong evidence of a steady increase or decrease across ${trend.sample_years} complete years. This does not prove that no changes occurred.`
    });
  }

  container.replaceChildren(...signals.map(signal => {
    const item = document.createElement("article");
    const title = document.createElement("b");
    const text = document.createElement("p");
    title.textContent = signal.label;
    text.textContent = signal.text;
    item.append(title, text);
    return item;
  }));
}

function reportNumber(value, unit = "") {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "not available";
  const formatted = Number(value).toLocaleString("en", { maximumFractionDigits: 2 });
  return unit ? `${formatted} ${unit}` : formatted;
}

function reportAnomaly(analysis, unit) {
  const anomaly = analysis.latest_month_anomaly;
  if (anomaly.status === "insufficient_history") {
    return `Insufficient history: ${anomaly.baseline_years || 0} earlier comparison years; ${anomaly.required_baseline_years || 3} required.`;
  }
  const month = new Intl.DateTimeFormat("en", { month: "long", timeZone: "UTC" })
    .format(new Date(Date.UTC(2020, anomaly.month - 1, 1)));
  const status = anomaly.status === "unusual"
    ? "outside the historical baseline range"
    : "within the historical baseline range";
  return `${month} ${anomaly.year} was ${status}: ${reportNumber(anomaly.observed, unit)} versus an earlier same-month median of ${reportNumber(anomaly.baseline_median, unit)} (${anomaly.baseline_years} comparison years).`;
}

function reportTrend(analysis, unit) {
  const trend = analysis.trend;
  if (trend.status === "insufficient_history") {
    return `Not tested: ${trend.sample_years} complete years available; ${trend.required_years} required.`;
  }
  if (trend.status === "increasing" || trend.status === "decreasing") {
    return `Statistically significant ${trend.status} trend; Sen's slope ${reportNumber(Math.abs(trend.sen_slope_per_year), `${unit}/year`)} (Mann–Kendall p=${trend.p_value}, ${trend.sample_years} complete years).`;
  }
  return `No statistically significant trend detected across ${trend.sample_years} complete years.`;
}

function formatEvidenceReport(report) {
  const lines = [
    "EARTHSIGNAL — RESEARCH EVIDENCE REPORT",
    `Generated (UTC): ${report.generated_at}`,
    "",
    "LOCATION AND PERIOD",
    `Primary location: ${report.primary_location_name}`,
    `Coordinates: ${report.location.latitude}, ${report.location.longitude}`,
    `Dates: ${report.period.start} to ${report.period.end}`,
    `Sources: ${report.sources.join("; ")}`,
    "",
    "RESEARCH BRIEF",
    report.research_brief,
    "",
    "OBSERVATION SUMMARY"
  ];

  for (const [metric, label] of [["PRECTOTCORR", "Daily precipitation"], ["T2M", "Daily air temperature"]]) {
    const summary = report.summary[metric];
    const unit = report.parameters[metric].unit;
    lines.push(
      `${label} (${metric}; ${unit}):`,
      `  Mean: ${reportNumber(summary.mean, unit)}; minimum: ${reportNumber(summary.min, unit)}; maximum: ${reportNumber(summary.max, unit)}.`,
      `  Valid observations: ${reportNumber(summary.valid_count)}; missing observations: ${reportNumber(summary.missing_count)}.`
    );
  }

  lines.push("", "HISTORICAL ANALYSIS");
  for (const [metric, label] of [["PRECTOTCORR", "Daily precipitation"], ["T2M", "Daily air temperature"]]) {
    const analysis = report.analysis[metric];
    const unit = report.parameters[metric].unit;
    lines.push(
      `${label} (${metric}):`,
      `  Coverage: ${analysis.coverage.valid_observations} valid observations, ${analysis.coverage.complete_months} complete months, ${analysis.coverage.complete_years} complete years.`,
      `  Seasonal comparison: ${reportAnomaly(analysis, unit)}`,
      `  Long-term trend: ${reportTrend(analysis, unit)}`
    );
  }

  const events = report.research_events;
  lines.push("", "RAINFALL EVENT SCREENS");
  if (events.threshold === null) {
    lines.push(`High-rainfall screen: not estimated; ${events.wet_day_count} positive wet days were available, and at least 20 are required.`);
  } else {
    lines.push(`High-rainfall screen: ${events.high_rain_days.length} days at or above ${reportNumber(events.threshold, report.parameters.PRECTOTCORR.unit)} (95th percentile of ${events.wet_day_count} positive wet days).`);
    events.high_rain_days.forEach(event => {
      lines.push(`  ${event.date}: ${reportNumber(event.rainfall, report.parameters.PRECTOTCORR.unit)}`);
    });
  }
  lines.push(`Extended dry spells: ${events.dry_spells.length} period(s) of at least 14 consecutive days below 1 mm/day.`);
  events.dry_spells.forEach(spell => {
    lines.push(`  ${spell.start} to ${spell.end}: ${spell.days} days`);
  });

  lines.push("", "LOCATION COMPARISONS");
  report.comparisons.forEach(entry => {
    const rainfall = entry.summary.PRECTOTCORR;
    const temperature = entry.summary.T2M;
    const rainfallEvents = entry.rainfall_events;
    const threshold = rainfallEvents.threshold === null
      ? "not estimated"
      : reportNumber(rainfallEvents.threshold, entry.parameters.PRECTOTCORR.unit);
    lines.push(
      `${entry.location_name} (${entry.location.latitude}, ${entry.location.longitude}):`,
      `  Mean daily precipitation: ${reportNumber(rainfall.mean, entry.parameters.PRECTOTCORR.unit)}; mean air temperature: ${reportNumber(temperature.mean, entry.parameters.T2M.unit)}.`,
      `  Valid daily records: ${rainfall.valid_count}; high-rainfall screen: ${rainfallEvents.high_rain_days.length} day(s), threshold ${threshold}; extended dry spells: ${rainfallEvents.dry_spells.length}.`
    );
  });

  lines.push("", "METHODS AND LIMITATIONS");
  report.method_notes.forEach(note => lines.push(`- ${note}`));
  lines.push(
    "- Location comparisons are point samples, not district or region-wide averages.",
    "- Rainfall event screens are exploratory signals, not confirmation of floods, drought impacts or their causes. Daily gridded data cannot establish short-duration rainfall intensity or local impacts.",
    "- This concise report omits the full daily observation rows to remain readable; consult the listed data source for the underlying time series."
  );
  return lines.join("\n");
}

function downloadReport() {
  if (!currentData) return;
  const currentKey = `${currentData.location.latitude},${currentData.location.longitude}`;
  const primaryName = places[currentKey] || "Selected point";
  const comparisons = currentComparisons.length > 0
    ? currentComparisons
    : [{ name: primaryName, data: currentData, events: currentRainfallEvents }];
  const report = {
    generated_at: new Date().toISOString(),
    primary_location_name: primaryName,
    location: currentData.location,
    period: currentData.period,
    research_brief: $("research-brief-text").textContent,
    sources: [currentData.source, ...(currentData.modis ? [currentData.modis.source] : [])],
    parameters: currentData.parameters,
    summary: currentData.summary,
    analysis: currentData.analysis,
    research_events: currentRainfallEvents,
    comparisons: comparisons.map(entry => ({
      location_name: entry.name,
      location: entry.data.location,
      parameters: entry.data.parameters,
      summary: entry.data.summary,
      rainfall_events: entry.events
    })),
    method_notes: [
      currentData.method_note,
      ...(currentData.modis ? [currentData.modis.method_note] : [])
    ]
  };
  const text = formatEvidenceReport(report);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `earthsignal-report-${currentData.period.start}-to-${currentData.period.end}.txt`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

$("load").addEventListener("click", loadData);
$("metric").addEventListener("change", drawChart);
$("load-modis").addEventListener("click", loadModis);
$("download-report").addEventListener("click", downloadReport);
$("compare-locations").addEventListener("click", compareLocations);
$("research-location-search-button").addEventListener("click", searchResearchLocations);
$("comparison-location-search-button").addEventListener("click", searchComparisonLocations);
renderSelectedComparisonLocations();
$("research-location-query").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchResearchLocations();
  }
});
$("comparison-location-query").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchComparisonLocations();
  }
});
$("event-filter").addEventListener("change", () => {
  if (currentRainfallEvents && currentData) {
    renderRainfallEvents(currentRainfallEvents, currentData.parameters.PRECTOTCORR.unit);
  }
});
$("place").addEventListener("change", () => {
  const name = places[$("place").value];
  clearComparisonLocations();
  updateComparisonSearchCountry(placeCountries[$("place").value]);
  if (name) {
    $("research-location-status").className = "location-search-status";
    $("research-location-status").textContent = `Selected ${name}. Load NASA data to retrieve its observations.`;
  }
  if (name && !currentData) $("place-title").textContent = name;
  if (currentData) {
    currentComparisons = [];
    $("comparison-results").hidden = true;
    $("comparison-status").textContent = "Load NASA POWER data for the newly selected location before comparing.";
    $("status").textContent = "Location changed. Load NASA data to refresh the results.";
  }
});
["start", "end"].forEach(id => {
  $(id).addEventListener("change", () => {
    if (!currentData) return;
    currentComparisons = [];
    $("comparison-results").hidden = true;
    $("comparison-status").textContent = "Load NASA POWER data for the selected date range before comparing.";
    $("status").textContent = "Date range changed. Load NASA data to refresh the results.";
  });
});
