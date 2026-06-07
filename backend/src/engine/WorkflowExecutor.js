const EventEmitter = require('events');
const { v4: uuidv4 } = require('uuid');
const { LRUCache } = require('lru-cache');
const { parseDSL, topologicalSort, getPredecessors, getSuccessors } = require('./dag');
const { createNode } = require('../nodes/registry');
const db = require('../db');

class WorkflowExecutor extends EventEmitter {
  constructor() {
    super();
    this.executions = new Map();
    this.contextCache = new LRUCache({
      max: 500,
      ttl: 1000 * 60 * 60
    });
  }

  async executeWorkflow(workflowId, triggerType = 'manual') {
    const workflow = db.prepare('SELECT * FROM workflows WHERE id = ?').get(workflowId);
    if (!workflow) {
      throw new Error('Workflow not found');
    }

    if (!workflow.dsl_json) {
      throw new Error('Workflow DSL is empty');
    }

    const executionId = uuidv4();
    const now = new Date().toISOString();

    db.prepare(`
      INSERT INTO executions (id, workflow_id, trigger_type, status, started_at)
      VALUES (?, ?, ?, 'running', ?)
    `).run(executionId, workflowId, triggerType, now);

    const execution = {
      id: executionId,
      workflowId,
      status: 'running',
      nodes: new Map(),
      nodeStatuses: new Map(),
      pendingDependencies: new Map(),
      results: new Map(),
      paused: false,
      terminated: false,
      startedAt: now
    };

    this.executions.set(executionId, execution);

    try {
      const { nodes, edges } = parseDSL(workflow.dsl_json);

      nodes.forEach((node, nodeId) => {
        execution.nodes.set(nodeId, createNode(node));
        execution.nodeStatuses.set(nodeId, 'pending');
        const predecessors = getPredecessors(nodeId, edges);
        execution.pendingDependencies.set(nodeId, new Set(predecessors));
      });

      this.emit('execution:start', {
        executionId,
        workflowId,
        timestamp: now
      });

      await this.scheduleReadyNodes(execution, nodes, edges);

    } catch (error) {
      this.failExecution(executionId, error.message);
      throw error;
    }

    return executionId;
  }

  async scheduleReadyNodes(execution, nodes, edges) {
    if (execution.terminated) return;

    if (execution.paused) {
      return;
    }

    const readyNodes = [];
    execution.pendingDependencies.forEach((deps, nodeId) => {
      if (deps.size === 0 && execution.nodeStatuses.get(nodeId) === 'pending') {
        readyNodes.push(nodeId);
      }
    });

    if (readyNodes.length === 0) {
      const allCompleted = Array.from(execution.nodeStatuses.values()).every(
        s => s === 'completed' || s === 'failed'
      );
      if (allCompleted) {
        const hasFailed = Array.from(execution.nodeStatuses.values()).includes('failed');
        if (hasFailed) {
          this.failExecution(execution.id, 'One or more nodes failed');
        } else {
          this.completeExecution(execution.id);
        }
      }
      return;
    }

    await Promise.all(
      readyNodes.map(nodeId => this.executeNode(execution, nodeId, nodes, edges))
    );
  }

  async executeNode(execution, nodeId, nodes, edges) {
    if (execution.terminated) return;
    if (execution.paused) return;

    const node = execution.nodes.get(nodeId);
    if (!node) return;

    execution.nodeStatuses.set(nodeId, 'running');

    const now = new Date().toISOString();
    db.prepare(`
      INSERT INTO execution_logs (execution_id, node_id, status, started_at)
      VALUES (?, ?, 'running', ?)
    `).run(execution.id, nodeId, now);

    this.emit('node:start', {
      executionId: execution.id,
      nodeId,
      nodeType: node.type,
      timestamp: now
    });

    try {
      const predecessors = getPredecessors(nodeId, edges);
      const inputs = {};

      for (const predId of predecessors) {
        const result = execution.results.get(predId);
        if (result) {
          if (node.type === 'condition') {
            Object.assign(inputs, result);
          } else {
            const edge = edges.find(e => e.source === predId && e.target === nodeId);
            if (edge && edge.sourceHandle) {
              const predNode = nodes.get(predId);
              if (predNode && predNode.type === 'condition') {
                if (result.branch === edge.sourceHandle) {
                  Object.assign(inputs, result.input || {});
                } else {
                  execution.nodeStatuses.set(nodeId, 'skipped');
                  this.skipNode(execution, nodeId, 'Condition not met');
                  await this.handleNodeCompletion(execution, nodeId, edges, nodes);
                  return;
                }
              }
            } else {
              Object.assign(inputs, result);
            }
          }
        }
      }

      const logId = db.prepare('SELECT last_insert_rowid() as id').get().id;
      db.prepare(`
        UPDATE execution_logs
        SET input_data = ?
        WHERE id = ?
      `).run(JSON.stringify(inputs), logId);

      const context = {
        executionId: execution.id,
        nodeId,
        cache: this.contextCache
      };

      const output = await node.execute(inputs, context);

      const cacheKey = `${execution.id}:${nodeId}`;
      this.contextCache.set(cacheKey, output);
      execution.results.set(nodeId, output);

      if (output && output.success === false) {
        throw new Error(output.error || 'Node execution failed');
      }

      execution.nodeStatuses.set(nodeId, 'completed');
      const finishTime = new Date().toISOString();

      db.prepare(`
        UPDATE execution_logs
        SET status = 'completed', output_data = ?, finished_at = ?
        WHERE execution_id = ? AND node_id = ? AND status = 'running'
      `).run(JSON.stringify(output), finishTime, execution.id, nodeId);

      this.emit('node:complete', {
        executionId: execution.id,
        nodeId,
        output,
        timestamp: finishTime
      });

    } catch (error) {
      execution.nodeStatuses.set(nodeId, 'failed');
      const finishTime = new Date().toISOString();

      db.prepare(`
        UPDATE execution_logs
        SET status = 'failed', error_msg = ?, finished_at = ?
        WHERE execution_id = ? AND node_id = ? AND status = 'running'
      `).run(error.message, finishTime, execution.id, nodeId);

      this.emit('node:error', {
        executionId: execution.id,
        nodeId,
        error: error.message,
        timestamp: finishTime
      });
    }

    await this.handleNodeCompletion(execution, nodeId, edges, nodes);
  }

