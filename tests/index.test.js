describe('Crypto Bot', () => {
  test('should pass basic test', () => {
    expect(true).toBe(true);
  });

  test('environment configuration', () => {
    const requiredEnvVars = ['EXCHANGE', 'API_KEY', 'API_SECRET', 'TRADING_PAIR'];
    requiredEnvVars.forEach(envVar => {
      expect(process.env[envVar]).toBeDefined();
    });
  });
});