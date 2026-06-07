const BaseNode = require('./base');
const HttpRequestNode = require('./HttpRequestNode');
const ConditionNode = require('./ConditionNode');
const DataTransformNode = require('./DataTransformNode');
const CronTriggerNode = require('./CronTriggerNode');
const SendEmailNode = require('./SendEmailNode');
const JsonExtractorNode = require('./JsonExtractorNode');

const nodeRegistry = new Map();

function registerNode(type, NodeClass, meta = {}) {
  nodeRegistry.set(type, { NodeClass, meta });
}

function getNodeClass(type) {
  const entry = nodeRegistry.get(type);
  return entry ? entry.NodeClass : null;
}

function getNodeMeta(type) {
  const entry = nodeRegistry.get(type);
  return entry ? entry.meta : null;
}

function getAllNodeTypes() {
  const types = [];
  for (const [type, entry] of nodeRegistry) {
    types.push({
      type,
      ...entry.meta
    });
  }
  return types;
}

function createNode(nodeConfig) {
  const NodeClass = getNodeClass(nodeConfig.type);
  if (!NodeClass) {
    throw new Error(`Unknown node type: ${nodeConfig.type}`);
  }
  return new NodeClass(nodeConfig);
}

registerNode('cronTrigger', CronTriggerNode, {
  label: '定时触发器',
  category: 'trigger',
  icon: 'clock',
  description: '按 Cron 表达式定时触发工作流',
  defaultConfig: {
    cronExpression: '0 * * * *',
    timezone: 'Asia/Shanghai'
  },
  inputs: 0,
  outputs: 1
});

registerNode('httpRequest', HttpRequestNode, {
  label: 'HTTP 请求',
  category: 'network',
  icon: 'globe',
  description: '发送 HTTP 请求获取数据',
  defaultConfig: {
    method: 'GET',
    url: 'https://api.example.com',
    headers: {},
    body: null,
    timeout: 30000
  },
  inputs: 1,
  outputs: 1
});

registerNode('condition', ConditionNode, {
  label: '条件分支',
  category: 'logic',
  icon: 'split',
  description: '根据条件判断走不同分支',
  defaultConfig: {
    left: '${status}',
    operator: '===',
    right: 200,
    expression: ''
  },
  inputs: 1,
  outputs: 2,
  outputLabels: ['满足条件', '不满足条件']
});

registerNode('dataTransform', DataTransformNode, {
  label: '数据处理',
  category: 'data',
  icon: 'transform',
  description: '转换和处理数据',
  defaultConfig: {
    mappings: [],
    script: ''
  },
  inputs: 1,
  outputs: 1
});

registerNode('jsonExtractor', JsonExtractorNode, {
  label: 'JSON 提取',
  category: 'data',
  icon: 'json',
  description: '从 JSON 数据中提取字段',
  defaultConfig: {
    path: ''
  },
  inputs: 1,
  outputs: 1
});

registerNode('sendEmail', SendEmailNode, {
  label: '发送邮件',
  category: 'notification',
  icon: 'mail',
  description: '发送邮件通知',
  defaultConfig: {
    to: '',
    subject: '',
    body: ''
  },
  inputs: 1,
  outputs: 1
});

module.exports = {
  registerNode,
  getNodeClass,
  getNodeMeta,
  getAllNodeTypes,
  createNode
};
