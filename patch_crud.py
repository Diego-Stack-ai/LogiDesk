import re

with open('frontend/punti_consegna.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add Aggiungi button
old_buttons = '''                    <button id="btnShowMap" class="btn-map" onclick="window.navigateWithState('mappa_google.html')" style="background: #10b981; color: white; border: none; height: 45px; padding: 0 20px; border-radius: 8px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px;">
                        <span class="material-icons-round">map</span> Mappa
                    </button>
                    <!-- Aggiungi nascosto/disabilitato per ora per Punti Consegna -->'''
new_buttons = '''                    <button id="btnShowMap" class="btn-map" onclick="window.navigateWithState('mappa_google.html')" style="background: #10b981; color: white; border: none; height: 45px; padding: 0 20px; border-radius: 8px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px;">
                        <span class="material-icons-round">map</span> Mappa
                    </button>
                    <button class="btn-add" onclick="window.openEditModal(null)" style="background: var(--primary); color: white; border: none; height: 45px; padding: 0 20px; border-radius: 8px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px;">
                        <span class="material-icons-round">add</span> Aggiungi
                    </button>'''
html = html.replace(old_buttons, new_buttons)

# 2. Add Delete button in Card
old_actions = '''                            <div class="item-actions" style="display:flex; gap:8px;">
                                <button class="btn-edit" data-action="edit" data-point-id="${d.id}" title="Modifica dati" style="border: 1px solid #e2e8f0;">
                                    <span class="material-icons-round" style="font-size:18px; color:var(--text-main); pointer-events:none;">edit</span>
                                </button>
                                <button class="btn-edit" data-action="geo" data-point-id="${d.id}" title="Geolocalizza (Google Maps)" style="border: 1px solid #e2e8f0;">
                                    <span class="material-icons-round" style="font-size:18px; color:#10b981; pointer-events:none;">my_location</span>
                                </button>
                            </div>'''
new_actions = '''                            <div class="item-actions" style="display:flex; gap:8px;">
                                <button class="btn-edit" data-action="edit" data-point-id="${d.id}" title="Modifica dati" style="border: 1px solid #e2e8f0;">
                                    <span class="material-icons-round" style="font-size:18px; color:var(--text-main); pointer-events:none;">edit</span>
                                </button>
                                <button class="btn-edit" data-action="geo" data-point-id="${d.id}" title="Geolocalizza (Google Maps)" style="border: 1px solid #e2e8f0;">
                                    <span class="material-icons-round" style="font-size:18px; color:#10b981; pointer-events:none;">my_location</span>
                                </button>
                                <button class="btn-edit" data-action="delete" data-point-id="${d.id}" title="Elimina Punto" style="border: 1px solid #e2e8f0;">
                                    <span class="material-icons-round" style="font-size:18px; color:#ef4444; pointer-events:none;">delete</span>
                                </button>
                            </div>'''
html = html.replace(old_actions, new_actions)

# 3. Fix event delegation
old_delegation = '''            document.getElementById("listContainer").addEventListener("click", (e) => {
                const btn = e.target.closest(".btn-icon");
                if (!btn) return;
                const action = btn.getAttribute("data-action");
                const pointId = btn.getAttribute("data-point-id");
                if (action === "geo" && pointId) {
                    window.openMapModal(pointId);
                } else if (action === "edit" && pointId) {
                    window.openEditModal(pointId);
                }
            });'''
new_delegation = '''            document.getElementById("listContainer").addEventListener("click", (e) => {
                const btn = e.target.closest(".btn-edit");
                if (!btn) return;
                const action = btn.getAttribute("data-action");
                const pointId = btn.getAttribute("data-point-id");
                if (action === "geo" && pointId) {
                    window.openMapModal(pointId);
                } else if (action === "edit" && pointId) {
                    window.openEditModal(pointId);
                } else if (action === "delete" && pointId) {
                    window.deletePoint(pointId);
                }
            });'''
html = html.replace(old_delegation, new_delegation)

# 4. Inject JS implementations
js_impl = '''        window.closeMapModal = function() {
            const modal = document.getElementById("mapModal");
            if (modal) modal.style.display = "none";
        };

        window.openEditModal = function(id) {
            const modal = document.getElementById('editModal');
            const form = document.getElementById('editForm');
            const title = document.querySelector('#editModal h3');
            const subtitle = document.getElementById('editModalSubtitle');
            
            if (id) {
                const p = window.fullData.find(x => x.id === id);
                if (!p) return;
                form.dataset.id = id;
                title.innerText = "Modifica Punto di Consegna";
                subtitle.innerText = "ID: " + id;
                
                document.getElementById('editNome').value = p.nome || '';
                document.getElementById('editIndirizzo').value = p.indirizzo || '';
                document.getElementById('editCap').value = p.cap || '';
                document.getElementById('editCitta').value = p.citta || '';
                document.getElementById('editProvincia').value = p.provincia || '';
                document.getElementById('editZona').value = p.codice_zona || '';
                
                let win = "";
                if (Array.isArray(p.finestre_consegna)) {
                    win = p.finestre_consegna.map(w => `${w.inizio || ''} - ${w.fine || ''}`).join(', ');
                } else if (typeof p.finestre_consegna === 'string') {
                    win = p.finestre_consegna;
                }
                document.getElementById('editFinestre').value = win;
                
                document.getElementById('editStato').value = (p.is_attivo !== false) ? "true" : "false";
                
                let lat = p.geolocalizzazione ? (p.geolocalizzazione.lat || p.geolocalizzazione.latitude || '') : '';
                let lon = p.geolocalizzazione ? (p.geolocalizzazione.lon || p.geolocalizzazione.longitude || p.geolocalizzazione.lng || '') : '';
                document.getElementById('editLat').value = lat;
                document.getElementById('editLng').value = lon;
            } else {
                form.dataset.id = "";
                title.innerText = "Nuovo Punto di Consegna";
                subtitle.innerText = "Compila i dati per creare un nuovo punto";
                form.reset();
                document.getElementById('editStato').value = "true";
            }
            
            modal.style.display = 'flex';
        };

        window.closeEditModal = function() {
            const modal = document.getElementById('editModal');
            if (modal) modal.style.display = 'none';
        };

        window.saveEdit = async function() {
            const id = document.getElementById('editForm').dataset.id;
            const isNew = !id;
            const nome = document.getElementById('editNome').value.trim();
            if (!nome) return alert("Inserire il Nome Punto");
            
            const activeTenantId = window.CompanyContext.getActiveTenantId();
            if (!activeTenantId) return alert("Nessun tenant attivo!");
            
            const finestreStr = document.getElementById('editFinestre').value.trim();
            
            const data = {
                nome: nome,
                indirizzo: document.getElementById('editIndirizzo').value.trim(),
                cap: document.getElementById('editCap').value.trim(),
                citta: document.getElementById('editCitta').value.trim(),
                provincia: document.getElementById('editProvincia').value.trim().toUpperCase(),
                codice_zona: document.getElementById('editZona').value.trim(),
                finestre_consegna: finestreStr,
                is_attivo: document.getElementById('editStato').value === "true",
                tenantId: activeTenantId,
                updatedAt: new Date().toISOString()
            };
            
            let lat = document.getElementById('editLat').value.trim();
            let lon = document.getElementById('editLng').value.trim();
            if (lat && lon) {
                data.geolocalizzazione = { lat: parseFloat(lat), lon: parseFloat(lon) };
            }
            
            try {
                if (isNew) {
                    data.codice_esterno = "NUOVO_" + Date.now();
                    const { collection, addDoc, db } = await import("https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js");
                    await addDoc(collection(db, `tenants/${activeTenantId}/punti_consegna`), data);
                } else {
                    const { doc, updateDoc, db } = await import("https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js");
                    const ref = doc(db, `tenants/${activeTenantId}/punti_consegna`, id);
                    await updateDoc(ref, data);
                }
                alert("Punto di consegna salvato con successo.");
                window.closeEditModal();
                // Ricarica i dati per forzare aggiornamento UI se onSnapshot non basta
                loadData();
            } catch (err) {
                console.error(err);
                alert("Errore salvataggio: " + err.message);
            }
        };

        window.deletePoint = async function(id) {
            if (!confirm("⚠️ ATTENZIONE: Sei sicuro di voler eliminare questo punto di consegna definitivamente dal database?")) return;
            try {
                const activeTenantId = window.CompanyContext.getActiveTenantId();
                if (!activeTenantId) return alert("Nessun tenant attivo!");
                const { doc, deleteDoc, db } = await import("https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js");
                const ref = doc(db, `tenants/${activeTenantId}/punti_consegna`, id);
                await deleteDoc(ref);
                alert("Punto di consegna eliminato.");
                loadData();
            } catch (err) {
                console.error(err);
                alert("Errore eliminazione: " + err.message);
            }
        };'''

old_close_map = '''        window.closeMapModal = function() {
            const modal = document.getElementById("mapModal");
            if (modal) modal.style.display = "none";
        };'''
html = html.replace(old_close_map, js_impl)

with open('frontend/punti_consegna.html', 'w', encoding='utf-8') as f:
    f.write(html)
