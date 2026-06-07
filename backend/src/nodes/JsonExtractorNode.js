const BaseNode = require('./base');

class JsonExtractorNode extends BaseNode {
  async execute(input, context) {
    const { path, jsonData } = this.config;

    let data = jsonData || input;
    if (typeof data === 'string') {
      try {
        data = JSON.parse(data);
      } catch (e) {
        return {
          success: false,
          error: 'Invalid JSON input',
          input
        };
      }
    }

    const result = this.extractByPath(data, path);

    return {
      success: true,
      data: result,
      path,
      input
    };
  }

  extractByPath(obj, path) {
    if (!path) return obj;
    const keys = path.split('.').filter(k => k);
    let result = obj;
    for (const key of keys) {
      if (result && typeof result === 'object' && key in result) {
        result = result[key];
      } else if (Array.isArray(result) && !isNaN(Number(key))) {
        result = result[Number(key)];
      } else {
        return undefined;
      }
    }
    return result;
  }
}

module.exports = JsonExtractorNode;
