const initSqlJs = require('sql.js');
const path = require('path');
const fs = require('fs');

const dataDir = path.join(__dirname, '..', 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.join(dataDir, 'flowforge.db');

let db = null;
let SQL = null;

async function initDatabase() {
  SQL = await initSqlJs();

  if (fs.existsSync(dbPath)) {
    const fileBuffer = fs.readFileSync(dbPath);
    db = new SQL.Database(fileBuffer);
  } else {
    db = new SQL.Database();
  }

  db.run(`
    CREATE TABLE IF NOT EXISTS workflows (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      dsl_json TEXT,
      status TEXT DEFAULT 'idle',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS executions (
      id TEXT PRIMARY KEY,
      workflow_id TEXT NOT NULL,
      trigger_type TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      started_at TIMESTAMP,
      finished_at TIMESTAMP,
      FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    );

    CREATE TABLE IF NOT EXISTS execution_logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      execution_id TEXT NOT NULL,
      node_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      input_data TEXT,
      output_data TEXT,
      error_msg TEXT,
      started_at TIMESTAMP,
      finished_at TIMESTAMP,
      FOREIGN KEY (execution_id) REFERENCES executions(id)
    );

    CREATE INDEX IF NOT EXISTS idx_executions_workflow_id ON executions(workflow_id);
    CREATE INDEX IF NOT EXISTS idx_execution_logs_execution_id ON execution_logs(execution_id);
  `);

  saveDatabase();
}

function saveDatabase() {
  if (db) {
    const data = db.export();
    const buffer = Buffer.from(data);
    fs.writeFileSync(dbPath, buffer);
  }
}

function prepare(sql) {
  return {
    run(...params) {
      const stmt = db.prepare(sql);
      stmt.bind(params);
      const result = stmt.step();
      const lastID = db.exec('SELECT last_insert_rowid() as id')[0]?.values[0]?.[0];
      const changes = db.getRowsModified?.() || 0;
      stmt.free();
      saveDatabase();
      return { lastInsertRowid: lastID, changes };
    },
    get(...params) {
      const stmt = db.prepare(sql);
      stmt.bind(params);
      const result = [];
      while (stmt.step()) {
        result.push(stmt.getAsObject());
      }
      stmt.free();
      return result[0];
    },
    all(...params) {
      const stmt = db.prepare(sql);
      stmt.bind(params);
      const result = [];
      while (stmt.step()) {
        result.push(stmt.getAsObject());
      }
      stmt.free();
      return result;
    }
  };
}

function exec(sql) {
  db.exec(sql);
  saveDatabase();
}

function pragma() {
}

const dbWrapper = {
  init: initDatabase,
  prepare,
  exec,
  pragma
};

module.exports = dbWrapper;
