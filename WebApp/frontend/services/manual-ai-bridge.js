export const BRIDGE_SCHEMA_VERSION = 'logidesk.manual-ai-bridge/1.0';

export const CANONICAL_FIELDS = Object.freeze([
    'tipo_documento', 'data_viaggio', 'numero_ddt',
    'codice_punto_committente', 'denominazione_punto', 'indirizzo',
    'numero_civico', 'cap', 'localita', 'provincia', 'telefono',
    'note_consegna', 'orario_da', 'orario_a', 'codice_zona_originale',
    'codice_zona_logistica', 'codice_articolo_committente',
    'codice_articolo_operativo', 'descrizione_articolo', 'lotto',
    'scadenza_da', 'scadenza_a', 'quantita', 'unita_misura', 'colli',
    'porzioni_per_collo', 'peso', 'giro_sorgente'
]);

const SENSITIVE_KEYS = new Set([
    'codice_fiscale', 'partita_iva', 'email', 'telefono', 'cellulare',
    'nome', 'cognome', 'cliente', 'ragione_sociale', 'denominazione',
    'indirizzo'
]);

function stableToken(kind, value) {
    const input = String(value);
    let hash = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
        hash ^= input.charCodeAt(i);
        hash = Math.imul(hash, 16777619);
    }
    return `<${kind.toUpperCase()}_${(hash >>> 0).toString(16).padStart(8, '0')}>`;
}

const DOCUMENT_ANCHORS = Object.freeze([
    'ddt', 'documento di trasporto', 'luogo di destinazione', 'codice destinazione',
    'causale del trasporto', 'responsabile del trasporto', 'codice articolo',
    'descrizione', 'quantita', 'quantità', 'data', 'giro', 'peso', 'colli'
]);

export function createStructuralSignature(file) {
    const kind = String(file.kind || 'unknown').replace(/^pdf.*$/, 'pdf').replace(/^image.*$/, 'image');
    const sections = (file.sections || []).map(section => ({
        name: String(section.name || '').trim().toLowerCase(),
        columns: (section.columns || []).map(column => String(column || '').trim().toLowerCase()),
        extraction: section.extraction || null
    }));
    const searchableText = (file.sampleRows || [])
        .map(row => Object.values(row).filter(value => typeof value === 'string').join(' '))
        .join(' ')
        .toLowerCase();
    const anchors = DOCUMENT_ANCHORS.filter(anchor => searchableText.includes(anchor));
    const descriptor = JSON.stringify({ kind, sections, anchors });
    return stableToken('struttura', descriptor).slice(1, -1).toLowerCase();
}

export function anonymizeRows(rows, keepKeys = [], maxRows = 12) {
    const keep = new Set(keepKeys.map(key => String(key).trim().toLowerCase()));
    return rows.slice(0, maxRows).map(row => Object.fromEntries(
        Object.entries(row).map(([key, value]) => {
            const normalizedKey = key.trim().toLowerCase();
            if (value === null || ['number', 'boolean'].includes(typeof value)) return [key, value];
            if (keep.has(normalizedKey)) return [key, String(value)];
            const kind = SENSITIVE_KEYS.has(normalizedKey) ? normalizedKey : 'valore';
            return [key, stableToken(kind, value)];
        })
    ));
}

