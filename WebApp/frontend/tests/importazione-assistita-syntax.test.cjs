const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('inline module of importazione assistita has valid syntax', () => {
    const htmlPath = path.resolve(__dirname, '..', 'importazione_assistita.html');
    const html = fs.readFileSync(htmlPath, 'utf8');
    const marker = '<script type="module">';
    const start = html.indexOf(marker);
    const end = html.indexOf('</script>', start);
    assert.notEqual(start, -1, 'module script missing');
    assert.notEqual(end, -1, 'module script closing tag missing');
    const source = html
        .slice(start + marker.length, end)
        .split(/\r?\n/)
        .filter(line => !line.trimStart().startsWith('import '))
        .join('\n');
    new vm.Script(`(function () {${source}\n})`);
});

test('local ingestion lab has no DNR tenant or source-channel fallback', () => {
    const htmlPath = path.resolve(__dirname, '..', '..', 'tools', 'local-ingestion-lab.html');
    const html = fs.readFileSync(htmlPath, 'utf8');
    assert.doesNotMatch(html, /id="tenant"[^>]*value="DNR"/i);
    assert.match(html, /id="tenant"[^>]*required/i);
    assert.match(html, /source_channel:\$\('sourceChannel'\)\.value\.trim\(\)\|\|null/);
});