  async skipNode(execution, nodeId, reason) {
    const finishTime = new Date().toISOString();
    db.prepare(`
      UPDATE execution_logs
      SET status = 'skipped', error_msg = ?, finished_at = ?
      WHERE execution_id = ? AND node_id = ? AND status = 'running'
    `).run(reason, finishTime, execution.id, nodeId);

    this.emit('node:skip', {
      executionId: execution.id,
      nodeId,
      reason,
      timestamp: finishTime
    });
  }

  async handleNodeCompletion(execution, nodeId, edges, nodes) {
    const successors = getSuccessors(nodeId, edges);
    const nodeStatus = execution.nodeStatuses.get(nodeId);

    for (const succId of successors) {
      const deps = execution.pendingDependencies.get(succId);
      if (deps) {
        deps.delete(nodeId);
      }

      if (nodeStatus === 'failed') {
        const succNode = nodes.get(succId);
        if (succNode && succNode.type !== 'condition') {
          execution.nodeStatuses.set(succId, 'failed');
          this.skipNode(execution, succId, 'Upstream node failed');
        }
      }
    }

    setTimeout(() => {
      this.scheduleReadyNodes(execution, nodes, edges);
    }, 0);
  }

  completeExecution(executionId) {
    const execution = this.executions.get(executionId);
    if (!execution) return;

    execution.status = 'completed';
    const now = new Date().toISOString();

    db.prepare(`
      UPDATE executions
      SET status = 'completed', finished_at = ?
      WHERE id = ?
    `).run(now, executionId);

    this.emit('execution:complete', {
      executionId,
      timestamp: now
    });

    setTimeout(() => {
      this.cleanupExecution(executionId);
    }, 5000);
  }

  failExecution(executionId, errorMessage) {
    const execution = this.executions.get(executionId);
    if (!execution) return;

    execution.status = 'failed';
    execution.terminated = true;
    const now = new Date().toISOString();

    db.prepare(`
      UPDATE executions
      SET status = 'failed', finished_at = ?
      WHERE id = ?
    `).run(now, executionId);

    this.emit('execution:fail', {
      executionId,
      error: errorMessage,
      timestamp: now
    });

    setTimeout(() => {
      this.cleanupExecution(executionId);
    }, 5000);
  }

  pauseExecution(executionId) {
    const execution = this.executions.get(executionId);
    if (!execution || execution.status !== 'running') return false;

    execution.paused = true;
    this.emit('execution:pause', { executionId });
    return true;
  }

  resumeExecution(executionId) {
    const execution = this.executions.get(executionId);
    if (!execution || !execution.paused) return false;

    execution.paused = false;
    this.emit('execution:resume', { executionId });

    const workflow = db.prepare('SELECT dsl_json FROM workflows WHERE id = ?').get(execution.workflowId);
    if (workflow && workflow.dsl_json) {
      const { nodes, edges } = parseDSL(workflow.dsl_json);
      this.scheduleReadyNodes(execution, nodes, edges);
    }

    return true;
  }

  terminateExecution(executionId) {
    const execution = this.executions.get(executionId);
    if (!execution) return false;

    execution.terminated = true;
    execution.status = 'terminated';
    const now = new Date().toISOString();

    db.prepare(`
      UPDATE executions
      SET status = 'terminated', finished_at = ?
      WHERE id = ?
    `).run(now, executionId);

    this.emit('execution:terminate', {
      executionId,
      timestamp: now
    });

    setTimeout(() => {
      this.cleanupExecution(executionId);
    }, 1000);

    return true;
  }

  cleanupExecution(executionId) {
    const execution = this.executions.get(executionId);
    if (!execution) return;

    for (const [key] of this.contextCache) {
      if (key.startsWith(`${executionId}:`)) {
        this.contextCache.delete(key);
      }
    }

    this.executions.delete(executionId);
  }

  getExecutionStatus(executionId) {
    const execution = this.executions.get(executionId);
    if (execution) {
      return {
        id: executionId,
        status: execution.status,
        paused: execution.paused,
        nodeStatuses: Object.fromEntries(execution.nodeStatuses)
      };
    }

    const dbExecution = db.prepare('SELECT * FROM executions WHERE id = ?').get(executionId);
    if (dbExecution) {
      const logs = db.prepare('SELECT * FROM execution_logs WHERE execution_id = ? ORDER BY id').all(executionId);
      const nodeStatuses = {};
      logs.forEach(log => {
        nodeStatuses[log.node_id] = log.status;
      });
      return {
        id: executionId,
        status: dbExecution.status,
        paused: false,
        nodeStatuses
      };
    }

    return null;
  }
}

const executor = new WorkflowExecutor();
module.exports = executor;