export function buildManualPrompt({ file, companyId, tenantId, workDate, operatorNote = '', keepSampleKeys = [] }) {
    if (!companyId) throw new Error('Azienda obbligatoria.');
    if (!tenantId) throw new Error('Committente obbligatorio: nessun fallback è consentito.');

    const payload = {
        schema_version: BRIDGE_SCHEMA_VERSION,
        source: {
            file_name: file.name,
            source_kind: file.kind,
            size: file.size,
            sections: file.sections,
            source_signature: file.sourceSignature || createStructuralSignature(file),
            signature_strength: 'candidate_only'
        },
        context: {
            company_id: companyId,
            tenant_id: tenantId,
            work_date: workDate || null,
            operator_note: operatorNote.trim()
        },
        canonical_fields: CANONICAL_FIELDS,
        sample_rows_anonymized: anonymizeRows(file.sampleRows || [], keepSampleKeys)
    };

    const responseShape = {
        schema_version: BRIDGE_SCHEMA_VERSION,
        tipo_documento: 'string',
        numero_giri_proposto: 0,
        mapping: [{
            campo_sorgente: 'string',
            campo_logidesk: 'uno dei canonical_fields',
            confidenza: 0.0,
            motivazione: 'string'
        }],
        ambiguita: [{ campo_sorgente: 'string', domanda: 'string' }],
        campi_nuovi: [{ campo_sorgente: 'string', utilita_proposta: 'string' }],
        avvisi: ['string']
    };

    return [
        'Sei un consulente di mappatura dati per LogiDesk.',
        'Analizza soltanto la rappresentazione anonimizzata seguente.',
        'Non inventare valori mancanti e non considerare le proposte già approvate.',
        'Evidenzia ambiguità su date, numero di giri, codici composti, quantità e unità.',
        'Restituisci esclusivamente JSON valido nella forma richiesta.',
        '',
        'DATI LOGIDESK:',
        JSON.stringify(payload, null, 2),
        '',
        'FORMA RISPOSTA:',
        JSON.stringify(responseShape, null, 2)
    ].join('\n');
}

function requireObjectList(data, key) {
    const value = data[key] ?? [];
    if (!Array.isArray(value) || value.some(item => !item || typeof item !== 'object' || Array.isArray(item))) {
        throw new Error(`${key} deve essere una lista di oggetti.`);
    }
    return value;
}

