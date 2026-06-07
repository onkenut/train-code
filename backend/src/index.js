const express = require('express');
const http = require('http');
const cors = require('cors');
const path = require('path');

const workflowsRouter = require('./routes/workflows');
const executionsRouter = require('./routes/executions');
const setupWebSocket = require('./websocket');
const db = require('./db');

const app = express();
const server = http.createServer(app);

const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

app.use('/api/workflows', workflowsRouter);
app.use('/api/executions', executionsRouter);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

const frontendDist = path.join(__dirname, '..', '..', 'frontend', 'dist');
app.use(express.static(frontendDist));
app.get('*', (req, res, next) => {
  if (req.path.startsWith('/api/') || req.path.startsWith('/ws')) {
    return next();
  }
  res.sendFile(path.join(frontendDist, 'index.html'));
});

async function start() {
  try {
    await db.init();

    setupWebSocket(server);

    server.listen(PORT, () => {
      console.log(`
╔══════════════════════════════════════════════════════════════╗
║                    FlowForge Engine                         ║
╠══════════════════════════════════════════════════════════════╣
║  Server running on: http://localhost:${PORT}                   ║
║  WebSocket:        ws://localhost:${PORT}/ws                  ║
║  API Base:         http://localhost:${PORT}/api               ║
╚══════════════════════════════════════════════════════════════╝
      `);
    });
  } catch (error) {
    console.error('Failed to start server:', error);
    process.exit(1);
  }
}

start();
