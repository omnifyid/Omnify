import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { api, configureApiAuth } from '$lib/api/client';
import type { AuthResponse, User } from '$lib/api/types';

const ACCESS_KEY = 'kasir.accessToken';
const REFRESH_KEY = 'kasir.refreshToken';

class AuthState {
  accessToken = $state<string | null>(null);
  refreshToken = $state<string | null>(null);
  user = $state<User | null>(null);
  ready = $state(false);

  get isAuthenticated() {
    return Boolean(this.accessToken);
  }

  init() {
    if (!browser || this.ready) return;
    this.accessToken = localStorage.getItem(ACCESS_KEY);
    this.refreshToken = localStorage.getItem(REFRESH_KEY);
    configureApiAuth({
      getAccessToken: () => this.accessToken,
      refreshAccessToken: () => this.refresh()
    });
    this.ready = true;
  }

  private saveTokens(tokens: AuthResponse) {
    this.accessToken = tokens.access_token;
    this.refreshToken = tokens.refresh_token;
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
  }

  async login(identifier: string, password: string) {
    const tokens = await api.post<AuthResponse>('/auth/login', { identifier, password });
    this.saveTokens(tokens);
    await this.loadMe();
  }

  async refresh() {
    if (!this.refreshToken) return false;
    try {
      const tokens = await api.post<AuthResponse>('/auth/refresh', { refresh_token: this.refreshToken });
      this.saveTokens(tokens);
      return true;
    } catch {
      this.clear();
      return false;
    }
  }

  async loadMe() {
    if (!this.accessToken) return;
    this.user = await api.get<User>('/users/me');
  }

  async logout() {
    try {
      if (this.refreshToken) await api.post('/auth/logout', { refresh_token: this.refreshToken });
    } finally {
      this.clear();
      await goto('/login');
    }
  }

  clear() {
    this.accessToken = null;
    this.refreshToken = null;
    this.user = null;
    if (browser) {
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    }
  }
}

export const auth = new AuthState();
