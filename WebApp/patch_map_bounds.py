import re

with open('frontend/mappa_google.html', 'r', encoding='utf-8') as f:
    html = f.read()

old_code = """                listDiv.appendChild(item);
            });

            document.getElementById('stat-count').innerText = filtered.length;"""

new_code = """                listDiv.appendChild(item);
            });

            // LOGICA CENTRAMENTO MAPPA (fitBounds)
            if (filtered.length > 0 && window.mapInstance) {
                const bounds = new google.maps.LatLngBounds();
                let validMarkers = 0;
                filtered.forEach(p => {
                    const mLat = parseFloat(p.lat) || 0;
                    const mLng = parseFloat(p.lon) || 0;
                    // Escludi i punti non geolocalizzati (che finiscono a 45.42 per default o a 0)
                    if (mLat !== 0 && mLng !== 0 && mLat !== 45.42) { 
                        bounds.extend(new google.maps.LatLng(mLat, mLng));
                        validMarkers++;
                    }
                });
                if (validMarkers > 0) {
                    window.mapInstance.fitBounds(bounds);
                    // Non zoomare troppo se c'è un solo punto
                    if (validMarkers === 1) {
                        window.mapInstance.setZoom(16);
                    }
                }
            }

            document.getElementById('stat-count').innerText = filtered.length;"""

html = html.replace(old_code, new_code)

with open('frontend/mappa_google.html', 'w', encoding='utf-8') as f:
    f.write(html)
