class BaseNode {
  constructor(nodeConfig) {
    this.id = nodeConfig.id;
    this.type = nodeConfig.type;
    this.config = nodeConfig.data || {};
  }

  async execute(input, context) {
    throw new Error('execute() must be implemented by subclass');
  }

  getConfig() {
    return this.config;
  }
}

module.exports = BaseNode;
