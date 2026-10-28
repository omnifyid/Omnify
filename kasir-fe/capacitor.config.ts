import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.kasir.pos',
  appName: 'Kasir',
  webDir: 'build',
  server: { androidScheme: 'https' }
};

export default config;
