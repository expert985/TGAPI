/**
 * PM2 进程管理配置文件
 *
 * 使用方法：
 *   pm2 start ecosystem.config.js         # 启动所有服务
 *   pm2 start ecosystem.config.js --only bot    # 只启动bot
 *   pm2 start ecosystem.config.js --only api    # 只启动API
 *   pm2 restart ecosystem.config.js       # 重启所有服务
 *   pm2 stop ecosystem.config.js          # 停止所有服务
 *   pm2 delete ecosystem.config.js        # 删除所有服务
 *   pm2 logs                              # 查看日志
 *   pm2 monit                             # 实时监控
 */

module.exports = {
  apps: [
    // Telegram Bot服务
    {
      name: 'tgapi-bot',
      script: 'venv/bin/python',
      args: '-m bot.main',
      cwd: './',
      interpreter: 'none',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
      },
      error_file: './logs/pm2-bot-error.log',
      out_file: './logs/pm2-bot-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
    },

    // API服务器
    {
      name: 'tgapi-api',
      script: 'venv/bin/python',
      args: '-m api.server',
      cwd: './',
      interpreter: 'none',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1',
      },
      error_file: './logs/pm2-api-error.log',
      out_file: './logs/pm2-api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      merge_logs: true,
      min_uptime: '10s',
      max_restarts: 10,
      restart_delay: 4000,
    },
  ],

  /**
   * 部署配置（可选）
   */
  deploy: {
    production: {
      user: 'tgapi',
      host: 'your-server.com',
      ref: 'origin/main',
      repo: 'git@github.com:yourusername/TGAPI.git',
      path: '/opt/TGAPI',
      'pre-deploy-local': '',
      'post-deploy': 'source venv/bin/activate && pip install -r requirements.txt && pm2 reload ecosystem.config.js --env production',
      'pre-setup': ''
    }
  }
};
