global.window = {}; global.document = undefined;
const { verCmp } = require('../ui.js');
const assert = require('assert');
// nomes de versão do app: por número, nunca como texto ("1.10" < "1.9" seria o erro)
assert.ok(verCmp('1.10', '1.9') > 0); assert.ok(verCmp('1.13', '1.9') > 0); assert.ok(verCmp('1.14', '1.13') > 0);
assert.ok(verCmp('1.9', '1.10') < 0); assert.ok(verCmp('2.0', '1.99') > 0); assert.strictEqual(verCmp('1.13', '1.13.0'), 0);
assert.ok(verCmp('1.13.1', '1.13') > 0); assert.ok(verCmp('1.13', '1.14') < 0); assert.strictEqual(verCmp('', null), 0);
console.log('test_versao ok');
