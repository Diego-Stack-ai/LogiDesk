import { db, auth } from './core/firebase-init.js';
import { CompanyContext } from './core/CompanyContext.js';
import { onAuthStateChanged, signOut } from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js';
import { collection, doc, getDocs, addDoc, setDoc, serverTimestamp } from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js';

const page = document.body.dataset.masterPage;
const isArticles = page === 'articles';
let tenants = [];
let records = [];
const el = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[char]));
const tenantName = id => {
    const tenant = tenants.find(item => item.id === id);
    return tenant?.nome || tenant?.name || id;
};
const collectionPath = tenantId => isArticles ? CompanyContext.getImportMappingsPath(tenantId) : CompanyContext.getDdtReturnsPath(tenantId);
const normalizeLabel = value => String(value || '').replaceAll('_', ' ').toUpperCase();

function articleFields(record = {}) {
    return `
        <div class="master-field"><label for="tenantId">Committente</label><select id="tenantId" required></select></div>
        <div class="master-field"><label for="code">Codice articolo</label><input id="code" required value="${escapeHtml(record.id || '')}"></div>
        <div class="master-field master-span"><label for="description">Descrizione</label><input id="description" required value="${escapeHtml(record.descrizione || '')}"></div>
        <div class="master-field"><label for="family">Famiglia</label><input id="family" value="${escapeHtml(record.famiglia || '')}"></div>
        <div class="master-field"><label for="packaging">Confezionamento</label><input id="packaging" value="${escapeHtml(record.confezionamento || '')}"></div>
        <div class="master-field"><label for="primaryUnit">Unità principale</label><input id="primaryUnit" value="${escapeHtml(record.unita_principale || '')}"></div>
        <div class="master-field"><label for="secondaryUnit">Unità secondaria</label><input id="secondaryUnit" value="${escapeHtml(record.unita_secondaria || '')}"></div>
        <div class="master-field"><label for="ratio">Rapporto</label><input id="ratio" type="number" step="any" value="${escapeHtml(record.ratio ?? '')}"></div>
        <div class="master-field"><label for="portions">Porzioni</label><input id="portions" type="number" step="any" value="${escapeHtml(record.porzioni ?? record.per ?? '')}"></div>
        <div class="master-field"><label for="known">Stato</label><select id="known"><option value="true">Articolo riconosciuto</option><option value="false">Da verificare</option></select></div>`;
}

function ddtFields(record = {}) {
    return `
        <div class="master-field"><label for="tenantId">Committente</label><select id="tenantId" required></select></div>
        <div class="master-field"><label for="deliveryCode">Codice consegna</label><input id="deliveryCode" required value="${escapeHtml(record.codice_consegna || '')}"></div>
        <div class="master-field"><label for="ddtDate">Data DDT</label><input id="ddtDate" type="date" required value="${escapeHtml(record.data_ddt || '')}"></div>
        <div class="master-field"><label for="ddtNumber">Numero DDT</label><input id="ddtNumber" required value="${escapeHtml(record.numero_ddt || '')}"></div>
        <div class="master-field"><label for="type">Tipo rientro</label><select id="type"><option value="completo">Completo</option><option value="parziale">Parziale</option></select></div>
        <div class="master-field"><label for="status">Stato</label><select id="status"><option value="da_allegare">Da allegare</option><option value="allegato">Allegato</option><option value="verificato">Verificato</option></select></div>
        <div class="master-field master-span"><label for="notes">Note</label><textarea id="notes" rows="4">${escapeHtml(record.note || '')}</textarea></div>`;
}

function tenantOptions(selectedId = '') {
    return '<option value="">Seleziona il committente</option>' + tenants.map(tenant => `<option value="${escapeHtml(tenant.id)}" ${tenant.id === selectedId ? 'selected' : ''}>${escapeHtml(tenantName(tenant.id))}</option>`).join('');
}

async function load() {
    try {
        const tenantSnapshot = await getDocs(collection(db, CompanyContext.getCompanyPath() + '/tenants'));
        tenants = tenantSnapshot.docs.map(item => ({ id:item.id, ...item.data() })).sort((a,b) => tenantName(a.id).localeCompare(tenantName(b.id)));
        el('tenantFilter').innerHTML = '<option value="ALL">Tutti i committenti</option>' + tenants.map(tenant => `<option value="${escapeHtml(tenant.id)}">${escapeHtml(tenantName(tenant.id))}</option>`).join('');
        const groups = await Promise.all(tenants.map(async tenant => {
            const snapshot = await getDocs(collection(db, collectionPath(tenant.id)));
            return snapshot.docs.map(item => ({ id:item.id, tenant_id:tenant.id, ...item.data() }));
        }));
        records = groups.flat().filter(record => !isArticles || !record.id.startsWith('_'));
        render();
    } catch (error) {
        el('stats').textContent = 'Errore di caricamento';
        el('records').innerHTML = `<div class="master-empty master-error">${escapeHtml(error.message)}</div>`;
    }
}

function articleCard(record) {
    return `<article class="master-card"><div class="master-head"><div><div class="master-title">${escapeHtml(record.descrizione || record.id)}</div><div class="master-badges"><span class="master-badge">${escapeHtml(record.id)}</span><span class="master-badge">${escapeHtml(tenantName(record.tenant_id))}</span><span class="master-badge">${record.is_articolo_noto === false ? 'DA VERIFICARE' : 'RICONOSCIUTO'}</span></div></div>${editButton(record)}</div><div class="master-detail"><div class="master-label">Famiglia · Confezionamento</div><div class="master-value">${escapeHtml(record.famiglia || '-')} · ${escapeHtml(record.confezionamento || '-')}</div></div><div class="master-detail"><div class="master-label">Unità · Rapporto · Porzioni</div><div class="master-value">${escapeHtml(record.unita_principale || '-')} / ${escapeHtml(record.unita_secondaria || '-')} · ${escapeHtml(record.ratio ?? '-')} · ${escapeHtml(record.porzioni ?? record.per ?? '-')}</div></div></article>`;
}

