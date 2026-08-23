import re

with open('frontend/punti_consegna.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update resolvePointType
new_resolver = '''function resolvePointType(d) {
            if (d.sottocodice) {
                const sc = String(d.sottocodice).trim().toUpperCase();
                if (sc === 'FRUTTA') return 'FRUTTA';
                if (sc === 'LATTE') return 'LATTE';
            }
            return 'UNKNOWN';
        }'''
content = re.sub(r'function resolvePointType\(d\) \{.*?\/\/ Safest fallback.*?\}', new_resolver, content, flags=re.DOTALL)

# 2. Add formatTimeWindows
if 'function formatTimeWindows' not in content:
    content = content.replace('function renderList() {', '''function formatTimeWindows(arr) {
            if (!arr || !Array.isArray(arr)) return "Non def.";
            return arr.map(w => {
                if (w.da && w.a) return w.da + " - " + w.a;
                if (w.start && w.end) return w.start + " - " + w.end;
                return JSON.stringify(w);
            }).join(", ");
        }
        function renderList() {''')

# 3. Modify renderList for single badge, association, and formatted time windows
def patch_render_list(match):
    body = match.group(0)
    # Patch time windows
    body = re.sub(
        r'const fWin =.*?const lWin =.*?;', 
        '''let fWin = "Non def."; let lWin = "Non def.";
                if (type === "FRUTTA") fWin = formatTimeWindows(d.finestre_consegna);
                if (type === "LATTE") lWin = formatTimeWindows(d.finestre_consegna);''',
        body, flags=re.DOTALL
    )
    # Patch badge and association
    body = re.sub(
        r'let isFrutta = type === "FRUTTA".*?(?=<div class="item-card")',
        '''let isFrutta = type === "FRUTTA";
                let isLatte = type === "LATTE";
                
                let primaryCode = d.codice_esterno || d.codice_punto || "-";
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
                        let sibCode = sibling.codice_esterno || sibling.codice_punto || "-";
                        assocHTML = `<div style="font-size: 12px; color: #64748b; margin-top: 4px;">🔗 Associato a ${sibType}: ${sibCode}</div>`;
                        if (type === "FRUTTA") lWin = formatTimeWindows(sibling.finestre_consegna);
                        if (type === "LATTE") fWin = formatTimeWindows(sibling.finestre_consegna);
                    }
                }
                
                ''',
        body, flags=re.DOTALL
    )
    
    # Replace the actual card html to remove dual badge
    body = re.sub(
        r'<div class="item-title">.*?</div>',
        '''<div class="item-title">
                                <span class="material-icons" style="color: #94a3b8; font-size: 20px;">storefront</span>
                                <div>
                                    <div style="font-weight: 600; font-size: 15px; color: #1e293b;">${d.nome || "Senza Nome"}</div>
                                    <div style="font-size: 12px; color: #64748b;">${d.tenant_name || "N/A"}</div>
                                </div>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 4px;">
                                <div>${primaryBadge}</div>
                                ${assocHTML}
                            </div>''',
        body, flags=re.DOTALL
    )
    return body

content = re.sub(r'function renderList\(\) \{.*?(?=document\.getElementById\(\'pointsContainer\'\)\.innerHTML)', patch_render_list, content, flags=re.DOTALL)

# 4. Patch openMapModal
new_map_modal = '''window.openMapModal = function(id) {
            const point = fullData.find(d => d.id === id);
            if (!point) return;
            document.getElementById('mapModal').style.display = 'flex';
            document.getElementById('modalMapTitle').innerText = point.nome || 'Punto senza nome';
            let lat = null, lng = null;
            if (point.geolocalizzazione) {
                lat = point.geolocalizzazione.lat || point.geolocalizzazione.latitude;
                lng = point.geolocalizzazione.lng || point.geolocalizzazione.lon || point.geolocalizzazione.longitude;
            }
            if (!lat || !lng) {
                document.getElementById('noMapOverlay').style.display = 'flex';
                document.getElementById('modalMapSubtitle').innerText = "Coordinate non presenti";
            } else {
                document.getElementById('noMapOverlay').style.display = 'none';
                document.getElementById('modalMapSubtitle').innerText = "Coordinate: " + parseFloat(lat).toFixed(5) + " / " + parseFloat(lng).toFixed(5);
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
                }, 100);
            }
        }'''
content = re.sub(r'window\.openMapModal = function\(id\) \{.*?(?=window\.closeMapModal)', new_map_modal + '\n        ', content, flags=re.DOTALL)

# 5. Patch Save Edit modal
if 'function saveEdit' not in content:
    content = content.replace('window.closeEditModal = function() {', '''window.saveEdit = function() {
            alert("Scrittura non ancora certificata (Core V1). Funzionalità in sola lettura.");
            closeEditModal();
        };
        window.closeEditModal = function() {''')
        
    # Also attach saveEdit to the button in the modal if it's there
    content = re.sub(r'onclick="saveEdit\(\)".*?>Salva', 'onclick="saveEdit()">Salva', content)

with open('frontend/punti_consegna.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patch success')
