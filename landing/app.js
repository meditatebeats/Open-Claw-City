(function () {
  const form = document.getElementById("manifest-form");
  const output = document.getElementById("manifest-output");
  const input = document.getElementById("city-url");

  if (!form || !output || !input) {
    return;
  }

  const render = (value) => {
    output.textContent = value;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const rawBase = input.value.trim();
    if (!rawBase) {
      render("Please enter a valid URL.");
      return;
    }

    let base;
    try {
      base = new URL(rawBase).toString().replace(/\/$/, "");
    } catch {
      render("URL format is invalid. Example: https://city-api.example.com");
      return;
    }

    const manifestUrl = `${base}/city/manifest`;
    render(`Checking ${manifestUrl} ...`);

    try {
      const response = await fetch(manifestUrl, {
        method: "GET",
        headers: { Accept: "application/json" }
      });

      const bodyText = await response.text();
      let parsed = bodyText;

      try {
        parsed = JSON.parse(bodyText);
      } catch {
        // Keep text fallback.
      }

      const payload = {
        status: response.status,
        ok: response.ok,
        manifest: parsed
      };

      render(JSON.stringify(payload, null, 2));
    } catch (error) {
      render(`Request failed: ${error.message}`);
    }
  });
})();
