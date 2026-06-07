const express = require('express');
const db = require('../db');
const executor = require('../engine/WorkflowExecutor');

const router = express.Router();

router.get('/', (req, res) => {
  const executions = db.prepare(`
    SELECT e.*, w.name as workflow_name
    FROM executions e
    LEFT JOIN workflows w ON e.workflow_id = w.id
    ORDER BY e.started_at DESC
    LIMIT 100
  `).all();
  res.json(executions);
});

router.get('/:id', (req, res) => {
  const { id } = req.params;
  const execution = db.prepare(`
    SELECT e.*, w.name as workflow_name, w.dsl_json
    FROM executions e
    LEFT JOIN workflows w ON e.workflow_id = w.id
    WHERE e.id = ?
  `).get(id);
  
  if (!execution) {
    return res.status(404).json({ error: 'Execution not found' });
  }
  
  const runtimeStatus = executor.getExecutionStatus(id);
  if (runtimeStatus) {
    execution.runtimeStatus = runtimeStatus;
  }
  
  res.json(execution);
});

router.get('/:id/logs', (req, res) => {
  const { id } = req.params;
  const logs = db.prepare(`
    SELECT * FROM execution_logs
    WHERE execution_id = ?
    ORDER BY id ASC
  `).all(id);
  
  const formattedLogs = logs.map(log => ({
    ...log,
    input_data: log.input_data ? JSON.parse(log.input_data) : null,
    output_data: log.output_data ? JSON.parse(log.output_data) : null
  }));
  
  res.json(formattedLogs);
});

router.post('/:id/pause', (req, res) => {
  const { id } = req.params;
  const success = executor.pauseExecution(id);
  
  if (!success) {
    return res.status(400).json({ error: 'Cannot pause execution' });
  }
  
  res.json({ message: 'Execution paused' });
});

router.post('/:id/resume', (req, res) => {
  const { id } = req.params;
  const success = executor.resumeExecution(id);
  
  if (!success) {
    return res.status(400).json({ error: 'Cannot resume execution' });
  }
  
  res.json({ message: 'Execution resumed' });
});

router.post('/:id/terminate', (req, res) => {
  const { id } = req.params;
  const success = executor.terminateExecution(id);
  
  if (!success) {
    return res.status(400).json({ error: 'Cannot terminate execution' });
  }
  
  res.json({ message: 'Execution terminated' });
});

module.exports = router;
