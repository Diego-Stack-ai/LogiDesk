import re

with open('frontend/punti_consegna.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add formatExternalCode
if 'function formatExternalCode' not in html:
    html = html.replace('function formatTimeWindows', '''function formatExternalCode(val) {
            if (!val) return '-';
            let str = String(val).trim();
            if (str.toUpperCase().startsWith('P')) {
                str = str.substring(1);
            }
            return str;
        }
        function formatTimeWindows''')

# 2. Fix the renderList to use event delegation, formatted codes, and CANALE
def patch_render_list(match):
    body = match.group(0)
    
    new_card_logic = '''
                let type = resolvePointType(d);
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
                    const siblings = associationMap[d.association_group_id];
                    const sibling = siblings.find(sib => sib.id !== d.id);
                    if (sibling) {
                        let sibType = resolvePointType(sibling);
                        let sibRaw = sibling.codice_esterno || sibling.codice_punto || "-";
                        let sibCode = formatExternalCode(sibRaw);
                        assocHTML = `<div style="font-size: 12px; color: #64748b; margin-top: 4px;">🔗 Associato a ${sibType}: ${sibCode}</div>`;
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
    '''
    # We replace from "let isFrutta" up to "});"
    body = re.sub(r'let isFrutta =.*?\n\s+\}\);', new_card_logic, body, flags=re.DOTALL)
    return body

html = re.sub(r'function renderList\(\) \{.*?(?=document\.getElementById\(\'pointsContainer\'\)\.innerHTML)', patch_render_list, html, flags=re.DOTALL)

# 3. Add Event Delegation to pointsContainer
if "data-action='geo'" not in html and "pointsContainer.addEventListener" not in html:
    delegation = '''
        document.getElementById('pointsContainer').addEventListener('click', function(e) {
            const btn = e.target.closest('.btn-icon');
            if (!btn) return;
            const action = btn.getAttribute('data-action');
            const pointId = btn.getAttribute('data-point-id');
            if (action === 'geo' && pointId) {
                window.openMapModal(pointId);
            } else if (action === 'edit' && pointId) {
                window.openEditModal(pointId);
            }
        });
'''
    html = html.replace('function renderList() {', delegation + '\n        function renderList() {')

# 4. Fix Leaflet Map Container HTML
if '<div id="mapContainer"' not in html:
    html = html.replace('<div class="modal-body map-body">', '<div class="modal-body map-body">\n                <div id="mapContainer" style="width: 100%; height: 300px;"></div>')

# 5. Fix Leaflet Initialization logic safely
new_map_js = '''window.openMapModal = function(id) {
            const point = fullData.find(d => d.id === id);
            if (!point) return;
            document.getElementById('mapModal').style.display = 'flex';
            document.getElementById('modalMapTitle').innerText = point.nome || 'Punto senza nome';
            let lat = null, lng = null;
            if (point.geolocalizzazione) {
                lat = point.geolocalizzazione.lat || point.geolocalizzazione.latitude;
                lng = point.geolocalizzazione.lng || point.geolocalizzazione.lon || point.geolocalizzazione.longitude;
            }
            
            const container = document.getElementById('mapContainer');
            if (!container) {
                console.error("Map container not found in DOM");
                return;
            }
            
            if (!lat || !lng) {
                document.getElementById('noMapOverlay').style.display = 'flex';
                document.getElementById('modalMapSubtitle').innerText = "Coordinate non presenti";
                container.style.visibility = 'hidden';
            } else {
                document.getElementById('noMapOverlay').style.display = 'none';
                document.getElementById('modalMapSubtitle').innerText = "Coordinate: " + parseFloat(lat).toFixed(5) + " / " + parseFloat(lng).toFixed(5);
                container.style.visibility = 'visible';
                setTimeout(() => {
                    if (window.map) {
                        window.map.invalidateSize();
                        const latLng = new L.LatLng(lat, lng);
                        window.map.setView(latLng, 15);
                        if (window.marker) window.map.removeLayer(window.marker);
                        window.marker = L.marker(latLng).addTo(window.map);
                    } else {
                        window.map = L.map('mapContainer').setView([lat, lng], 15);
                        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(window.map);
                        window.marker = L.marker([lat, lng]).addTo(window.map);
                    }
                }, 200);
            }
        }'''
html = re.sub(r'window\.openMapModal = function\(id\) \{.*?(?=window\.closeMapModal)', new_map_js + '\n        ', html, flags=re.DOTALL)

with open('frontend/punti_consegna.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Rewrite success')
