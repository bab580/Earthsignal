(() => {
  const $ = (id) => document.getElementById(id);
  const storageKey = "earthsignal-farm-profile-v1";
  const t = (key) => window.EarthSignalFarmerI18n?.text(key) || key;
  const format = (key, values) => window.EarthSignalFarmerI18n?.format(key, values) || t(key);
  let refreshing = false;
  let weatherLocation = null;
  let weatherData = null;
  let weatherRequestId = 0;
  let latestSensorReading = null;
  let latestSensorFresh = false;

  function profile() {
    return {
      name: $("farm-name").value.trim(),
      location: $("farm-location").value.trim(),
      crop: $("farm-crop").value,
      device_id: $("farm-device").value.trim(),
      weather_location: weatherLocation
    };
  }

  window.earthSignalFarmLocation = () => weatherLocation;
  document.addEventListener("earthsignal-language-change", () => {
    if (weatherData) renderWeather(weatherData);
    renderReading(latestSensorReading ? { reading: latestSensorReading } : null);
    renderAlerts();
  });

  function persistProfile() {
    localStorage.setItem(storageKey, JSON.stringify(profile()));
  }

  function loadProfile() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      $("farm-name").value = saved.name || "";
      $("farm-location").value = saved.location || "Lira, Uganda";
      $("farm-crop").value = saved.crop || "Maize";
      $("farm-device").value = saved.device_id || "soilsense-01";
      const location = saved.weather_location;
      if (location && Number.isFinite(Number(location.latitude)) && Number.isFinite(Number(location.longitude))) {
        const savedLocationName = String(location.name || "");
        if (!saved.location || saved.location.trim().toLocaleLowerCase() === savedLocationName.trim().toLocaleLowerCase()) {
          weatherLocation = {
            name: savedLocationName || saved.location || "Lira, Uganda",
            latitude: Number(location.latitude),
            longitude: Number(location.longitude)
          };
        }
      } else if (!saved.location) {
        weatherLocation = {
          name: "Lira, Uganda",
          latitude: 2.2499,
          longitude: 32.8998
        };
        $("farm-location").value = weatherLocation.name;
      }

      if (weatherLocation) {
        $("farm-location").value = saved.location || weatherLocation.name;
        $("weather-selected-location").textContent = `Forecast location: ${weatherLocation.name}`;
        $("weather-selected-location").hidden = false;
        $("refresh-weather").disabled = false;
      } else {
        $("weather-selected-location").hidden = true;
        $("refresh-weather").disabled = true;
      }
    } catch (error) {
      setConnection(false, `Could not load saved farm details: ${error.message}`);
    }
  }

  function weatherLocationLabel(location) {
    return [location.name, location.admin1, location.country]
      .filter((part, index, parts) => part && parts.indexOf(part) === index)
      .join(", ");
  }

  function weatherStatus(message, isError = false) {
    $("weather-status").textContent = message;
    $("weather-status").classList.toggle("error", isError);
  }

  function locationSearchStatus(message, isError = false) {
    $("weather-location-status").textContent = message;
    $("weather-location-status").classList.toggle("error", isError);
  }

  async function findFarmLocation() {
    const query = $("farm-location").value.trim();
    const resultsElement = $("weather-location-results");
    resultsElement.replaceChildren();
    resultsElement.hidden = true;
    if (query.length < 2) {
      locationSearchStatus("Enter at least two characters to find a farm location.", true);
      return;
    }

    const button = $("find-farm-location");
    button.disabled = true;
    locationSearchStatus("Finding the farm location…");
    try {
      const response = await fetch(earthSignalApiUrl(`/api/weather/locations?query=${encodeURIComponent(query)}`));
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not find the farm location.");
      const locations = Array.isArray(payload.results) ? payload.results : [];
      if (locations.length === 0) {
        locationSearchStatus("No matching places found. Try adding a nearby city or country name.");
        return;
      }
      locations.forEach(location => {
        const option = document.createElement("button");
        option.type = "button";
        option.className = "location-search-option";
        option.textContent =
          `${weatherLocationLabel(location)} (${Number(location.latitude).toFixed(4)}, ${Number(location.longitude).toFixed(4)})`;
        option.addEventListener("click", () => selectWeatherLocation(location));
        resultsElement.append(option);
      });
      resultsElement.hidden = false;
      locationSearchStatus(`${locations.length} matching place${locations.length === 1 ? "" : "s"} found. Select your farm location to load its weather.`);
    } catch (error) {
      locationSearchStatus(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  function selectWeatherLocation(location) {
    weatherLocation = {
      name: weatherLocationLabel(location),
      latitude: Number(location.latitude),
      longitude: Number(location.longitude)
    };
    $("farm-location").value = weatherLocation.name;
    $("weather-selected-location").textContent =
      `Forecast location: ${weatherLocation.name} (${weatherLocation.latitude.toFixed(4)}, ${weatherLocation.longitude.toFixed(4)})`;
    $("weather-selected-location").hidden = false;
    $("weather-location-results").replaceChildren();
    $("weather-location-results").hidden = true;
    $("refresh-weather").disabled = false;
    weatherData = null;
    $("weather-data").hidden = true;
    let saved = true;
    try {
      persistProfile();
    } catch (error) {
      saved = false;
      locationSearchStatus(`Location selected, but farm details could not be saved: ${error.message}`, true);
    }
    if (saved) locationSearchStatus("Location selected.");
    refreshWeather();
  }

  function formatWeatherNumber(value, unit, digits = 1) {
    const number = Number(value);
    return value === null || value === undefined || !Number.isFinite(number)
      ? "—"
      : `${number.toLocaleString("en", { maximumFractionDigits: digits })} ${unit}`;
  }

  function weatherCondition(code) {
    const groups = [
      [[0], "conditionClear"],
      [[1], "conditionMainlyClear"],
      [[2], "conditionPartlyCloudy"],
      [[3], "conditionOvercast"],
      [[45, 48], "conditionFog"],
      [[51, 53, 55, 56, 57], "conditionDrizzle"],
      [[61, 63, 65, 66, 67], "conditionRain"],
      [[71, 73, 75, 77], "conditionSnow"],
      [[80, 81, 82], "conditionShowers"],
      [[85, 86], "conditionSnowShowers"],
      [[95, 96, 99], "conditionThunderstorm"]
    ];
    const match = groups.find(([codes]) => codes.includes(code));
    return t(match ? match[1] : "conditionUnavailable");
  }

  function forecastDateLabel(day) {
    return new Intl.DateTimeFormat("en", {
      weekday: "short",
      month: "short",
      day: "numeric",
      timeZone: "UTC"
    }).format(new Date(`${day}T12:00:00Z`));
  }

  function renderWeatherDays(elementId, days, emptyMessage, showProbability) {
    const container = $(elementId);
    container.replaceChildren();
    days.forEach(day => {
      const card = document.createElement("article");
      card.className = "weather-forecast-day";
      const date = document.createElement("strong");
      const condition = document.createElement("span");
      const temperature = document.createElement("small");
      const rain = document.createElement("small");
      date.textContent = forecastDateLabel(day.date);
      condition.textContent = weatherCondition(day.weather_code);
      temperature.textContent =
        `${formatWeatherNumber(day.temperature_max, weatherData.units.temperature)} / ${formatWeatherNumber(day.temperature_min, weatherData.units.temperature)}`;
      const probability = !showProbability || day.precipitation_probability_max === null || day.precipitation_probability_max === undefined
        ? ""
        : `; ${formatWeatherNumber(day.precipitation_probability_max, "%", 0)} ${t("chanceLabel")}`;
      rain.textContent = `${t("rainLabel")} ${formatWeatherNumber(day.precipitation_mm, weatherData.units.precipitation)}${probability}`;
      card.append(date, condition, temperature, rain);
      container.append(card);
    });
    if (days.length === 0) container.textContent = emptyMessage;
  }

  function renderWeather(data) {
    const temperatureUnit = data.units.temperature;
    const precipitationUnit = data.units.precipitation;
    const windUnit = data.units.wind_speed;
    const current = data.current;
    $("weather-condition").textContent = weatherCondition(current.weather_code);
    $("weather-observed-at").textContent = current.time
      ? `${t("observedLabel")} ${new Date(current.time).toLocaleString()}`
      : t("observationTimeUnavailable");
    $("weather-temperature").textContent = formatWeatherNumber(current.temperature, temperatureUnit);
    $("weather-apparent").textContent = formatWeatherNumber(current.apparent_temperature, temperatureUnit);
    $("weather-humidity").textContent = formatWeatherNumber(current.relative_humidity, "%", 0);
    $("weather-current-rain").textContent = formatWeatherNumber(current.precipitation_mm, precipitationUnit);
    $("weather-wind").textContent = formatWeatherNumber(current.wind_speed, windUnit);

    renderWeatherDays("weather-recent", data.recent_days, t("recentWeatherUnavailable"), false);
    renderWeatherDays("weather-forecast", data.forecast, t("forecastUnavailable"), true);

    const rainfallElement = $("rainfall-history");
    rainfallElement.replaceChildren();
    const history = data.rainfall_history;
    const maximum = Math.max(0, ...history.map(month => Number(month.precipitation_mm) || 0));
    history.forEach(month => {
      const row = document.createElement("div");
      row.className = "rainfall-month-row";
      const label = document.createElement("span");
      const bar = document.createElement("div");
      const fill = document.createElement("span");
      const total = document.createElement("span");
      const coverage = document.createElement("small");
      label.textContent = month.month;
      bar.className = "rainfall-month-bar";
      bar.setAttribute("aria-hidden", "true");
      const amount = Number(month.precipitation_mm);
      fill.style.width = Number.isFinite(amount) && maximum > 0 ? `${Math.max(1, amount / maximum * 100)}%` : "0%";
      bar.append(fill);
      total.className = "rainfall-month-total";
      total.textContent = formatWeatherNumber(month.precipitation_mm, precipitationUnit);
      coverage.className = "rainfall-month-coverage";
      coverage.textContent = `${month.valid_days}/${month.days_in_month} ${t("rainCoverage")}`;
      row.append(label, bar, total, coverage);
      rainfallElement.append(row);
    });
    $("weather-data").hidden = false;
    $("weather-status").textContent = `${t("updatedLabel")} ${new Date(data.retrieved_at).toLocaleTimeString()} · ${data.location.timezone || "local time zone"}`;
    $("weather-status").classList.remove("error");
    renderFarmContext();
  }

  async function refreshWeather() {
    if (!weatherLocation) {
      weatherStatus("Find and select your farm location to load its weather.");
      return;
    }
    const requestId = ++weatherRequestId;
    const button = $("refresh-weather");
    button.disabled = true;
    weatherStatus(`Loading weather for ${weatherLocation.name}…`);
    try {
      const query = new URLSearchParams({
        latitude: String(weatherLocation.latitude),
        longitude: String(weatherLocation.longitude)
      });
      const response = await fetch(earthSignalApiUrl(`/api/weather?${query}`), { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not retrieve weather data.");
      if (requestId !== weatherRequestId) return;
      weatherData = payload;
      renderWeather(payload);
    } catch (error) {
      if (requestId === weatherRequestId) weatherStatus(error.message, true);
    } finally {
      if (requestId === weatherRequestId) button.disabled = false;
    }
  }

  function renderFarmContext() {
    const crop = $("farm-crop").value;
    const planting = $("planting-guidance");
    const irrigation = $("irrigation-guidance");
    if (!weatherData) {
      planting.textContent = t("weatherContextWait");
      irrigation.textContent = latestSensorReading
        ? `${t("soilConnection")}: ${String(latestSensorReading.status).toUpperCase()}. ${t("checkProbeBeforeIrrigation")}`
        : t("irrigationWait");
      return;
    }

    const forecast = weatherData.forecast;
    const nextSevenDays = forecast.reduce((total, day) => total + (Number(day.precipitation_mm) || 0), 0);
    const nextThreeDays = forecast.slice(0, 3).reduce((total, day) => total + (Number(day.precipitation_mm) || 0), 0);
    const wettestMonth = weatherData.rainfall_history
      .filter(month => month.precipitation_mm !== null)
      .reduce((wettest, month) => !wettest || month.precipitation_mm > wettest.precipitation_mm ? month : wettest, null);
    const recentDrySpell = weatherData.recent_dry_spell;
    const drySpellContext = recentDrySpell.days >= 14
      ? format("drySpellSummary", { days: recentDrySpell.days, date: recentDrySpell.as_of })
      : format("noDrySpellSummary", { date: recentDrySpell.as_of || "date unavailable" });
    const wettestContext = wettestMonth
      ? format("wettestMonthSummary", {
        month: wettestMonth.month,
        rain: formatWeatherNumber(wettestMonth.precipitation_mm, weatherData.units.precipitation)
      })
      : "";
    planting.textContent = [
      format("plantingSummary", {
        crop,
        rain: formatWeatherNumber(nextSevenDays, weatherData.units.precipitation)
      }),
      wettestContext,
      drySpellContext,
      t("plantingCaveat")
    ].filter(Boolean).join(" ");

    if (!latestSensorReading) {
      irrigation.textContent = format("noRecentSensorSummary", {
        rain: formatWeatherNumber(nextThreeDays, weatherData.units.precipitation)
      });
    } else {
      irrigation.textContent = format("sensorSummary", {
        status: String(latestSensorReading.status).toUpperCase(),
        moisture: formatWeatherNumber(latestSensorReading.moisture, "%"),
        rain: formatWeatherNumber(nextThreeDays, weatherData.units.precipitation)
      });
    }
  }

  function renderAlerts() {
    const alerts = [];
    if (!latestSensorReading) {
      alerts.push({ text: t("noSensorForAlert"), type: "error" });
    } else if (!latestSensorFresh) {
      alerts.push({ text: t("staleSensorForAlert"), type: "error" });
    } else if (String(latestSensorReading.status).toUpperCase() === "DRY") {
      alerts.push({ text: t("drySensorForAlert"), type: "warning" });
    }

    if (weatherData) {
      const drySpell = weatherData.recent_dry_spell;
      if (drySpell.days >= 14) {
        alerts.push({
          text: format("drySpellAlert", { days: drySpell.days, date: drySpell.as_of }),
          type: "warning"
        });
      }
      weatherData.forecast.filter(day => day.precipitation_probability_max >= 70).slice(0, 3).forEach(day => {
        alerts.push({
          text: format("rainForecastAlert", {
            date: forecastDateLabel(day.date),
            chance: formatWeatherNumber(day.precipitation_probability_max, "%", 0)
          }),
          type: "warning"
        });
      });
    }

    const list = $("farmer-alert-list");
    list.replaceChildren();
    if (alerts.length === 0) {
      const item = document.createElement("li");
      item.textContent = weatherData ? t("noCurrentAlerts") : t("noWeatherAlerts");
      list.append(item);
    } else {
      alerts.forEach(alert => {
        const item = document.createElement("li");
        item.className = `alert-${alert.type}`;
        item.textContent = alert.text;
        list.append(item);
      });
    }
  }

  function setConnection(online, message) {
    $("farmer-connection").textContent = online ? t("connectionReporting") : t("connectionWaiting");
    $("farmer-connection").classList.toggle("connected", online);
    $("sensor-dot").classList.toggle("online", online);
    $("sensor-status-title").textContent = online ? t("sensorConnected") : t("sensorWaiting");
    $("sensor-status-message").textContent = message;
  }

  function renderReading(data) {
    if (!data || !data.reading) {
      latestSensorReading = null;
      latestSensorFresh = false;
      $("farmer-moisture").textContent = "—";
      $("farmer-raw").textContent = "—";
      $("farmer-updated").textContent = "—";
      $("farmer-age").textContent = t("noSensorReading");
      $("farmer-moisture-status").textContent = t("waitingSensor");
      $("moisture-bar").style.width = "0%";
      $("moisture-bar").parentElement.setAttribute("aria-valuenow", "0");
      setConnection(false, t("noSensorMessage"));
      renderFarmContext();
      renderAlerts();
      return;
    }

    const reading = data.reading;
    const timestamp = Date.parse(reading.recorded_at);
    const moisture = Number(reading.moisture);
    const raw = Number(reading.raw);
    if (!Number.isFinite(timestamp) || !Number.isFinite(moisture) || !Number.isFinite(raw)) {
      latestSensorReading = null;
      latestSensorFresh = false;
      setConnection(false, t("invalidReadingMessage"));
      renderFarmContext();
      renderAlerts();
      return;
    }

    latestSensorReading = reading;
    const age = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
    const fresh = age <= 180;
    latestSensorFresh = fresh;
    const boundedMoisture = Math.max(0, Math.min(100, moisture));
    $("farmer-moisture").textContent = `${moisture.toFixed(1)}%`;
    $("farmer-raw").textContent = String(raw);
    $("farmer-updated").textContent = new Date(timestamp).toLocaleTimeString();
    $("farmer-age").textContent = age < 60 ? `${age}s ago` : `${Math.floor(age / 60)}m ago`;
    $("farmer-moisture-status").textContent = String(reading.status || "UNKNOWN").toUpperCase();
    $("moisture-bar").style.width = `${boundedMoisture}%`;
    $("moisture-bar").parentElement.setAttribute("aria-valuenow", String(boundedMoisture));
    setConnection(
      fresh,
      fresh
        ? format("latestReadingMessage", { device: reading.device_id })
        : format("staleReadingMessage", { minutes: Math.floor(age / 60) })
    );
    renderFarmContext();
    renderAlerts();
  }

  async function refresh() {
    if (refreshing) return;
    const deviceId = $("farm-device").value.trim();
    if (!deviceId) {
      setConnection(false, t("emptyDeviceIdMessage"));
      return;
    }

    refreshing = true;
    try {
      const response = await fetch(earthSignalApiUrl(`/api/sensors/latest?device_id=${encodeURIComponent(deviceId)}`), {
        cache: "no-store"
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not retrieve sensor readings.");
      renderReading(payload);
    } catch (error) {
      setConnection(false, `${error.message} Check that the EarthSignal backend is running.`);
      latestSensorFresh = false;
      renderFarmContext();
      renderAlerts();
    } finally {
      refreshing = false;
    }
  }

  function saveFarm() {
    const farm = profile();
    if (!farm.device_id) {
      setConnection(false, "Enter a device ID before saving the farm profile.");
      return;
    }

    try {
      persistProfile();
      $("sensor-status-message").textContent = "Farm details saved in this browser. Sensor readings will appear when the ESP32 sends data using the same device ID.";
      refresh();
      if (!weatherLocation || $("farm-location").value.trim().toLocaleLowerCase() !== weatherLocation.name.trim().toLocaleLowerCase()) {
        findFarmLocation();
      }
    } catch (error) {
      setConnection(false, `Could not save farm details in this browser: ${error.message}`);
    }
  }

  document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const page = link.dataset.page;
      $("research-page").hidden = page !== "research";
      $("farmer-page").hidden = page !== "farmer";
      $("experiments-page").hidden = page !== "experiments";
      document.querySelectorAll(".nav-link").forEach((item) => {
        item.classList.toggle("active", item === link);
      });
      if (page === "farmer") refresh();
      history.replaceState(null, "", `#${page}`);
    });
  });

  $("save-farm").addEventListener("click", saveFarm);
  $("refresh-sensor").addEventListener("click", refresh);
  $("find-farm-location").addEventListener("click", findFarmLocation);
  $("farm-location").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      findFarmLocation();
    }
  });
  $("refresh-weather").addEventListener("click", refreshWeather);
  $("farm-crop").addEventListener("change", () => {
    renderFarmContext();
    try {
      persistProfile();
    } catch (error) {
      weatherStatus(`Crop selection changed, but farm details could not be saved: ${error.message}`, true);
    }
  });
  $("farm-location").addEventListener("input", () => {
    $("weather-location-results").replaceChildren();
    $("weather-location-results").hidden = true;
    if (!weatherLocation || $("farm-location").value.trim().toLocaleLowerCase() !== weatherLocation.name.trim().toLocaleLowerCase()) {
      locationSearchStatus("Find and select this farm location to update the forecast.");
    }
  });
  loadProfile();
  renderFarmContext();
  renderAlerts();
  if (weatherLocation) refreshWeather();
  else if ($("farm-location").value.trim()) findFarmLocation();
  if (location.hash === "#farmer" || location.hash === "#experiments" || location.hash === "#research") {
    const page = location.hash === "#farmer"
      ? "farmer"
      : location.hash === "#research" ? "research" : "experiments";
    $("research-page").hidden = page !== "research";
    $("farmer-page").hidden = page !== "farmer";
    $("experiments-page").hidden = page !== "experiments";
    document.querySelectorAll(".nav-link").forEach((item) => {
      item.classList.toggle("active", item.dataset.page === page);
    });
  }
  refresh();
  setInterval(() => {
    if (!$("farmer-page").hidden) refresh();
  }, 10000);
  setInterval(() => {
    if (!$("farmer-page").hidden && weatherLocation) refreshWeather();
  }, 30 * 60 * 1000);
})();
