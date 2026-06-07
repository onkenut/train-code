const WebSocket = require('ws');
const executor = require('./engine/WorkflowExecutor');

function setupWebSocket(server) {
  const wss = new WebSocket.Server({ server, path: '/ws' });

  const clients = new Map();

  wss.on('connection', (ws) => {
    const clientId = Date.now().toString();
    clients.set(clientId, { ws, subscriptions: new Set() });

    ws.on('message', (message) => {
      try {
        const data = JSON.parse(message);
        const client = clients.get(clientId);

        if (!client) return;

        switch (data.type) {
          case 'subscribe':
            if (data.executionId) {
              client.subscriptions.add(data.executionId);
            }
            break;
          case 'unsubscribe':
            if (data.executionId) {
              client.subscriptions.delete(data.executionId);
            }
            break;
        }
      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    });

    ws.on('close', () => {
      clients.delete(clientId);
    });
  });

  function broadcast(event, data) {
    const message = JSON.stringify({ event, data });
    clients.forEach((client) => {
      if (client.ws.readyState === WebSocket.OPEN) {
        if (data.executionId) {
          if (client.subscriptions.has(data.executionId)) {
            client.ws.send(message);
          }
        } else {
          client.ws.send(message);
        }
      }
    });
  }

  executor.on('execution:start', (data) => broadcast('execution:start', data));
  executor.on('execution:complete', (data) => broadcast('execution:complete', data));
  executor.on('execution:fail', (data) => broadcast('execution:fail', data));
  executor.on('execution:pause', (data) => broadcast('execution:pause', data));
  executor.on('execution:resume', (data) => broadcast('execution:resume', data));
  executor.on('execution:terminate', (data) => broadcast('execution:terminate', data));

  executor.on('node:start', (data) => broadcast('node:start', data));
  executor.on('node:complete', (data) => broadcast('node:complete', data));
  executor.on('node:error', (data) => broadcast('node:error', data));
  executor.on('node:skip', (data) => broadcast('node:skip', data));

  return wss;
}

module.exports = setupWebSocket;
