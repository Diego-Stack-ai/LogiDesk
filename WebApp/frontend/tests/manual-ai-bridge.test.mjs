import assert from 'node:assert/strict';
import test from 'node:test';

import {
    BRIDGE_SCHEMA_VERSION,
    applyMappings,
    anonymizeRows,
    buildManualPrompt,
    createStructuralSignature,
    detectTableRegions,
    findCandidateDuplicates,
    advanceProfileState,
    applyReconciliationDecisions,
    reconcileNormalizedRecords,
    uniqueHeaders,
    validateManualResponse
} from '../services/manual-ai-bridge.js';

test('anonymizes string values and preserves numbers', () => {
    const result = anonymizeRows([{ Cliente: 'Riservato', Peso: 25.5 }]);
    assert.match(result[0].Cliente, /^<CLIENTE_[0-9a-f]{8}>$/);
    assert.equal(result[0].Peso, 25.5);
});

test('requires sequential, evidenced profile certification', () => {
    const reviewed = advanceProfileState({ status: 'DRAFT' }, 'REVIEWED', { operator_id: 'op' });
    const tested = advanceProfileState(reviewed, 'TESTED', { tests_total: 3, tests_passed: 3 });
    const certified = advanceProfileState(tested, 'CERTIFIED', { approved_by: 'op' });
    assert.equal(certified.status, 'CERTIFIED');
    assert.throws(() => advanceProfileState({ status: 'DRAFT' }, 'CERTIFIED', { approved_by: 'op' }), /non consentita/);
});

test('records field decisions without mutating master data', () => {
    const source = [{ status: 'MODIFIED', differences: [{ field: 'indirizzo', existing: 'A', incoming: 'B' }] }];
    const reviewed = applyReconciliationDecisions(source, { '0:0': 'REPLACE' });
    assert.equal(reviewed[0].differences[0].decision, 'REPLACE');
    assert.equal(source[0].differences[0].decision, undefined);
});

test('requires an explicit tenant', () => {
    assert.throws(() => buildManualPrompt({
        file: { name: 'test.xlsx', kind: 'excel', size: 1, sections: [], sampleRows: [] },
        companyId: 'company', tenantId: '', workDate: '2026-09-04'
    }), /Committente obbligatorio/);
});

test('structural signature ignores row values but preserves layout', () => {
    const base = { kind: 'excel', sections: [{ name: 'Riepilogo', columns: ['Giro', 'Peso'] }] };
    const first = createStructuralSignature({ ...base, sampleRows: [{ Giro: 'A', Peso: 10 }] });
    const second = createStructuralSignature({ ...base, sampleRows: [{ Giro: 'B', Peso: 20 }] });
    const changed = createStructuralSignature({ kind: 'excel', sections: [{ name: 'Riepilogo', columns: ['Zona', 'Peso'] }], sampleRows: [] });
    assert.equal(first, second);
    assert.notEqual(first, changed);
});

test('validates a supported response', () => {
    const response = validateManualResponse(JSON.stringify({
        schema_version: BRIDGE_SCHEMA_VERSION,
        tipo_documento: 'ddt',
        numero_giri_proposto: 1,
        mapping: [{
            campo_sorgente: 'Codice destinazione',
            campo_logidesk: 'codice_punto_committente',
            confidenza: 0.9
        }],
        ambiguita: [], campi_nuovi: [], avvisi: []
    }));
    assert.equal(response.numero_giri_proposto, 1);
});

test('rejects an invented canonical field', () => {
    assert.throws(() => validateManualResponse(JSON.stringify({
        schema_version: BRIDGE_SCHEMA_VERSION,
        tipo_documento: 'ddt',
        numero_giri_proposto: 1,
        mapping: [{ campo_sorgente: 'X', campo_logidesk: 'inventato', confidenza: 0.5 }]
    })), /sconosciuto/);
});

test('applies mappings and detects duplicated delivery point codes per tenant', () => {
    const records = applyMappings([
        { Dest: 'P001', Peso: 10 },
        { Dest: 'P001', Peso: 20 }
    ], [
        { campo_sorgente: 'Dest', campo_logidesk: 'codice_punto_committente' },
        { campo_sorgente: 'Peso', campo_logidesk: 'peso' }
    ]);
    assert.deepEqual(records[0].data, { codice_punto_committente: 'P001', peso: 10 });
    assert.equal(findCandidateDuplicates(records, 'tenant-a').length, 1);
});

test('rejects two source columns mapped to the same canonical field', () => {
    assert.throws(() => applyMappings([{ A: 1, B: 2 }], [
        { campo_sorgente: 'A', campo_logidesk: 'peso' },
        { campo_sorgente: 'B', campo_logidesk: 'peso' }
    ]), /associato più di una volta/);
});

test('detects multiple tables in one worksheet', () => {
    const matrix = [
        ['Mezzo', 'Giorno', 'Autista', 'KM'],
        ['AA001AA', '2026-09-04', 'Autista', 100],
        [null, null, null, null],
        ['Codice cliente', 'Nome cliente', 'Indirizzo', 'Quantità'],
        ['P001', 'Cliente', 'Via', 10]
    ];
    const regions = detectTableRegions(matrix);
    assert.equal(regions.length, 2);
    assert.equal(regions[0].headerRowIndex, 0);
    assert.equal(regions[0].endRowIndex, 1);
    assert.equal(regions[1].headerRowIndex, 3);
});

test('creates unique names for empty and duplicated headers', () => {
    assert.deepEqual(uniqueHeaders(['Codice', '', 'Codice']), ['Codice', 'Colonna_2', 'Codice_2']);
});

test('reconciles tenant records as identical, modified or new', () => {
    const records = [
        { data: { codice_punto_committente: 'p001', indirizzo: 'Via Roma 1' } },
        { data: { codice_articolo_committente: 'A-1', descrizione_articolo: 'Nuova descrizione' } },
        { data: { codice_punto_committente: 'P999' } }
    ];
    const result = reconcileNormalizedRecords(records, {
        deliveryPoints: [{ id: 'dp1', codice_esterno: 'P001', indirizzo: 'Via Roma 1' }],
        articles: [{ id: 'a1', codice: 'A-1', descrizione: 'Vecchia descrizione' }]
    }, 'tenant-a');
    assert.equal(result[0].status, 'IDENTICAL');
    assert.equal(result[1].status, 'MODIFIED');
    assert.equal(result[1].differences[0].field, 'descrizione_articolo');
    assert.equal(result[2].status, 'NEW');
});
