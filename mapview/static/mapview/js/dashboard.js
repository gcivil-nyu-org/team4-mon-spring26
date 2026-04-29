(function initializeDashboard() {
  const nycCenter = [40.7128, -74.006];
  const nycZoom = 10;
  const nycBounds = L.latLngBounds(
    [40.49612, -74.25559],
    [40.91553, -73.70001],
  );
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

  const map = L.map(mapElement, {
    maxBounds: nycBounds,
    maxBoundsViscosity: 1.0,
  }).setView(nycCenter, nycZoom);
  map.setMinZoom(map.getBoundsZoom(nycBounds));
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

  function setStatus(message, type = 'info') {
    statusElement.textContent = message || "";
    statusElement.className = `status-message status-${type}`;
    if (message) {
      statusElement.style.display = 'block';
    } else {
      statusElement.style.display = 'none';
    }
  }

  function showLoading(message = 'Loading...') {
    setStatus(message, 'loading');
  }

  function showError(message) {
    setStatus(message, 'error');
    setTimeout(() => setStatus(''), 5000);
  }

  function showSuccess(message) {
    setStatus(message, 'success');
    setTimeout(() => setStatus(''), 3000);
  }

  function getFillColor(score) {
    const thresholds = window.TENANTGUARD_CONFIG?.thresholds || [
      { max_score: 4, color: "#E33B1B" },
      { max_score: 6, color: "#F8FC19" },
      { max_score: 9, color: "#25D60B" },
      { max_score: 10, color: "#4A83FF" }
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

    let legendItems = "";
    thresholds.forEach(t => {
      legendItems += `
        <div class="legend-item">
          <div class="legend-color" style="background-color: ${t.color}"></div>
          <span>${t.name}</span>
        </div>
      `;
    });

    legendEl.innerHTML = `
      <button
        type="button"
        class="legend-toggle"
        id="legend-toggle"
        aria-expanded="false"
        aria-controls="legend-tooltip"
      >
        <span class="legend-toggle-title">Livability Index</span>
        <span class="legend-toggle-icon" aria-hidden="true">?</span>
      </button>
      <div class="legend-tooltip hidden" id="legend-tooltip" role="tooltip">
        <h4>Livability Risk</h4>
        <p class="legend-copy">
          Scores run from 0 to 10, where 10 is safest. We weight severe housing issues
          more heavily before converting the total into the neighborhood score.
        </p>
        <div class="legend-formula">
          <strong>Weighted issues:</strong> Class C x3, Class B x2, Class A x1, 311 complaints x1
        </div>
        <div class="legend-scale">
          ${legendItems}
        </div>
        <p class="legend-copy legend-copy-subtle">
          More complaints and violations lower the score. Fewer issues keep it closer to 10.
        </p>
      </div>
    `;

    const toggleButton = document.getElementById("legend-toggle");
    const tooltip = document.getElementById("legend-tooltip");
    if (!toggleButton || !tooltip) return;

    const closeLegend = () => {
      legendEl.classList.remove("expanded");
      tooltip.classList.add("hidden");
      toggleButton.setAttribute("aria-expanded", "false");
      const icon = toggleButton.querySelector(".legend-toggle-icon");
      if (icon) icon.textContent = "?";
    };

    const openLegend = () => {
      legendEl.classList.add("expanded");
      tooltip.classList.remove("hidden");
      toggleButton.setAttribute("aria-expanded", "true");
      const icon = toggleButton.querySelector(".legend-toggle-icon");
      if (icon) icon.textContent = "X";
    };

    toggleButton.addEventListener("click", (event) => {
      event.stopPropagation();
      if (legendEl.classList.contains("expanded")) {
        closeLegend();
      } else {
        openLegend();
      }
    });

    legendEl.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    document.addEventListener("click", () => {
      closeLegend();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeLegend();
      }
    });
  }
  
  async function fetchWithRetry(url, options = {}, retries = 3) {
    for (let i = 0; i < retries; i++) {
      try {
        const response = await fetch(url, options);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
      } catch (error) {
        if (i === retries - 1) throw error;
        await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
      }
    }
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
        <button class="panel-tab" data-tab="community">Community</button>
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
      <div class="tab-content hidden" id="tab-community">
        <p class="loading-text">Loading community info…</p>
      </div>
    `;
    panelElement.classList.remove("hidden");

    let communityLoaded = false;
    panelElement.querySelectorAll(".panel-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        switchTab(tab.dataset.tab);
        if (tab.dataset.tab === "community" && !communityLoaded) {
          communityLoaded = true;
          fetchCommunityPreview(ntaCode);
        }
      });
    });

    document.getElementById("panel-close-btn").addEventListener("click", () => {
      resetActiveSelection();
    });

    fetchViolations(ntaCode);
    fetchComplaints(ntaCode);
  }

  async function fetchCommunityPreview(ntaCode) {
    const container = document.getElementById("tab-community");
    container.innerHTML = "<div class='loading-spinner'><div class='spinner'></div><p>Loading community...</p></div>";
    try {
      const data = await fetchWithRetry(`/api/map/community-preview/${encodeURIComponent(ntaCode)}/`);
      if (!data.has_community) {
        container.innerHTML = `
          <p class="empty-text">No community set up for this neighborhood yet.</p>
          <p><a href="/communities/${encodeURIComponent(ntaCode)}/" style="color:#2563eb;">View forum</a></p>
        `;
        return;
      }
      let postsHtml = '';
      if (data.recent_posts && data.recent_posts.length > 0) {
        postsHtml = data.recent_posts.map(p => `
          <div style="padding:0.4rem 0;border-bottom:1px solid #f1f5f9;">
            <a href="/communities/${encodeURIComponent(ntaCode)}/post/${p.id}/" style="color:#2563eb;font-weight:500;font-size:0.88rem;">${p.title}</a>
            <div style="font-size:0.75rem;color:#64748b;">by ${p.author} · ${p.category_display} · ${p.reply_count} replies</div>
          </div>
        `).join('');
      } else {
        postsHtml = '<p class="empty-text">No posts yet.</p>';
      }
      container.innerHTML = `
        <p><strong>Members:</strong> ${data.member_count} &nbsp;|&nbsp; <strong>Posts:</strong> ${data.post_count}</p>
        ${data.is_member ? '<p style="color:#16a34a;font-size:0.85rem;font-weight:600;">You are a member of this community</p>' : ''}
        <p><strong>Recent Discussions:</strong></p>
        ${postsHtml}
        <p style="margin-top:0.5rem;"><a href="/communities/${encodeURIComponent(ntaCode)}/" class="btn btn-primary btn-sm" style="text-decoration:none;display:inline-block;padding:0.3rem 0.8rem;font-size:0.82rem;">Visit Community Forum</a></p>
      `;
    } catch (error) {
      console.error('Error fetching community preview:', error);
      container.innerHTML = `<p class="empty-text">Unable to load community data.</p>`;
    }
  }

  async function fetchViolations(ntaCode) {
    const container = document.getElementById("tab-violations");
    container.innerHTML = "<div class='loading-spinner'><div class='spinner'></div><p>Loading violations...</p></div>";
    
    try {
      const data = await fetchWithRetry(`/api/nta-violations/?nta_code=${encodeURIComponent(ntaCode)}&limit=200`);

      if (!data.violations || data.violations.length === 0) {
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
        <p class="data-count">${
          data.returned_count !== data.count
            ? `Showing ${data.returned_count} of ${data.count} violation${data.count !== 1 ? "s" : ""}`
            : `${data.count} violation${data.count !== 1 ? "s" : ""} found`
        }</p>
        <div class="data-list">${rows}</div>
      `;
    } catch (error) {
      console.error('Error fetching violations:', error);
      container.innerHTML = `
        <div class='error-message'>
          <p>⚠️ Unable to load violations</p>
          <p class='error-detail'>${error.message || 'Please try again later'}</p>
          <button onclick="location.reload()" class="retry-button">Retry</button>
        </div>
      `;
    }
  }

  async function fetchComplaints(ntaCode) {
    const container = document.getElementById("tab-complaints");
    container.innerHTML = "<div class='loading-spinner'><div class='spinner'></div><p>Loading complaints...</p></div>";
    
    try {
      const data = await fetchWithRetry(`/api/nta-complaints/?nta_code=${encodeURIComponent(ntaCode)}&limit=200`);

      if (!data.complaints || data.complaints.length === 0) {
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
        <p class="data-count">${
          data.returned_count !== data.count
            ? `Showing ${data.returned_count} of ${data.count} complaint${data.count !== 1 ? "s" : ""}`
            : `${data.count} complaint${data.count !== 1 ? "s" : ""} found`
        }</p>
        <div class="data-list">${rows}</div>
      `;
    } catch (error) {
      console.error('Error fetching complaints:', error);
      container.innerHTML = `
        <div class='error-message'>
          <p>⚠️ Unable to load complaints</p>
          <p class='error-detail'>${error.message || 'Please try again later'}</p>
          <button onclick="location.reload()" class="retry-button">Retry</button>
        </div>
      `;
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

  /* ---- My Community marker + Return button ------------------------------ */

  let myMarker = null;
  let myNtaCode = null;
  let utilityControls = null;
  let utilityControlsInner = null;

  function getUtilityControlsInner() {
    if (utilityControlsInner) return utilityControlsInner;

    utilityControls = L.control({ position: 'topright' });
    utilityControls.onAdd = function() {
      const outer = L.DomUtil.create('div', 'map-utility-controls');
      const inner = L.DomUtil.create('div', 'leaflet-bar map-utility-controls-inner', outer);
      L.DomEvent.disableClickPropagation(outer);
      utilityControlsInner = inner;
      return outer;
    };
    utilityControls.addTo(map);
    return utilityControlsInner;
  }

  async function loadMyMarker() {
    try {
      const data = await fetch('/api/map/my-marker/').then(r => r.json());
      if (!data.has_marker || !data.lat || !data.lng) return;
      myNtaCode = data.nta_code;

      const icon = L.divIcon({
        className: 'my-community-marker',
        html: '<div style="background:#2563eb;width:14px;height:14px;border-radius:50%;border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);"></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      });

      myMarker = L.marker([data.lat, data.lng], { icon, zIndexOffset: 1000 })
        .bindPopup(`<strong>My Home</strong><br/>${data.nta_name}<br/>Score: ${data.risk_score}/10<br/>${data.member_count} members · ${data.post_count} posts`)
        .addTo(map);

      const controlGroup = getUtilityControlsInner();
      const btn = document.createElement('a');
      btn.href = '#';
      btn.title = 'Return to My Community';
      btn.className = 'map-control-button map-control-button-home';
      btn.innerHTML = '&#127968;';
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (myMarker) {
          map.flyTo(myMarker.getLatLng(), 14, { duration: 0.8 });
          myMarker.openPopup();
        }
      });
      controlGroup.appendChild(btn);
    } catch (err) {
      // Silently fail — user may not be authenticated or verified
    }
  }

  /* ---- Community Activity Heatmap Layer --------------------------------- */

  let activityLayer = null;
  let activityVisible = false;

  async function loadActivityLayer() {
    try {
      const data = await fetch('/api/map/community-activity/').then(r => r.json());
      if (!data.communities || data.communities.length === 0) return;

      const maxActivity = Math.max(...data.communities.map(c => c.activity_score), 1);

      const controlGroup = getUtilityControlsInner();
      const btn = document.createElement('a');
      btn.href = '#';
      btn.id = 'activity-toggle';
      btn.title = 'Toggle Community Activity';
      btn.className = 'map-control-button map-control-button-activity';
      btn.innerHTML = '&#128293;';
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        toggleActivity(data.communities, maxActivity);
      });
      controlGroup.appendChild(btn);
    } catch (err) {
      // Silently fail
    }
  }

  function toggleActivity(communities, maxActivity) {
    if (activityVisible && activityLayer) {
      map.removeLayer(activityLayer);
      activityLayer = null;
      activityVisible = false;
      const btn = document.getElementById('activity-toggle');
      if (btn) btn.style.background = '#fff';
      return;
    }

    const circleMarkers = [];
    communities.forEach(c => {
      const layerMap = featureLayerByLevel.get('nta');
      if (!layerMap) return;
      const layer = layerMap.get(c.nta_code);
      if (!layer) return;
      const center = layer.getBounds().getCenter();
      const intensity = c.activity_score / maxActivity;
      const radius = 8 + intensity * 25;
      const cm = L.circleMarker(center, {
        radius: radius,
        fillColor: '#8b5cf6',
        color: '#7c3aed',
        weight: 1,
        fillOpacity: 0.15 + intensity * 0.35,
        interactive: false,
      });
      circleMarkers.push(cm);
    });

    activityLayer = L.layerGroup(circleMarkers).addTo(map);
    activityVisible = true;
    const btn = document.getElementById('activity-toggle');
    if (btn) btn.style.background = '#ede9fe';
  }

  /* ---- Recency Label ---------------------------------------------------- */

  async function loadRecencyLabel() {
    try {
      const data = await fetch('/api/map/recency-label/').then(r => r.json());
      if (data.label && data.recency_window !== 'all') {
        const legendEl = document.getElementById('map-legend');
        if (legendEl) {
          const tag = document.createElement('div');
          tag.style.cssText = 'font-size:0.72rem;color:#64748b;margin-top:0.4rem;text-align:center;';
          tag.textContent = 'Data window: ' + data.label;
          legendEl.appendChild(tag);
        }
      }
    } catch (err) {
      // Silently fail
    }
  }

  /* ---- Init ------------------------------------------------------------- */

  loadInitialLayer().then(() => {
    loadMyMarker();
    loadActivityLayer();
    loadRecencyLabel();
  }).catch((error) => {
    setStatus(error.message);
  });
})();