export function validateManualResponse(rawResponse) {
    const cleaned = rawResponse.trim()
        .replace(/^```(?:json)?\s*/i, '')
        .replace(/\s*```$/, '');
    let data;
    try {
        data = JSON.parse(cleaned);
    } catch {
        throw new Error('La risposta incollata non è JSON valido.');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('La risposta deve essere un oggetto JSON.');
    if (data.schema_version !== BRIDGE_SCHEMA_VERSION) throw new Error('Versione del contratto non riconosciuta.');
    if (typeof data.tipo_documento !== 'string' || !data.tipo_documento.trim()) throw new Error('tipo_documento obbligatorio.');
    if (!Number.isInteger(data.numero_giri_proposto) || data.numero_giri_proposto < 0) {
        throw new Error('numero_giri_proposto deve essere un intero maggiore o uguale a zero.');
    }

    const mappings = requireObjectList(data, 'mapping');
    mappings.forEach((mapping, index) => {
        if (typeof mapping.campo_sorgente !== 'string' || !mapping.campo_sorgente.trim()) {
            throw new Error(`mapping[${index}].campo_sorgente non valido.`);
        }
        if (!CANONICAL_FIELDS.includes(mapping.campo_logidesk)) {
            throw new Error(`mapping[${index}].campo_logidesk sconosciuto.`);
        }
        if (typeof mapping.confidenza !== 'number' || mapping.confidenza < 0 || mapping.confidenza > 1) {
            throw new Error(`mapping[${index}].confidenza non valida.`);
        }
    });
    requireObjectList(data, 'ambiguita');
    requireObjectList(data, 'campi_nuovi');
    if (!Array.isArray(data.avvisi ?? []) || (data.avvisi ?? []).some(item => typeof item !== 'string')) {
        throw new Error('avvisi deve essere una lista di stringhe.');
    }
    return data;
}

export function applyMappings(rows, mappings) {
    const targets = new Set();
    mappings.forEach((mapping, index) => {
        if (!CANONICAL_FIELDS.includes(mapping.campo_logidesk)) {
            throw new Error(`mapping[${index}].campo_logidesk sconosciuto.`);
        }
        if (targets.has(mapping.campo_logidesk)) {
            throw new Error(`Il campo ${mapping.campo_logidesk} è associato più di una volta.`);
        }
        targets.add(mapping.campo_logidesk);
    });
    return rows.map((row, rowIndex) => {
        const normalized = {};
        mappings.forEach(mapping => {
            const value = row[mapping.campo_sorgente];
            normalized[mapping.campo_logidesk] = value === undefined || value === '' ? null : value;
        });
        return { source_section: row.__foglio || null, source_row: rowIndex + 2, data: normalized };
    });
}

export function findCandidateDuplicates(records, tenantId) {
    const seen = new Map();
    const duplicates = [];
    records.forEach((record, index) => {
        const data = record.data || {};
        const candidates = [
            ['delivery_point', data.codice_punto_committente],
            ['article', data.codice_articolo_committente],
            ['ddt', data.numero_ddt]
        ];
        candidates.forEach(([domain, rawValue]) => {
            const value = String(rawValue ?? '').trim().toUpperCase();
            if (!value) return;
            const key = `${tenantId}|${domain}|${value}`;
            if (seen.has(key)) {
                duplicates.push({ domain, value, first_index: seen.get(key), duplicate_index: index });
            } else {
                seen.set(key, index);
            }
        });
    });
    return duplicates;
}

const HEADER_HINTS = Object.freeze([
    'codice', 'cliente', 'ragione sociale', 'nome cliente', 'indirizzo',
    'localita', 'località', 'provincia', 'colli', 'peso', 'quantita',
    'quantità', 'giro', 'viaggio', 'articolo', 'descrizione', 'data',
    'giorno', 'targa', 'mezzo', 'autista', 'ora', 'tempo', 'fatturato',
    'note', 'fascia oraria', 'tipo', 'resi'
]);

function populatedCells(row) {
    return (row || []).filter(value => value !== null && value !== undefined && String(value).trim() !== '');
}

export function detectTableRegions(matrix, maxHeaderScan = 40) {
    const candidates = [];
    matrix.slice(0, maxHeaderScan).forEach((row, index) => {
        const populated = populatedCells(row);
        if (populated.length < 3) return;
        const combined = populated.map(value => String(value).trim().toLowerCase()).join(' | ');
        const hintCount = HEADER_HINTS.filter(hint => combined.includes(hint)).length;
        if (hintCount >= 2) candidates.push({ headerRowIndex: index, hintCount, fallback: false });
    });
    if (!candidates.length) {
        let bestIndex = -1;
        let bestWidth = 0;
        matrix.slice(0, maxHeaderScan).forEach((row, index) => {
            const width = populatedCells(row).length;
            if (width > bestWidth) {
                bestIndex = index;
                bestWidth = width;
            }
        });
        if (bestIndex >= 0 && bestWidth >= 2) candidates.push({ headerRowIndex: bestIndex, hintCount: 0, fallback: true });
    }
    return candidates.map((candidate, index) => {
        const nextHeader = candidates[index + 1]?.headerRowIndex ?? matrix.length;
        let endRowIndex = nextHeader - 1;
        while (endRowIndex > candidate.headerRowIndex && populatedCells(matrix[endRowIndex]).length === 0) endRowIndex -= 1;
        return { ...candidate, dataStartRowIndex: candidate.headerRowIndex + 1, endRowIndex };
    });
}

export function uniqueHeaders(row) {
    const counts = new Map();
    return (row || []).map((value, index) => {
        const base = String(value ?? '').trim() || `Colonna_${index + 1}`;
        const count = (counts.get(base) || 0) + 1;
        counts.set(base, count);
        return count === 1 ? base : `${base}_${count}`;
    });
}

const MASTER_ALIASES = Object.freeze({
    delivery_point: {
        codice_punto_committente: ['codice_punto_committente', 'codice_esterno', 'codice'],
        denominazione_punto: ['denominazione_punto', 'nome', 'denominazione'],
        indirizzo: ['indirizzo'], numero_civico: ['numero_civico', 'civico'],
        cap: ['cap'], localita: ['localita', 'citta'], provincia: ['provincia'],
        telefono: ['telefono', 'cellulare'], note_consegna: ['note_consegna', 'note'],
        codice_zona_logistica: ['codice_zona_logistica', 'codice_zona']
    },
    article: {
        codice_articolo_committente: ['codice_articolo_committente', 'codice_articolo', 'codice_esterno', 'codice'],
        codice_articolo_operativo: ['codice_articolo_operativo', 'codice_secondario'],
        descrizione_articolo: ['descrizione_articolo', 'descrizione', 'nome']
    }
});

function normalizedComparable(value) {
    return String(value ?? '').trim().replace(/\s+/g, ' ').toUpperCase();
}

function masterValue(master, aliases) {
    for (const alias of aliases) {
        if (master[alias] !== undefined && master[alias] !== null && master[alias] !== '') return master[alias];
    }
    return null;
}

export function reconcileNormalizedRecords(records, masters, tenantId) {
    const domains = [
        { name: 'delivery_point', key: 'codice_punto_committente', rows: masters.deliveryPoints || [] },
        { name: 'article', key: 'codice_articolo_committente', rows: masters.articles || [] }
    ];
    const results = [];
    records.forEach((record, recordIndex) => {
        domains.forEach(domain => {
            const incomingKey = normalizedComparable(record.data?.[domain.key]);
            if (!incomingKey) return;
            const aliases = MASTER_ALIASES[domain.name];
            const matches = domain.rows.filter(master => normalizedComparable(masterValue(master, aliases[domain.key])) === incomingKey);
            if (!matches.length) {
                results.push({ record_index: recordIndex, domain: domain.name, key: incomingKey, status: 'NEW', differences: [] });
                return;
            }
            if (matches.length > 1) {
                results.push({ record_index: recordIndex, domain: domain.name, key: incomingKey, status: 'AMBIGUOUS', match_ids: matches.map(item => item.id), differences: [] });
                return;
            }
            const master = matches[0];
            const differences = [];
            Object.entries(aliases).forEach(([canonicalField, fieldAliases]) => {
                const incomingValue = record.data?.[canonicalField];
                if (incomingValue === undefined || incomingValue === null || incomingValue === '') return;
                const existingValue = masterValue(master, fieldAliases);
                if (normalizedComparable(incomingValue) !== normalizedComparable(existingValue)) {
                    differences.push({ field: canonicalField, existing: existingValue, incoming: incomingValue });
                }
            });
            results.push({
                record_index: recordIndex,
                domain: domain.name,
                key: incomingKey,
                status: differences.length ? 'MODIFIED' : 'IDENTICAL',
                match_id: master.id,
                tenant_id: tenantId,
                differences
            });
        });
    });
    return results;
}

export const PROFILE_STATES = Object.freeze(['DRAFT', 'REVIEWED', 'TESTED', 'CERTIFIED']);

export function advanceProfileState(profile, targetState, evidence = {}) {
    const current = profile.status || 'DRAFT';
    const currentIndex = PROFILE_STATES.indexOf(current);
    const targetIndex = PROFILE_STATES.indexOf(targetState);
    if (currentIndex < 0 || targetIndex !== currentIndex + 1) {
        throw new Error(`Transizione profilo non consentita: ${current} -> ${targetState}.`);
    }
    if (targetState === 'REVIEWED' && !evidence.operator_id) {
        throw new Error('La revisione richiede l’identità dell’operatore.');
    }
    if (targetState === 'TESTED' && !(evidence.tests_total > 0) ) {
        throw new Error('Il collaudo richiede almeno un test registrato.');
    }
    if (targetState === 'TESTED' && evidence.tests_passed !== evidence.tests_total) {
        throw new Error('Il profilo non può essere collaudato con test falliti.');
    }
    if (targetState === 'CERTIFIED' && !evidence.approved_by) {
        throw new Error('La certificazione richiede un’approvazione umana esplicita.');
    }
    return {
        ...profile,
        status: targetState,
        lifecycle: [...(profile.lifecycle || []), {
            from: current,
            to: targetState,
            at: evidence.at || new Date().toISOString(),
            evidence
        }]
    };
}

export function applyReconciliationDecisions(reconciliation, decisions = {}) {
    return reconciliation.map((item, itemIndex) => ({
        ...item,
        differences: item.differences.map((difference, differenceIndex) => {
            const decision = decisions[`${itemIndex}:${differenceIndex}`] || 'KEEP_EXISTING';
            if (!['KEEP_EXISTING', 'REPLACE', 'ADD_AS_NOTE'].includes(decision)) {
                throw new Error(`Decisione di confronto non valida: ${decision}.`);
            }
            return { ...difference, decision };
        })
    }));
}
