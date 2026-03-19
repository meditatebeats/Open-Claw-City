(function () {
  const form = document.getElementById("manifest-form");
  const output = document.getElementById("manifest-output");
  const input = document.getElementById("city-url");
  const liveSource = document.getElementById("live-source");
  const liveStatNodes = document.querySelectorAll("[data-live-stat]");

  if (!form || !output || !input || !liveSource) {
    return;
  }

  const render = (value) => {
    output.textContent = value;
  };

  const setLiveStat = (key, value) => {
    const target = document.querySelector(`[data-live-stat="${key}"]`);
    if (!target) {
      return;
    }
    target.textContent = String(value);
  };

  const clearLiveStats = () => {
    liveStatNodes.forEach((node) => {
      node.textContent = "-";
    });
  };

  const normalizeBaseUrl = (rawBase) => {
    const parsed = new URL(rawBase);
    return parsed.toString().replace(/\/$/, "");
  };

  const fetchJson = async (url) => {
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" }
    });
    const bodyText = await response.text();
    let parsed = bodyText;
    try {
      parsed = JSON.parse(bodyText);
    } catch {
      // Keep text response as-is.
    }
    return {
      ok: response.ok,
      status: response.status,
      parsed
    };
  };

  const checkCity = async (base) => {
    const manifestUrl = `${base}/city/manifest`;
    const statsUrl = `${base}/city/stats`;
    render(`Checking ${manifestUrl} and ${statsUrl} ...`);

    try {
      const [manifestResult, statsResult] = await Promise.all([fetchJson(manifestUrl), fetchJson(statsUrl)]);

      const payload = {
        manifest: {
          status: manifestResult.status,
          ok: manifestResult.ok,
          data: manifestResult.parsed
        },
        stats: {
          status: statsResult.status,
          ok: statsResult.ok,
          data: statsResult.parsed
        }
      };
      render(JSON.stringify(payload, null, 2));

      if (manifestResult.ok && statsResult.ok && typeof statsResult.parsed === "object" && statsResult.parsed) {
        const statsData = statsResult.parsed;
        setLiveStat("registered_agents", statsData.registered_agents);
        setLiveStat("institution_count", statsData.institution_count);
        setLiveStat("employed_agents", statsData.employed_agents);
        setLiveStat("occupied_parcels", statsData.occupied_parcels);
        setLiveStat("payroll_volume", statsData.payroll_volume);
        setLiveStat("treasury_balance", statsData.treasury_balance);

        const manifestData = manifestResult.parsed;
        const mode =
          manifestData && typeof manifestData === "object" && "enrollment_mode" in manifestData
            ? manifestData.enrollment_mode
            : "unknown";
        liveSource.textContent = `Connected to ${base} | enrollment_mode=${mode} | updated ${new Date().toLocaleTimeString()}`;
      } else {
        clearLiveStats();
        liveSource.textContent = `Unable to load live stats from ${base}. Check API health/CORS and retry.`;
      }
    } catch (error) {
      clearLiveStats();
      liveSource.textContent = `Request failed for ${base}: ${error.message}`;
      render(`Request failed: ${error.message}`);
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const rawBase = input.value.trim();
    if (!rawBase) {
      render("Please enter a valid URL.");
      return;
    }

    try {
      const base = normalizeBaseUrl(rawBase);
      await checkCity(base);
    } catch {
      clearLiveStats();
      liveSource.textContent = "Invalid URL. Example: https://city-api.example.com";
      render("URL format is invalid. Example: https://city-api.example.com");
    }
  });
})();
