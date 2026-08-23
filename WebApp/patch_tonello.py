import re

with open('frontend/punti_consegna.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Trova inizio funzioni
idx_resolve = -1
idx_format_code = -1
idx_render = -1
idx_init = -1

for i, line in enumerate(lines):
    if 'function resolvePointType' in line: idx_resolve = i
    if 'function formatExternalCode' in line: idx_format_code = i
    if 'function renderList' in line: idx_render = i
    if 'async function init' in line: idx_init = i

new_resolve = '''        function resolvePointType(d) {
            let sc = d.sottocodice ? String(d.sottocodice).trim().toUpperCase() : "";
            if (sc === "FRUTTA" || sc === "LATTE") return sc;
            return "UNKNOWN";
        }

        function extractData(dataList) {
            fullData = dataList;
            associationMap = {};
            fullData.forEach(d => {
                if (d.association_group_id) {
                    if (!associationMap[d.association_group_id]) {
                        associationMap[d.association_group_id] = [];
                    }
                    associationMap[d.association_group_id].push(d);
                }
            });
        }
'''

new_render = '''        function renderList() {
            const search = document.getElementById("searchInput").value.toLowerCase().trim();
            const typeF = document.getElementById("typeFilter").value;
            const statusF = document.getElementById("statusFilter").value;

            let filtered = fullData.filter(d => {
                const type = resolvePointType(d);
                
                // Tipo
                if (typeF !== "ALL" && type !== typeF) return false;

                // Stato
                if (statusF === "ACTIVE" && d.attivo === false) return false;
                if (statusF === "INACTIVE" && d.attivo !== false) return false;

                // Testo
                if (search) {
                    const match = (
                        (d.nome && d.nome.toLowerCase().includes(search)) || 
                        (d.codice_esterno && d.codice_esterno.toLowerCase().includes(search)) || 
                        (d.citta && d.citta.toLowerCase().includes(search))
                    );
                    if (!match) return false;
                }

                return true;
            });

            const statsEl = document.getElementById("listStats");
            let fC = 0, lC = 0, uC = 0;
            fullData.forEach(d => {
                let t = resolvePointType(d);
                if(t==="FRUTTA") fC++;
                else if(t==="LATTE") lC++;
                else uC++;
            });
            statsEl.innerText = `Trovati ${filtered.length} su ${fullData.length} (FRUTTA: ${fC}, LATTE: ${lC}, UNKNOWN: ${uC})`;

            const container = document.getElementById("listContainer");
            container.innerHTML = "";

            let html = "";
            filtered.forEach(d => {
                const type = resolvePointType(d);
                let isFrutta = type === "FRUTTA";
                let isLatte = type === "LATTE";
                
                let rawCode = d.codice_esterno || d.codice_punto || "-";
                let primaryCode = formatExternalCode(rawCode);
                
                let primaryBadge = "";
                if (isFrutta) primaryBadge = `<span class="badge badge-frutta">F: ${primaryCode}</span>`;
                else if (isLatte) primaryBadge = `<span class="badge badge-latte">L: ${primaryCode}</span>`;
                else primaryBadge = `<span class="badge" style="background:#e2e8f0; color:#475569">?: ${primaryCode}</span>`;
                
                let assocHTML = "";
                if (d.association_group_id && associationMap[d.association_group_id]) {
                    const siblings = associationMap[d.association_group_id].filter(sib => sib.id !== d.id);
                    if (siblings.length > 0) {
                        let sibling = siblings[0];
                        let sibType = resolvePointType(sibling);
                        let sibRaw = sibling.codice_esterno || sibling.codice_punto || "-";
                        let sibCode = formatExternalCode(sibRaw);
                        assocHTML = `<div style="font-size: 12px; color: #64748b; margin-top: 4px;">&#128279; Associato a ${sibType}: ${sibCode}</div>`;
                    }
                }
                
                let tenantLabel = "N/A";
                if (d.tenant_name) tenantLabel = d.tenant_name;
                else if (d.tenant_id === 'AgvcnbuUMu7YhzSuUKTY') tenantLabel = "DNR";
                
                let channelHTML = `<div style="font-size: 12px; font-weight: 600; color: #475569; margin-top: 2px;">CANALE: ${type}</div>`;
                
                let windows = formatTimeWindows(d.finestre_consegna);
                
                html += `
                    <div class="item-card">
                        <div class="item-header">
                            <div class="item-title">
                                <span class="material-icons" style="color: #94a3b8; font-size: 20px;">storefront</span>
                                <div>
                                    <div style="font-weight: 600; font-size: 15px; color: #1e293b;">${d.nome || "Senza Nome"}</div>
                                    <div style="font-size: 12px; color: #64748b;">${tenantLabel}</div>
                                    ${channelHTML}
                                </div>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 4px; text-align: right;">
                                <div>${primaryBadge}</div>
                                ${assocHTML}
                            </div>
                        </div>
                        
                        <div class="item-details">
                            <div class="detail-row">
                                <span class="material-icons detail-icon">place</span>
                                <span>${d.indirizzo || "-"}, ${d.citta || ""} (${d.provincia || ""})</span>
                            </div>
                            <div class="detail-row">
                                <span class="material-icons detail-icon">schedule</span>
                                <span>Orari: ${windows}</span>
                            </div>
                        </div>
                        
                        <div class="item-actions">
                            <button class="btn-icon" data-action="geo" data-point-id="${d.id}" title="Geolocalizza">
                                <span class="material-icons" style="color: #10b981; pointer-events:none;">location_on</span>
                            </button>
                            <button class="btn-icon" data-action="edit" data-point-id="${d.id}" title="Modifica">
                                <span class="material-icons" style="color: #3b82f6; pointer-events:none;">edit</span>
                            </button>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
        }
'''

new_lines = lines[:idx_resolve] + [new_resolve] + lines[idx_format_code:idx_render] + [new_render] + lines[idx_init:]

with open('frontend/punti_consegna.html', 'w', encoding='utf-8') as f:
    for line in new_lines:
        f.write(line)
        if not line.endswith('\\n'):
            f.write('\\n')
