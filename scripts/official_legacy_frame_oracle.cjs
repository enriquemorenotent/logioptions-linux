// Differential oracle using the embedded 1.32 network.js source map content.
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
if (!source.trimEnd().endsWith('export default network;')) throw Error('Unknown source layout');
const factory = vm.runInNewContext(source.replace(/export default network;\s*$/, 'network;'), {Buffer}, {timeout: 2000});
const payloads = JSON.parse(fs.readFileSync(0, 'utf8'));
const results = payloads.map(payload => {
  const writes = [];
  const socket = {destroyed: false, cork() {}, uncork() {}, write(bytes) {writes.push(bytes)}};
  factory(socket, () => {}).send(Buffer.from(payload, 'base64'));
  return Buffer.concat(writes).toString('hex');
});
process.stdout.write(JSON.stringify(results));
