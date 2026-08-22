import re

with open('frontend/punti_consegna.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Replace nav
old_nav = re.search(r'<nav class="glass-nav">.*?</nav>', html, re.DOTALL).group(0)
new_nav = '''    <nav class="glass-nav">
        <div class="nav-content">
            <img src="assets/brand/logidesk-mark.svg" alt="LS" style="height: 32px; width: auto; margin-right: 8px;">
            <button id="dashboardBtn" class="logout-btn" title="Dashboard"
                onclick="window.navigateWithState('dashboard.html')"
                style="border:none; background:none; cursor:pointer; margin-right:8px; display:flex;">
                <span class="material-icons-round">dashboard</span>
            </button>
            <div class="nav-title" style="flex: 1;">Punti di Consegna <span id="tenantDisplay" style="font-size: 12px; opacity: 0.8; font-weight:normal; margin-left:8px;"></span></div>
            <a href="#" onclick="window.AuthService.logout(); return false;" class="logout-btn" title="Esci"><span class="material-icons-round">logout</span></a>
        </div>
    </nav>'''
html = html.replace(old_nav, new_nav)

# 2. Replace filters
old_filters = re.search(r'<div class="filters">.*?</div>', html, re.DOTALL).group(0)
new_filters = '''        <div class="glass-panel" style="padding: 24px; margin-bottom: 24px;">
            <div class="filters-container" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                <div class="input-group" style="flex:1; min-width: 250px;">
                    <input type="text" id="searchInput" placeholder="Cerca cliente, codice o citt\xa0..." style="width:100%; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px;">
                </div>
                <div class="input-group">
                    <select id="typeFilter" style="min-width: 160px; height: 45px; cursor: pointer; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0 12px;">
                        <option value="ALL">Tutte le Competenze</option>
                        <option value="FRUTTA">Frutta</option>
                        <option value="LATTE">Latte</option>
                    </select>
                </div>
                <div class="input-group">
                    <select id="statusFilter" style="min-width: 160px; height: 45px; cursor: pointer; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0 12px;">
                        <option value="ALL">Tutti gli stati</option>
                        <option value="ATTIVI">Attivi</option>
                        <option value="INATTIVI">Inattivi</option>
                    </select>
                </div>
                <div class="action-buttons" style="display:flex; gap:12px;">
                    <button id="btnShowMap" class="btn-map" onclick="window.navigateWithState('mappa_google.html')" style="background: #10b981; color: white; border: none; height: 45px; padding: 0 20px; border-radius: 8px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 8px;">
                        <span class="material-icons-round">map</span> Mappa
                    </button>
                    <!-- Aggiungi nascosto/disabilitato per ora per Punti Consegna -->
                </div>
            </div>
        </div>'''
html = html.replace(old_filters, new_filters)

# 3. Fix item-actions buttons in renderList
old_actions = re.search(r'<div class="item-actions">.*?</div>', html, re.DOTALL).group(0)
new_actions = '''                        <div class="item-actions" style="display:flex; gap:8px;">
                            <button class="btn-edit" data-action="geo" data-point-id="${d.id}" title="Geolocalizza (Google Maps)" style="border: 1px solid #e2e8f0;">
                                <span class="material-icons-round" style="font-size:18px; color:#10b981; pointer-events:none;">my_location</span>
                            </button>
                            <button class="btn-edit" data-action="edit" data-point-id="${d.id}" title="Modifica dati" style="border: 1px solid #e2e8f0;">
                                <span class="material-icons-round" style="font-size:18px; color:var(--text-main); pointer-events:none;">edit</span>
                            </button>
                        </div>'''
html = html.replace(old_actions, new_actions)

with open('frontend/punti_consegna.html', 'w', encoding='utf-8') as f:
    f.write(html)
