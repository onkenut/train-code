const BaseNode = require('./base');

class SendEmailNode extends BaseNode {
  async execute(input, context) {
    const { to, subject, body, smtp } = this.config;

    return {
      success: true,
      simulated: true,
      message: 'Email sending simulated',
      to,
      subject,
      body: this.interpolate(body || '', input),
      timestamp: new Date().toISOString()
    };
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
}

module.exports = SendEmailNode;
