const BaseNode = require('./base');

class CronTriggerNode extends BaseNode {
  async execute(input, context) {
    const { cronExpression, timezone } = this.config;

    return {
      success: true,
      triggerTime: new Date().toISOString(),
      cronExpression,
      timezone,
      message: 'Cron trigger executed'
    };
  }
}

module.exports = CronTriggerNode;
