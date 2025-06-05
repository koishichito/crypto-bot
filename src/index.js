import dotenv from 'dotenv';
import winston from 'winston';

dotenv.config();

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

logger.info('Crypto Bot starting...');
logger.info(`Mode: ${process.env.BOT_MODE || 'paper_trading'}`);
logger.info(`Exchange: ${process.env.EXCHANGE || 'not configured'}`);
logger.info(`Trading Pair: ${process.env.TRADING_PAIR || 'not configured'}`);

process.on('SIGINT', () => {
  logger.info('Bot shutting down...');
  process.exit(0);
});

logger.info('Bot initialized successfully');