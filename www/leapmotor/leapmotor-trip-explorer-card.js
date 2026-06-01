class LeapmotorTripExplorerCard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
  }

  setConfig(config) {
    this.config = {
      title: "Storico Viaggi",
      subtitle: "Anno, mese, giorno e dettaglio viaggi",
      url: "/local/leapmotor/trip_summary.json",
      maxHeight: "560px",
      ...config,
    };

    this.expanded = {
      years: new Set(),
      months: new Set(),
      days: new Set(),
    };

    this.selectedTripId = this.selectedTripId || null;

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }

    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          border-radius: 20px;
          overflow: hidden;
          background: var(--ha-card-background, var(--card-background-color));
          border: 1px solid var(--divider-color);
          box-shadow: none;
        }

        .card {
          padding: 20px;
        }

        .header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
          margin-bottom: 14px;
        }

        .title {
          font-size: 24px;
          font-weight: 500;
          color: var(--primary-text-color);
          line-height: 1.2;
        }

        .subtitle {
          margin-top: 6px;
          font-size: 15px;
          color: var(--secondary-text-color);
        }

        .refresh {
          border: 1px solid rgba(33,150,243,0.35);
          background: linear-gradient(135deg, rgba(33,150,243,0.18), rgba(33,150,243,0.04));
          color: var(--primary-text-color);
          padding: 8px 14px;
          border-radius: 14px;
          cursor: pointer;
          font-size: 13px;
        }

        .updated {
          color: var(--secondary-text-color);
          font-size: 12px;
          margin-bottom: 14px;
        }

        .scroll {
          overflow: auto;
          padding-right: 4px;
        }

        .content {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .row {
          display: grid;
          grid-template-columns: 26px minmax(120px, 1fr) auto;
          align-items: center;
          gap: 10px;
          padding: 12px 14px;
          border-radius: 16px;
          cursor: pointer;
          user-select: none;
          transition: background 0.15s ease, border 0.15s ease;
        }

        .row:hover {
          filter: brightness(1.08);
        }

        .year {
          background: linear-gradient(135deg, rgba(33,150,243,0.16), rgba(33,150,243,0.04));
          border: 1px solid rgba(33,150,243,0.28);
        }

        .month {
          background: linear-gradient(135deg, rgba(156,39,176,0.14), rgba(156,39,176,0.04));
          border: 1px solid rgba(156,39,176,0.25);
        }

        .day {
          background: linear-gradient(135deg, rgba(255,152,0,0.15), rgba(255,152,0,0.04));
          border: 1px solid rgba(255,152,0,0.27);
        }

        .arrow {
          color: var(--secondary-text-color);
          font-size: 16px;
          text-align: center;
        }

        .label {
          font-size: 15px;
          font-weight: 600;
          color: var(--primary-text-color);
        }

        .summary {
          color: var(--secondary-text-color);
          font-size: 13px;
          white-space: nowrap;
        }

        .children {
          margin-left: 22px;
          margin-top: 10px;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .table-wrap {
          margin-left: 22px;
          margin-top: 10px;
          border-radius: 16px;
          overflow-x: auto;
          border: 1px solid var(--divider-color);
          background: rgba(150,150,150,0.04);
        }

        table {
          width: 100%;
          min-width: 900px;
          border-collapse: collapse;
        }

        th {
          color: var(--secondary-text-color);
          font-size: 12px;
          font-weight: 600;
          text-align: left;
          padding: 11px 12px;
          border-bottom: 1px solid var(--divider-color);
          background: rgba(150,150,150,0.06);
          white-space: nowrap;
        }

        td {
          color: var(--primary-text-color);
          font-size: 13px;
          padding: 11px 12px;
          border-bottom: 1px solid rgba(150,150,150,0.12);
          white-space: nowrap;
        }

        tr:hover td {
          background: rgba(33,150,243,0.08);
        }

        .trip-row.selected td {
          background: rgba(33,150,243,0.13);
          border-top: 1px solid rgba(33,150,243,0.22);
          border-bottom: 1px solid rgba(33,150,243,0.22);
        }

        .trip-row.selected td:first-child {
          border-left: 3px solid rgba(33,150,243,0.85);
        }

        .track-btn {
          border: 1px solid rgba(33,150,243,0.35);
          background: linear-gradient(135deg, rgba(33,150,243,0.18), rgba(33,150,243,0.04));
          color: var(--primary-text-color);
          padding: 5px 8px;
          border-radius: 11px;
          cursor: pointer;
          font-size: 12px;
          white-space: nowrap;
          min-width: 72px;
        }

        .track-btn:hover {
          filter: brightness(1.12);
        }

        .track-btn.loading {
          opacity: 0.55;
          cursor: wait;
        }

        .track-overlay {
          position: fixed;
          inset: 28px;
          z-index: 9999;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(0,0,0,0.62);
          backdrop-filter: blur(8px);
        }

        .track-overlay.hidden {
          display: none;
        }

        .track-window {
          width: min(1280px, calc(100vw - 56px));
          height: min(760px, calc(100vh - 56px));
          background: var(--ha-card-background, var(--card-background-color));
          border: 1px solid var(--divider-color);
          border-radius: 22px;
          overflow: hidden;
          box-shadow: 0 20px 60px rgba(0,0,0,0.45);
          display: flex;
          flex-direction: column;
        }

        .track-header {
          height: 52px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 16px 0 18px;
          border-bottom: 1px solid var(--divider-color);
          color: var(--primary-text-color);
          font-size: 18px;
          font-weight: 600;
        }

        .track-close {
          border: none;
          background: transparent;
          color: var(--primary-text-color);
          font-size: 28px;
          line-height: 1;
          cursor: pointer;
          padding: 4px 8px;
          border-radius: 10px;
        }

        .track-close:hover {
          background: rgba(255,255,255,0.08);
        }

        .track-frame {
          width: 100%;
          flex: 1;
          border: 0;
          background: #111;
        }

        .empty,
        .error {
          color: var(--secondary-text-color);
          padding: 14px;
        }

        @media (max-width: 900px) {
          .row {
            grid-template-columns: 26px 1fr;
          }

          .summary {
            grid-column: 2;
            white-space: normal;
          }
        }
      </style>

      <ha-card>
        <div class="card">
          <div class="header">
            <div>
              <div class="title">${this.config.title}</div>
              <div class="subtitle">${this.config.subtitle}</div>
            </div>
            <button class="refresh">Aggiorna</button>
          </div>

          <div class="updated" id="updated"></div>

          <div class="scroll" style="max-height:${this.config.maxHeight}">
            <div id="content" class="content">Caricamento storico...</div>
          </div>
        </div>
      </ha-card>

      <div id="trackOverlay" class="track-overlay hidden">
        <div class="track-window">
          <div class="track-header">
            <div>Percorso viaggio</div>
            <button id="closeTrackOverlay" class="track-close">×</button>
          </div>
          <iframe id="trackMapFrame" class="track-frame"></iframe>
        </div>
      </div>
    `;

    this.shadowRoot.querySelector(".refresh").addEventListener("click", () => this.loadData());

    const closeTrackOverlay = this.shadowRoot.querySelector("#closeTrackOverlay");
    if (closeTrackOverlay) {
      closeTrackOverlay.addEventListener("click", () => this.closeTrackOverlay());
    }

    this.loadData();
  }

  async loadData() {
    const content = this.shadowRoot.querySelector("#content");
    const updated = this.shadowRoot.querySelector("#updated");

    try {
      const response = await fetch(`${this.config.url}?t=${Date.now()}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      this.data = await response.json();
      updated.textContent = `Aggiornato: ${this.data.generated_at || "N/D"}`;
      this.render();
    } catch (error) {
      content.innerHTML = `<div class="error">Errore lettura storico: ${error.message}</div>`;
    }
  }

  render() {
    const content = this.shadowRoot.querySelector("#content");
    const tree = this.data?.tree || {};
    const years = Object.keys(tree).sort((a, b) => Number(b) - Number(a));

    if (!years.length) {
      content.innerHTML = `<div class="empty">Nessun viaggio salvato</div>`;
      return;
    }

    content.innerHTML = years.map((year) => this.renderYear(year, tree[year])).join("");
    this.bindClicks();
    this.bindTrackButtons();
  }

  openTrackOverlay() {
    const overlay = this.shadowRoot.querySelector("#trackOverlay");
    const frame = this.shadowRoot.querySelector("#trackMapFrame");

    if (!overlay || !frame) return;

    frame.src = `/local/leapmotor/trip_map.html?v=6&t=${Date.now()}`;
    overlay.classList.remove("hidden");
  }

  closeTrackOverlay() {
    const overlay = this.shadowRoot.querySelector("#trackOverlay");
    const frame = this.shadowRoot.querySelector("#trackMapFrame");

    if (overlay) overlay.classList.add("hidden");
    if (frame) frame.src = "about:blank";
  }

  bindTrackButtons() {
    this.shadowRoot.querySelectorAll(".track-btn").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.stopPropagation();

        const tripId = button.dataset.tripId;
        if (!tripId || !this._hass) return;

        this.selectedTripId = Number(tripId);
        this.render();

        const freshButton = this.shadowRoot.querySelector(`.track-btn[data-trip-id="${tripId}"]`) || button;
        const oldText = freshButton.textContent;
        freshButton.textContent = "Carico...";
        freshButton.classList.add("loading");
        freshButton.disabled = true;

        try {
          await this._hass.callService("shell_command", "leapmotor_generate_trip_track", {
            trip_id: Number(tripId),
          });
          this.openTrackOverlay();

          freshButton.textContent = "Mostrato";
          window.dispatchEvent(new CustomEvent("leapmotor-trip-track-updated", {
            detail: { trip_id: Number(tripId), timestamp: Date.now() }
          }));
        } catch (error) {
          console.error("Errore generazione percorso viaggio", error);
          freshButton.textContent = "Errore";
        } finally {
          setTimeout(() => {
            freshButton.textContent = oldText;
            freshButton.classList.remove("loading");
            freshButton.disabled = false;
          }, 1800);
        }
      });
    });
  }

  renderYear(year, yearData) {
    const open = this.expanded.years.has(year);
    const summary = yearData.summary || {};
    const months = yearData.months || {};
    const monthKeys = Object.keys(months).sort((a, b) => Number(b) - Number(a));

    return `
      <div>
        <div class="row year" data-toggle="year" data-key="${year}">
          <div class="arrow">${open ? "▾" : "▸"}</div>
          <div class="label">${year}</div>
          <div class="summary">${this.summaryLine(summary)}</div>
        </div>
        ${
          open
            ? `<div class="children">
                ${monthKeys.map((month) => this.renderMonth(year, month, months[month])).join("")}
              </div>`
            : ""
        }
      </div>
    `;
  }

  renderMonth(year, month, monthData) {
    const key = `${year}-${month}`;
    const open = this.expanded.months.has(key);
    const summary = monthData.summary || {};
    const days = monthData.days || {};
    const dayKeys = Object.keys(days).sort((a, b) => b.localeCompare(a));
    const monthLabel = monthData.name || month;

    return `
      <div>
        <div class="row month" data-toggle="month" data-key="${key}">
          <div class="arrow">${open ? "▾" : "▸"}</div>
          <div class="label">${monthLabel}</div>
          <div class="summary">${this.summaryLine(summary)}</div>
        </div>
        ${
          open
            ? `<div class="children">
                ${dayKeys.map((day) => this.renderDay(year, month, day, days[day])).join("")}
              </div>`
            : ""
        }
      </div>
    `;
  }

  renderDay(year, month, day, dayData) {
    const key = `${year}-${month}-${day}`;
    const open = this.expanded.days.has(key);
    const summary = dayData.summary || {};
    const trips = dayData.trips || [];

    return `
      <div>
        <div class="row day" data-toggle="day" data-key="${key}">
          <div class="arrow">${open ? "▾" : "▸"}</div>
          <div class="label">${dayData.label || this.formatDate(day)}</div>
          <div class="summary">${this.summaryLine(summary)}</div>
        </div>
        ${
          open
            ? `<div class="table-wrap">
                ${this.renderTripsTable(trips)}
              </div>`
            : ""
        }
      </div>
    `;
  }

  renderTripsTable(trips) {
    if (!trips.length) {
      return `<div class="empty">Nessun viaggio nel giorno selezionato</div>`;
    }

    return `
      <table>
        <thead>
          <tr>
            <th>Partenza</th>
            <th>Arrivo</th>
            <th>Durata</th>
            <th>Km</th>
            <th>kWh</th>
            <th>kWh/100km</th>
            <th>SOC</th>
            <th>Vel.Media km/h</th>
            <th>Temp.</th>
            <th>Mappa</th>
          </tr>
        </thead>
        <tbody>
          ${trips.map((trip) => this.renderTripRow(trip)).join("")}
        </tbody>
      </table>
    `;
  }

  renderTripRow(trip) {
    const selected = String(this.selectedTripId) === String(trip.id);

    return `
      <tr class="trip-row ${selected ? "selected" : ""}" data-trip-id="${trip.id}">
        <td>${trip.start_time || ""}</td>
        <td>${trip.end_time || ""}</td>
        <td>${trip.duration || ""}</td>
        <td>${this.formatNumber(trip.km, 1)}</td>
        <td>${this.formatNumber(trip.kwh, 2)}</td>
        <td>${this.formatNumber(trip.cons, 1)}</td>
        <td>${this.formatNumber(trip.soc_start, 1)} → ${this.formatNumber(trip.soc_end, 1)}</td>
        <td>${this.formatNumber(trip.vel_media, 1)}</td>
        <td>${this.formatNumber(trip.temperatura, 1)}</td>
        <td>
          <button class="track-btn" data-trip-id="${trip.id}">
            🗺️ Mappa
          </button>
        </td>
      </tr>
    `;
  }

  bindClicks() {
    this.shadowRoot.querySelectorAll("[data-toggle]").forEach((row) => {
      row.addEventListener("click", () => {
        const type = row.dataset.toggle;
        const key = row.dataset.key;

        if (type === "year") this.toggleSet(this.expanded.years, key);
        if (type === "month") this.toggleSet(this.expanded.months, key);
        if (type === "day") this.toggleSet(this.expanded.days, key);

        this.render();
      });
    });
  }

  toggleSet(set, key) {
    if (set.has(key)) set.delete(key);
    else set.add(key);
  }

  summaryLine(summary) {
    const trips = summary.trips ?? 0;
    const km = this.formatNumber(summary.km, 1);
    const kwh = this.formatNumber(summary.kwh, 2);
    const cons = this.formatNumber(summary.cons, 1);
    return `${trips} viaggi · ${km} km · ${kwh} kWh · ${cons} kWh/100km`;
  }

  formatNumber(value, decimals) {
    const number = Number(value);
    if (Number.isNaN(number)) return (0).toFixed(decimals);
    return number.toFixed(decimals);
  }

  formatDate(value) {
    if (!value) return "";
    const parts = value.split("-");
    if (parts.length !== 3) return value;
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }

  getCardSize() {
    return 6;
  }
}

customElements.define("leapmotor-trip-explorer-card", LeapmotorTripExplorerCard);