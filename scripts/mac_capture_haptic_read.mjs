// Capture official diagnostic logs around a read-only haptic settings query.
// This script does not send vibration or haptic-configuration writes.
const pages = await (await fetch('http://127.0.0.1:19222/json/list')).json();
const page = pages.find(p => p.title === 'Logi Options+' && p.url.startsWith('file:///Applications/logioptionsplus.app/'));
if (!page) throw Error('Official Options+ UI not found');
const ws = new WebSocket(page.webSocketDebuggerUrl);
const expression = `(async () => {
  const trace = [];
  const request = (verb, path, payload) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Agent timeout: ' + path)), 5000);
    const callback = response => {
      clearTimeout(timer);
      trace.push({verb, path, payload, response});
      if (response.result?.code !== 'SUCCESS') reject(Error(JSON.stringify(response.result)));
      else resolve(response);
    };
    if (payload === undefined) globalThis.connection.send(verb, path, callback);
    else globalThis.connection.send(verb, path, payload, callback);
  });
  let restoreDisabled = false;
  try {
    const baseline = await request('GET', '/logging/optionsplus_backend/status');
    if (!baseline.payload?.enabledByUser && !baseline.payload?.enabledByCfg) {
      restoreDisabled = true;
      await request('SET', '/logging/optionsplus_backend/trigger', {action: 'ENABLE'});
    }
    const devices = await request('GET', '/devices/list');
    const device = devices.payload.deviceInfos.find(d => d.displayName === 'MX Master 4' && d.state === 'ACTIVE' && d.supported);
    if (!device) throw Error('Supported MX Master 4 is not active');
    await request('GET', '/haptics/' + device.id + '/config');
    await request('SET', '/logging/optionsplus_backend/trigger', {
      action: 'SAVE', userLogsArchivePath: '/tmp/logioptions-research/haptic-read-logs.zip',
    });
  } catch (error) {
    trace.push({error: String(error)});
  } finally {
    if (restoreDisabled) {
      try { await request('SET', '/logging/optionsplus_backend/trigger', {action: 'DISABLE'}); }
      catch (error) { trace.push({restoreError: String(error)}); }
    }
  }
  return trace;
})()`;
try {
  const result = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Capture timeout')), 45000);
    ws.addEventListener('open', () => ws.send(JSON.stringify({id: 1, method: 'Runtime.evaluate', params: {
      expression, awaitPromise: true, returnByValue: true,
    }})));
    ws.addEventListener('error', () => {clearTimeout(timer); reject(Error('Debugger connection failed'))});
    ws.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      if (message.id !== 1) return;
      clearTimeout(timer);
      if (message.error || message.result?.exceptionDetails) reject(Error(JSON.stringify(message)));
      else resolve(message.result.result.value);
    });
  });
  console.log(JSON.stringify({capturedAt: new Date().toISOString(), trace: result}, null, 2));
} finally {
  ws.close();
}
