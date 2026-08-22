import re

with open('frontend/punti_consegna.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the HTML generation in renderList
old_html_block = re.search(r'html \+= `(.*?)`;', html, re.DOTALL).group(1)

new_html_block = '''
                    <div class="item-card" style="padding: 24px;">
                        <div class="card-header" style="display:flex; justify-content:space-between; align-items:flex-start; gap:16px;">
                            <div>
                                <h4 class="card-title" style="margin:0; font-size:16px; font-weight:700; color:#1e293b; text-transform:uppercase;">${d.nome || 'Senza Nome'}</h4>
                                <div style="display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; align-items:center;">
                                    ${primaryBadge}
                                    <span class="badge" style="background:#f1f5f9; color:#64748b">ZONA: ${d.codice_zona || '-'}</span>
                                    <span class="badge" style="background:var(--primary); color:white">${tenantLabel}</span>
                                </div>
                                ${assocHTML}
                            </div>
                            <div class="item-actions" style="display:flex; gap:8px;">
                                <button class="btn-edit" data-action="edit" data-point-id="${d.id}" title="Modifica dati">
                                    <span class="material-icons-round" style="font-size:18px; pointer-events:none;">edit</span>
                                </button>
                                <button class="btn-edit" data-action="geo" data-point-id="${d.id}" title="Geolocalizza (Google Maps)">
                                    <span class="material-icons-round" style="font-size:18px; color:#10b981; pointer-events:none;">my_location</span>
                                </button>
                            </div>
                        </div>
                        
                        <div class="card-grid" style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; padding-top:16px; border-top:1px solid #f1f5f9;">
                            <div>
                                <div style="font-size:10px; font-weight:700; color:#64748b; letter-spacing:0.5px; margin-bottom:4px;">INDIRIZZO</div>
                                <div style="font-size:13px; color:#334155; font-weight:500;">${d.indirizzo || '-'}</div>
                            </div>
                            <div>
                                <div style="font-size:10px; font-weight:700; color:#64748b; letter-spacing:0.5px; margin-bottom:4px;">CITT\u00c0 / PROV</div>
                                <div style="font-size:13px; color:#334155; font-weight:500;">${d.citta || '-'} <br><span style="opacity:0.7">(${d.provincia || '-'})</span></div>
                            </div>
                        </div>
                        
                        <div class="card-grid" style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; padding:12px; background:#f8fafc; border-radius:8px;">
                            <div>
                                <div style="font-size:10px; font-weight:700; color:#64748b; letter-spacing:0.5px; margin-bottom:4px;">ORARI</div>
                                <div style="font-size:13px; color:#0f172a; font-weight:600;">${windows}</div>
                            </div>
                            <div>
                                <div style="font-size:10px; font-weight:700; color:#64748b; letter-spacing:0.5px; margin-bottom:4px;">COORDINATE GPS</div>
                                <div style="font-size:13px; color:#0f172a; font-weight:600;">
                                    ${(d.geolocalizzazione && (d.geolocalizzazione.lat || d.geolocalizzazione.latitude)) ? parseFloat(d.geolocalizzazione.lat || d.geolocalizzazione.latitude).toFixed(4) + '/' + parseFloat(d.geolocalizzazione.lon || d.geolocalizzazione.longitude || d.geolocalizzazione.lng).toFixed(4) : '-'}
                                </div>
                            </div>
                        </div>
                    </div>
                '''

html = html.replace(old_html_block, new_html_block)

# Fix the CSS for btn-edit
if '.btn-edit' not in html:
    html = html.replace('</style>', '''
        .btn-edit {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #ffffff;
            transition: all 0.2s;
        }
        .btn-edit:hover { background: #f8fafc; }
    </style>''')

with open('frontend/punti_consegna.html', 'w', encoding='utf-8') as f:
    f.write(html)