function ddtCard(record) {
    return `<article class="master-card ddt"><div class="master-head"><div><div class="master-title">${escapeHtml(record.codice_consegna || 'Codice non indicato')}</div><div class="master-badges"><span class="master-badge">${escapeHtml(tenantName(record.tenant_id))}</span><span class="master-badge">${escapeHtml(normalizeLabel(record.tipo || 'completo'))}</span><span class="master-badge">${escapeHtml(normalizeLabel(record.stato || 'da_allegare'))}</span></div></div>${editButton(record)}</div><div class="master-detail"><div class="master-label">DDT</div><div class="master-value">${escapeHtml(record.data_ddt || '-')} · ${escapeHtml(record.numero_ddt || '-')}</div></div>${record.note ? `<div class="master-detail"><div class="master-label">Note</div><div class="master-value">${escapeHtml(record.note)}</div></div>` : ''}</article>`;
}

function editButton(record) {
    return `<button class="master-edit" data-edit="${escapeHtml(record.id)}" data-tenant="${escapeHtml(record.tenant_id)}" title="Modifica"><span class="material-icons-round">edit</span></button>`;
}

function render() {
    const query = el('searchInput').value.trim().toLowerCase();
    const tenantId = el('tenantFilter').value;
    const filtered = records.filter(record => (tenantId === 'ALL' || record.tenant_id === tenantId) && (!query || JSON.stringify(record).toLowerCase().includes(query)));
    filtered.sort((a,b) => isArticles ? a.id.localeCompare(b.id) : String(b.data_ddt || '').localeCompare(String(a.data_ddt || '')));
    el('stats').textContent = `${filtered.length} ${isArticles ? 'articoli' : 'rientri'} visualizzati su ${records.length}`;
    el('records').innerHTML = filtered.map(isArticles ? articleCard : ddtCard).join('') || `<div class="master-empty">Nessun ${isArticles ? 'articolo' : 'rientro DDT'} trovato.</div>`;
}

function openEditor(record = null) {
    el('recordId').value = record?.id || '';
    el('originalTenantId').value = record?.tenant_id || '';
    el('editorTitle').textContent = `${record ? 'Modifica' : 'Nuovo'} ${isArticles ? 'articolo' : 'rientro DDT'}`;
    el('formFields').innerHTML = isArticles ? articleFields(record || {}) : ddtFields(record || {});
    const suggestedTenant = record?.tenant_id || (el('tenantFilter').value === 'ALL' ? '' : el('tenantFilter').value);
    el('tenantId').innerHTML = tenantOptions(suggestedTenant);
    el('tenantId').disabled = Boolean(record);
    if (isArticles) { el('code').readOnly = Boolean(record); el('known').value = record?.is_articolo_noto === false ? 'false' : 'true'; }
    else { el('type').value = record?.tipo || 'completo'; el('status').value = record?.stato || 'da_allegare'; }
    el('formError').textContent = '';
    el('editorModal').classList.add('active');
}

function numericValue(id) {
    const value = el(id).value;
    return value === '' ? '' : Number(value);
}

async function save(event) {
    event.preventDefault();
    const tenantId = el('originalTenantId').value || el('tenantId').value;
    if (!tenantId) { el('formError').textContent = 'Seleziona il committente.'; return; }
    try {
        if (isArticles) {
            const code = (el('recordId').value || el('code').value).trim().toUpperCase();
            if (!code) throw new Error('Inserisci il codice articolo.');
            await setDoc(doc(db, collectionPath(tenantId), code), { descrizione:el('description').value.trim(), famiglia:el('family').value.trim(), confezionamento:el('packaging').value.trim(), unita_principale:el('primaryUnit').value.trim(), unita_secondaria:el('secondaryUnit').value.trim(), ratio:numericValue('ratio'), porzioni:numericValue('portions'), is_articolo_noto:el('known').value === 'true' }, { merge:true });
        } else {
            if (el('type').value === 'parziale' && !el('notes').value.trim()) throw new Error('La nota è obbligatoria per un rientro parziale.');
            const payload = { codice_consegna:el('deliveryCode').value.trim(), data_ddt:el('ddtDate').value, numero_ddt:el('ddtNumber').value.trim(), tipo:el('type').value, stato:el('status').value, note:el('notes').value.trim(), updated_at:serverTimestamp() };
            if (el('recordId').value) await setDoc(doc(db, collectionPath(tenantId), el('recordId').value), payload, { merge:true });
            else await addDoc(collection(db, collectionPath(tenantId)), { ...payload, created_at:serverTimestamp() });
        }
        el('editorModal').classList.remove('active');
        await load();
    } catch (error) { el('formError').textContent = error.message; }
}

el('editorForm').addEventListener('submit', save);
el('records').addEventListener('click', event => { const button = event.target.closest('[data-edit]'); if (button) openEditor(records.find(record => record.id === button.dataset.edit && record.tenant_id === button.dataset.tenant)); });
el('searchInput').addEventListener('input', render);
el('tenantFilter').addEventListener('change', render);
el('addBtn').addEventListener('click', () => openEditor());
el('cancelBtn').addEventListener('click', () => el('editorModal').classList.remove('active'));
el('backBtn').addEventListener('click', () => { location.href = 'dashboard.html'; });
el('logoutBtn').addEventListener('click', async () => { await signOut(auth); location.replace('login.html'); });
onAuthStateChanged(auth, user => user ? load() : location.replace('login.html'));
