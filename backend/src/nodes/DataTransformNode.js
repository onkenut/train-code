const BaseNode = require('./base');

class DataTransformNode extends BaseNode {
  async execute(input, context) {
    const { mappings, script } = this.config;

    let output = { ...input };

    if (script) {
      try {
        output = this.executeScript(script, input);
      } catch (error) {
        return {
          success: false,
          error: error.message,
          input
        };
      }
    } else if (mappings && Array.isArray(mappings)) {
      output = {};
      mappings.forEach(mapping => {
        if (mapping.source && mapping.target) {
          output[mapping.target] = this.getValue(mapping.source, input);
        }
      });
    }

    return {
      success: true,
      data: output,
      input
    };
  }

  executeScript(script, input) {
    const { VM } = require('vm2');
    const vm = new VM({
      timeout: 5000,
      sandbox: { input }
    });
    return vm.run(script);
  }

  getValue(path, data) {
    const keys = path.split('.');
    let result = data;
    for (const key of keys) {
      if (result && typeof result === 'object' && key in result) {
        result = result[key];
      } else {
        return undefined;
      }
    }
    return result;
  }
}

module.exports = DataTransformNode;
