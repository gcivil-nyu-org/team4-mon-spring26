(function initializeDashboard() {
  const nycCenter = [40.7128, -74.006];
  const nycZoom = 10;
  const layerOrder = ["nta", "mid", "block"];
  const minZoomByLevel = {
    nta: 0,
    mid: 13,
    block: 16,
  };
  const selectedStyle = {
    weight: 3.5,
    color: "#0f172a",
    fillOpacity: 0.78,
  };

  const mapElement = document.getElementById("map");
  const panelElement = document.getElementById("info-panel");
  const statusElement = document.getElementById("status-message");
  const searchForm = document.getElementById("address-search-form");
  const searchInput = document.getElementById("address-search-input");
  const searchButton = searchForm.querySelector("button");

  const map = L.map(mapElement).setView(nycCenter, nycZoom);
  const mapboxToken = window.TENANTGUARD_CONFIG && window.TENANTGUARD_CONFIG.mapboxAccessToken;
  if (mapboxToken) {
    L.tileLayer(`https://api.mapbox.com/styles/v1/mapbox/light-v11/tiles/{z}/{x}/{y}?access_token=${mapboxToken}`, {
      maxZoom: 19,
      attribution: '&copy; Mapbox',
      tileSize: 512,
      zoomOffset: -1
    }).addTo(map);
  } else {
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
  }

  let activeLayer = null;
  let activePopup = null;
  let activeGeojsonLayer = null;
  let activeBoundaryLevel = "nta";
  const geojsonByLevel = new Map();
  const renderedLayerByLevel = new Map();
  const featureLayerByLevel = new Map();

  const markers = L.markerClusterGroup({
    maxClusterRadius: 40,
    spiderfyOnMaxZoom: true,
  });
  map.addLayer(markers);

  function setStatus(message) {
    statusElement.textContent = message || "";
  }

  function getFillColor(score) {
    const thresholds = window.TENANTGUARD_CONFIG?.thresholds || [
      { max_score: 5, color: "#dc2626" },
      { max_score: 7.5, color: "#eab308" },
      { max_score: 10, color: "#16a34a" }
    ];
    for (let t of thresholds) {
      if (score <= t.max_score) return t.color;
    }
    return thresholds[thresholds.length - 1].color;
  }

  function initLegend() {
    const legendEl = document.getElementById("map-legend");
    if (!legendEl) return;
    const thresholds = window.TENANTGUARD_CONFIG?.thresholds || [];
    
    let html = `<h4>Livability Risk</h4>`;
    thresholds.forEach(t => {
      html += `
        <div class="legend-item">
          <div class="legend-color" style="background-color: ${t.color}"></div>
          <span>${t.name}</span>
        </div>
      `;
    });
    legendEl.innerHTML = html;
  }
  
  initLegend();

  function baseStyle(feature) {
    return {
      color: "#334155",
      weight: 1.5,
      fillColor: getFillColor(feature.properties.placeholder_score),
      fillOpacity: 0.82,
    };
  }

  /* ---- Tabbed info-panel ------------------------------------------------ */

  function switchTab(tabName) {
    panelElement.querySelectorAll(".panel-tab").forEach((t) => t.classList.remove("active"));
    panelElement.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));
    const btn = panelElement.querySelector(`[data-tab="${tabName}"]`);
    if (btn) btn.classList.add("active");
    const pane = document.getElementById(`tab-${tabName}`);
    if (pane) pane.classList.remove("hidden");
  }

  function renderPanel(feature) {
    const props = feature.properties;
    const ntaCode = props.nta_code;
    const issues = props.top_issues.map((issue) => `<li>${issue}</li>`).join("");

    markers.clearLayers();

    const extraStats =
      props.total_violations !== undefined
        ? `<p><strong>HPD Violations:</strong> ${props.total_violations} &nbsp;|&nbsp; <strong>311 Complaints:</strong> ${props.total_complaints}</p>`
        : "";

    panelElement.innerHTML = `
      <div class="panel-header">
        <h2>${props.nta_name}</h2>
        <button class="panel-close" id="panel-close-btn" title="Close">&times;</button>
      </div>
      <div class="panel-tabs">
        <button class="panel-tab active" data-tab="summary">Summary</button>
        <button class="panel-tab" data-tab="violations">Violations</button>
        <button class="panel-tab" data-tab="complaints">Complaints</button>
      </div>
      <div class="tab-content" id="tab-summary">
        <p><strong>Borough:</strong> ${props.borough}</p>
        <p><strong>Livability Score:</strong> ${Number(props.placeholder_score).toFixed(1)} / 10</p>
        ${extraStats}
        <p>${props.placeholder_summary}</p>
        <p><strong>Top Reported Issues:</strong></p>
        <ul>${issues}</ul>
      </div>
      <div class="tab-content hidden" id="tab-violations">
        <p class="loading-text">Loading HPD violations…</p>
      </div>
      <div class="tab-content hidden" id="tab-complaints">
        <p class="loading-text">Loading 311 complaints…</p>
      </div>
    `;
    panelElement.classList.remove("hidden");

    panelElement.querySelectorAll(".panel-tab").forEach((tab) => {
      tab.addEventListener("click", () => switchTab(tab.dataset.tab));
    });

    document.getElementById("panel-close-btn").addEventListener("click", () => {
      resetActiveSelection();
    });

    fetchViolations(ntaCode);
    fetchComplaints(ntaCode);
  }

  async function fetchViolations(ntaCode) {
    const container = document.getElementById("tab-violations");
    try {
      const resp = await fetch(`/api/nta-violations/?nta_code=${encodeURIComponent(ntaCode)}&limit=200`);
      const data = await resp.json();

      if (!resp.ok || !data.violations || data.violations.length === 0) {
        container.innerHTML = "<p class='empty-text'>No HPD violations found for this area.</p>";
        return;
      }

      const rows = data.violations
        .map(
          (v) => `
        <div class="data-card violation-${(v.violation_class || "").toLowerCase()}">
          <div class="data-card-header">
            <span class="badge badge-${(v.violation_class || "").toLowerCase()}">Class ${v.violation_class || "?"}</span>
            <span class="data-date">${v.inspection_date || "N/A"}</span>
          </div>
          <p class="data-address">${v.address || "Unknown address"}${v.apartment ? ", Apt " + v.apartment : ""}</p>
          <p class="data-desc">${v.nov_description || "No description available"}</p>
          <p class="data-status"><strong>Status:</strong> ${v.current_status || v.violation_status || "Unknown"}</p>
        </div>`
        )
        .join("");

      data.violations.forEach((v) => {
        if (v.latitude && v.longitude) {
          const m = L.circleMarker([v.latitude, v.longitude], {
            radius: 6,
            fillColor: "#dc2626",
            color: "#fff",
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
          });
          m.bindPopup(`<b>${v.address}</b><br/>Class ${v.violation_class} Violation<br/>${v.nov_description || ""}`);
          markers.addLayer(m);
        }
      });

      container.innerHTML = `
        <p class="data-count">${data.count} violation${data.count !== 1 ? "s" : ""} found</p>
        <div class="data-list">${rows}</div>
      `;
    } catch {
      container.innerHTML = "<p class='empty-text'>Failed to load violations.</p>";
    }
  }

  async function fetchComplaints(ntaCode) {
    const container = document.getElementById("tab-complaints");
    try {
      const resp = await fetch(`/api/nta-complaints/?nta_code=${encodeURIComponent(ntaCode)}&limit=200`);
      const data = await resp.json();

      if (!resp.ok || !data.complaints || data.complaints.length === 0) {
        container.innerHTML = "<p class='empty-text'>No 311 complaints found for this area.</p>";
        return;
      }

      const rows = data.complaints
        .map(
          (c) => `
        <div class="data-card">
          <div class="data-card-header">
            <span class="badge">${c.complaint_type || "Unknown"}</span>
            <span class="data-date">${c.created_date ? c.created_date.split("T")[0] : "N/A"}</span>
          </div>
          <p class="data-address">${c.incident_address || "No address"}</p>
          <p class="data-desc">${c.descriptor || "No details"}</p>
          <p class="data-status"><strong>Status:</strong> ${c.status || "Unknown"}</p>
        </div>`
        )
        .join("");

      data.complaints.forEach((c) => {
        if (c.latitude && c.longitude) {
          const m = L.circleMarker([c.latitude, c.longitude], {
            radius: 6,
            fillColor: "#eab308",
            color: "#fff",
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
          });
          m.bindPopup(`<b>${c.incident_address || "Address"}</b><br/>${c.complaint_type}<br/>${c.descriptor || ""}`);
          markers.addLayer(m);
        }
      });

      container.innerHTML = `
        <p class="data-count">${data.count} complaint${data.count !== 1 ? "s" : ""} found</p>
        <div class="data-list">${rows}</div>
      `;
    } catch {
      container.innerHTML = "<p class='empty-text'>Failed to load complaints.</p>";
    }
  }

  /* ---- Popup (hover / click tooltip on map) ----------------------------- */

  function popupHtml(feature) {
    const props = feature.properties;
    const issues = props.top_issues.map((issue) => `• ${issue}`).join("<br/>");
    return `
      <div>
        <strong>Neighborhood:</strong> ${props.nta_name}<br/>
        <strong>Livability Score:</strong> ${Number(props.placeholder_score).toFixed(1)} / 10<br/><br/>
        <strong>Top Reported Issues:</strong><br/>
        ${issues}
      </div>
    `;
  }

  function getFeatureKey(feature) {
    return feature.properties.cell_id || feature.properties.nta_code;
  }

  function getActiveLevelByZoom(zoom) {
    if (zoom >= minZoomByLevel.block) {
      return "block";
    }
    if (zoom >= minZoomByLevel.mid) {
      return "mid";
    }
    return "nta";
  }

  function resetActiveSelection() {
    if (activeLayer && activeGeojsonLayer) {
      activeGeojsonLayer.resetStyle(activeLayer);
    }
    activeLayer = null;
    if (activePopup) {
      map.closePopup(activePopup);
      activePopup = null;
    }
    panelElement.classList.add("hidden");
  }

  function selectLayer(layer, shouldPan = false) {
    if (activeLayer && activeLayer !== layer && activeGeojsonLayer) {
      activeGeojsonLayer.resetStyle(activeLayer);
    }

    activeLayer = layer;
    layer.setStyle(selectedStyle);
    layer.bringToFront();

    const center = layer.getBounds().getCenter();
    if (shouldPan) {
      map.flyTo(center, Math.max(map.getZoom(), 13), { duration: 0.8 });
    }

    if (activePopup) {
      map.closePopup(activePopup);
    }
    activePopup = L.popup({
      autoClose: true,
      closeButton: false,
      offset: [0, -10],
    })
      .setLatLng(center)
      .setContent(popupHtml(layer.feature))
      .openOn(map);

    renderPanel(layer.feature);
  }

  function onEachFeatureFactory(level) {
    const levelMap = featureLayerByLevel.get(level);
    return function onEachFeature(feature, layer) {
      levelMap.set(getFeatureKey(feature), layer);
      layer.on("mouseover", () => {
        if (layer !== activeLayer) {
          layer.setStyle({ weight: 2, fillOpacity: 0.74 });
        }
      });
      layer.on("mouseout", () => {
        if (layer !== activeLayer) {
          const layerGroup = renderedLayerByLevel.get(level);
          if (layerGroup) {
            layerGroup.resetStyle(layer);
          }
        }
      });
      layer.on("click", () => selectLayer(layer));
    };
  }

  function findContainingFeature(level, lng, lat) {
    const payload = geojsonByLevel.get(level);
    if (!payload) {
      return null;
    }
    const point = turf.point([lng, lat]);
    return payload.features.find((feature) => turf.booleanPointInPolygon(point, feature)) || null;
  }

  async function fetchBoundaryLevel(level) {
    if (geojsonByLevel.has(level)) {
      return geojsonByLevel.get(level);
    }
    const response = await fetch(`/api/boundaries/?level=${encodeURIComponent(level)}`);
    if (!response.ok) {
      throw new Error(`Unable to load boundary data for ${level} view.`);
    }
    const payload = await response.json();
    geojsonByLevel.set(level, payload);
    return payload;
  }

  async function mountBoundaryLevel(level) {
    if (renderedLayerByLevel.has(level)) {
      return renderedLayerByLevel.get(level);
    }
    const payload = await fetchBoundaryLevel(level);
    featureLayerByLevel.set(level, new Map());
    const layer = L.geoJSON(payload, {
      style: baseStyle,
      onEachFeature: onEachFeatureFactory(level),
    });
    renderedLayerByLevel.set(level, layer);
    return layer;
  }

  async function switchBoundaryLevel(level) {
    if (activeBoundaryLevel === level && activeGeojsonLayer) {
      return;
    }
    const nextLayer = await mountBoundaryLevel(level);
    resetActiveSelection();
    if (activeGeojsonLayer) {
      map.removeLayer(activeGeojsonLayer);
    }
    nextLayer.addTo(map);
    activeGeojsonLayer = nextLayer;
    activeBoundaryLevel = level;
  }

  async function ensureCorrectLayerForCurrentZoom() {
    const targetLevel = getActiveLevelByZoom(map.getZoom());
    if (targetLevel !== activeBoundaryLevel || !activeGeojsonLayer) {
      setStatus(`Loading ${targetLevel} boundaries...`);
      await switchBoundaryLevel(targetLevel);
      setStatus("Map loaded. Click a neighborhood or search an address.");
    }
  }

  async function loadInitialLayer() {
    setStatus("Loading NYC neighborhood boundaries...");
    await switchBoundaryLevel("nta");
    if (activeGeojsonLayer) {
      map.fitBounds(activeGeojsonLayer.getBounds(), { padding: [12, 12] });
    }
    setStatus("Map loaded. Click a neighborhood or search an address.");
  }

  async function findFeatureAcrossLevels(lng, lat) {
    const levelsToTry = [activeBoundaryLevel, ...layerOrder.filter((level) => level !== activeBoundaryLevel)];
    for (const level of levelsToTry) {
      const payload = geojsonByLevel.get(level) || (await fetchBoundaryLevel(level));
      if (!payload || !payload.features) {
        continue;
      }
      const feature = findContainingFeature(level, lng, lat);
      if (feature) {
        return { level, feature };
      }
    }
    return null;
  }

  async function selectFeature(level, feature) {
    await switchBoundaryLevel(level);
    const layerMap = featureLayerByLevel.get(level);
    if (!layerMap) {
      return false;
    }
    const layer = layerMap.get(getFeatureKey(feature));
    if (!layer) {
      return false;
    }
    layer.fire("click");
    return true;
  }

  map.on("zoomend", () => {
    ensureCorrectLayerForCurrentZoom().catch((error) => setStatus(error.message));
  });

  async function geocodeAddress(query) {
    const response = await fetch(`/api/geocode/?q=${encodeURIComponent(query)}`);
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Address lookup failed.");
    }
    return payload;
  }

  async function onSearchSubmit(event) {
    event.preventDefault();
    const query = searchInput.value.trim();
    if (!query) {
      return;
    }

    searchButton.disabled = true;
    setStatus("Searching address...");
    try {
      const result = await geocodeAddress(query);
      map.flyTo([result.lat, result.lng], 17, { duration: 1 });

      const match = await findFeatureAcrossLevels(result.lng, result.lat);
      if (!match) {
        setStatus(`Address found (${result.label}), but no matching boundary polygon.`);
        return;
      }

      const selected = await selectFeature(match.level, match.feature);
      if (!selected) {
        setStatus("Address matched, but map feature selection failed.");
        return;
      }

      setStatus(`Showing ${match.feature.properties.nta_name} for "${result.label}".`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      searchButton.disabled = false;
    }
  }

  searchForm.addEventListener("submit", onSearchSubmit);

  loadInitialLayer().catch((error) => {
    setStatus(error.message);
  });
})();
