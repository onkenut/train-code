const BaseNode = require('./base');
const axios = require('axios');

class HttpRequestNode extends BaseNode {
  async execute(input, context) {
    const { method = 'GET', url, headers = {}, body, timeout = 30000 } = this.config;
    
    const finalUrl = this.interpolate(url || '', input);
    const finalHeaders = this.interpolateObject(headers, input);
    const finalBody = body ? this.interpolateObject(body, input) : undefined;

    const startTime = Date.now();
    try {
      const response = await axios({
        method: method.toLowerCase(),
        url: finalUrl,
        headers: finalHeaders,
        data: finalBody,
        timeout: timeout
      });

      return {
        success: true,
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
        data: response.data,
        duration: Date.now() - startTime
      };
    } catch (error) {
      return {
        success: false,
        status: error.response?.status || null,
        statusText: error.response?.statusText || error.message,
        data: error.response?.data || null,
        error: error.message,
        duration: Date.now() - startTime
      };
    }
  }

  interpolate(template, data) {
    return template.replace(/\$\{([^}]+)\}/g, (_, key) => {
      const keys = key.split('.');
      let value = data;
      for (const k of keys) {
        if (value && typeof value === 'object' && k in value) {
          value = value[k];
        } else {
          return '';
        }
      }
      return value != null ? String(value) : '';
    });
  }

  interpolateObject(obj, data) {
    if (typeof obj !== 'object' || obj === null) return obj;
    if (Array.isArray(obj)) {
      return obj.map(item => this.interpolateObject(item, data));
    }
    const result = {};
    for (const [key, value] of Object.entries(obj)) {
      if (typeof value === 'string') {
        result[key] = this.interpolate(value, data);
      } else if (typeof value === 'object') {
        result[key] = this.interpolateObject(value, data);
      } else {
        result[key] = value;
      }
    }
    return result;
  }
}

module.exports = HttpRequestNode;
