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
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  let activeLayer = null;
  let activePopup = null;
  let activeGeojsonLayer = null;
  let activeBoundaryLevel = "nta";
  const geojsonByLevel = new Map();
  const renderedLayerByLevel = new Map();
  const featureLayerByLevel = new Map();

  function setStatus(message) {
    statusElement.textContent = message || "";
  }

  function getFillColor(score) {
    if (score <= 3) {
      return "#dc2626";
    }
    if (score <= 6) {
      return "#eab308";
    }
    return "#16a34a";
  }

  function baseStyle(feature) {
    return {
      color: "#334155",
      weight: 1.2,
      fillColor: getFillColor(feature.properties.placeholder_score),
      fillOpacity: 0.62,
    };
  }

  function renderPanel(feature) {
    const props = feature.properties;
    const issues = props.top_issues
      .map((issue) => `<li>${issue}</li>`)
      .join("");

    panelElement.innerHTML = `
      <h2>${props.nta_name}</h2>
      <p><strong>Borough:</strong> ${props.borough}</p>
      <p><strong>Livability Score:</strong> ${Number(props.placeholder_score).toFixed(1)} / 10</p>
      <p>${props.placeholder_summary}</p>
      <p><strong>Top Reported Issues:</strong></p>
      <ul>${issues}</ul>
    `;
    panelElement.classList.remove("hidden");
  }

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
