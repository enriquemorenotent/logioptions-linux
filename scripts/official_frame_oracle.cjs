// Execute only the recovered framing factory with a mock socket and stub imports.
// The complete official application is never loaded or launched.
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const start = source.indexOf('2824:(t,e,r)=>');
const end = source.indexOf(',21136:', start);
if (start < 0 || end < 0) throw Error('Unsupported official bundle layout');
const factory = source.slice(start + 5, end);
const context = vm.createContext({
  factorySource: factory,
  Buffer,
  payloads: JSON.parse(fs.readFileSync(0, 'utf8')),
  console: {log() {}, error() {}},
});
const result = vm.runInContext(`
  const mod = {exports: {}};
  const factory = eval('(' + factorySource + ')');
  factory(mod, {}, id => {
    if (id === 4573) return {Buffer};
    if (id === 71655) return {isNetworkLogsEnabled: () => false};
    throw Error('Unexpected dependency: ' + id);
  });
  payloads.map(base64 => {
    const writes = [];
    const socket = {destroyed: false, cork() {}, uncork() {}, write(bytes) {writes.push(bytes)}};
    mod.exports.network(socket, () => {}).send(Buffer.from(base64, 'base64'));
    return Buffer.concat(writes).toString('hex');
  });
`, context, {timeout: 2000});
process.stdout.write(JSON.stringify(result));
