const express = require('express');
const { v4: uuidv4 } = require('uuid');
const db = require('../db');
const { parseDSL, detectCycle } = require('../engine/dag');
const executor = require('../engine/WorkflowExecutor');
const { getAllNodeTypes } = require('../nodes/registry');

const router = express.Router();

router.get('/', (req, res) => {
  const workflows = db.prepare('SELECT * FROM workflows ORDER BY created_at DESC').all();
  res.json(workflows);
});

router.get('/node-types', (req, res) => {
  const types = getAllNodeTypes();
  res.json(types);
});

router.get('/:id', (req, res) => {
  const { id } = req.params;
  const workflow = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id);
  if (!workflow) {
    return res.status(404).json({ error: 'Workflow not found' });
  }
  res.json(workflow);
});

router.post('/', (req, res) => {
  const { name, dsl_json } = req.body;
  const id = uuidv4();

  if (dsl_json) {
    try {
      const { nodes, edges } = parseDSL(dsl_json);
      if (detectCycle(nodes, edges)) {
        return res.status(400).json({ error: 'DSL contains a cycle' });
      }
    } catch (error) {
      return res.status(400).json({ error: 'Invalid DSL JSON' });
    }
  }

  db.prepare(`
    INSERT INTO workflows (id, name, dsl_json, status)
    VALUES (?, ?, ?, 'idle')
  `).run(id, name, dsl_json ? JSON.stringify(dsl_json) : null);

  const workflow = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id);
  res.status(201).json(workflow);
});

router.put('/:id', (req, res) => {
  const { id } = req.params;
  const { name, dsl_json } = req.body;

  const existing = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id);
  if (!existing) {
    return res.status(404).json({ error: 'Workflow not found' });
  }

  if (dsl_json) {
    try {
      const { nodes, edges } = parseDSL(dsl_json);
      if (detectCycle(nodes, edges)) {
        return res.status(400).json({ error: 'DSL contains a cycle' });
      }
    } catch (error) {
      return res.status(400).json({ error: 'Invalid DSL JSON' });
    }
  }

  db.prepare(`
    UPDATE workflows
    SET name = ?, dsl_json = ?
    WHERE id = ?
  `).run(
    name || existing.name,
    dsl_json ? JSON.stringify(dsl_json) : existing.dsl_json,
    id
  );

  const workflow = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id);
  res.json(workflow);
});

router.delete('/:id', (req, res) => {
  const { id } = req.params;

  const existing = db.prepare('SELECT * FROM workflows WHERE id = ?').get(id);
  if (!existing) {
    return res.status(404).json({ error: 'Workflow not found' });
  }

  db.prepare('DELETE FROM execution_logs WHERE execution_id IN (SELECT id FROM executions WHERE workflow_id = ?)').run(id);
  db.prepare('DELETE FROM executions WHERE workflow_id = ?').run(id);
  db.prepare('DELETE FROM workflows WHERE id = ?').run(id);

  res.json({ message: 'Workflow deleted' });
});

router.post('/:id/execute', async (req, res) => {
  const { id } = req.params;

  try {
    const executionId = await executor.executeWorkflow(id, 'manual');
    res.status(201).json({ executionId });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

router.get('/:id/executions', (req, res) => {
  const { id } = req.params;
  const executions = db.prepare(`
    SELECT * FROM executions
    WHERE workflow_id = ?
    ORDER BY started_at DESC
    LIMIT 50
  `).all(id);
  res.json(executions);
});

module.exports = router;
