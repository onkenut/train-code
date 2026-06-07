const BaseNode = require('./base');

class ConditionNode extends BaseNode {
  async execute(input, context) {
    const { expression, left, operator, right } = this.config;
    
    let conditionMet = false;

    if (expression) {
      conditionMet = this.evaluateExpression(expression, input);
    } else {
      conditionMet = this.compare(left, operator, right, input);
    }

    return {
      success: true,
      conditionMet,
      branch: conditionMet ? 'true' : 'false',
      input
    };
  }

  evaluateExpression(expr, data) {
    try {
      const keys = Object.keys(data || {});
      const values = Object.values(data || {});
      const fn = new Function(...keys, `return ${expr};`);
      return fn(...values);
    } catch (error) {
      return false;
    }
  }

  compare(left, operator, right, data) {
    const leftVal = this.getValue(left, data);
    const rightVal = this.getValue(right, data);

    switch (operator) {
      case '==':
        return leftVal == rightVal;
      case '===':
        return leftVal === rightVal;
      case '!=':
        return leftVal != rightVal;
      case '!==':
        return leftVal !== rightVal;
      case '>':
        return leftVal > rightVal;
      case '>=':
        return leftVal >= rightVal;
      case '<':
        return leftVal < rightVal;
      case '<=':
        return leftVal <= rightVal;
      case 'contains':
        return String(leftVal).includes(String(rightVal));
      case 'startsWith':
        return String(leftVal).startsWith(String(rightVal));
      case 'endsWith':
        return String(leftVal).endsWith(String(rightVal));
      default:
        return false;
    }
  }

  getValue(val, data) {
    if (typeof val === 'string' && val.startsWith('${') && val.endsWith('}')) {
      const key = val.slice(2, -1);
      const keys = key.split('.');
      let result = data;
      for (const k of keys) {
        if (result && typeof result === 'object' && k in result) {
          result = result[k];
        } else {
          return undefined;
        }
      }
      return result;
    }
    return val;
  }
}

module.exports = ConditionNode;
