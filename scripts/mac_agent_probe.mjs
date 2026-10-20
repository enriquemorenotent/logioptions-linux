// Run on the test Mac with the official Options+ UI's loopback debugger enabled.
// Use the official UI's existing connection; do not replace or patch the agent.
const port = Number(process.env.OPTIONSPLUS_DEBUG_PORT || 19222);
const allowed = new Set(['/devices/list', '/configuration', '/permissions', '/v2/profiles', '/logging/optionsplus_backend/status']);
const deviceRoute = /^\/(battery\/dev[0-9a-f]+\/state|devices\/dev[0-9a-f]+\/easy_switch|smartshift\/dev[0-9a-f]+\/params)$/;
const hapticRoute = /^\/haptics\/dev[0-9a-f]+\/(config|status|event_sources)$/;
const paths = process.argv.slice(2);
if (!paths.length) paths.push('/devices/list');
for (const path of paths) {
  if (!allowed.has(path) && !deviceRoute.test(path) && !hapticRoute.test(path)) throw Error(`Route is not in the read-only probe allowlist: ${path}`);
}
const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const page = pages.find(p => p.title === 'Logi Options+' && p.url.startsWith('file:///Applications/logioptionsplus.app/'));
if (!page) throw Error('Official Options+ page not found');
const ws = new WebSocket(page.webSocketDebuggerUrl);
const result = await new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(Error('Debugger request timed out')), paths.length * 6000 + 3000);
  ws.addEventListener('error', () => {clearTimeout(timeout); reject(Error('Debugger connection failed'))});
  ws.addEventListener('open', () => {
    const expression = `(async () => {
      const replies = [];
      for (const path of ${JSON.stringify(paths)}) {
        replies.push(await new Promise(resolve => {
          const timer = setTimeout(() => resolve({path, error: 'Agent response timed out'}), 5000);
          globalThis.connection.send('GET', path, response => {
            clearTimeout(timer);
            resolve(response);
          });
        }));
      }
      return replies;
    })()`;
    ws.send(JSON.stringify({id: 1, method: 'Runtime.evaluate', params: {
      expression, awaitPromise: true, returnByValue: true,
    }}));
  });
  ws.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id !== 1) return;
    clearTimeout(timeout);
    if (message.error || message.result?.exceptionDetails) {
      reject(Error(JSON.stringify(message.error || message.result.exceptionDetails)));
    } else resolve(message.result.result.value);
  });
}).finally(() => ws.close());
console.log(JSON.stringify({capturedAt: new Date().toISOString(), replies: result}, null, 2));
