import { browser } from '$app/environment';
import { DEFAULT_LANGUAGE, isLanguage, messages, type Language, type MessageKey } from './messages';

const STORAGE_KEY = 'kasir.language';

class LanguageState {
  current = $state<Language>(DEFAULT_LANGUAGE);

  init() {
    if (!browser) return;

    const stored = localStorage.getItem(STORAGE_KEY);
    this.current = stored && isLanguage(stored) ? stored : DEFAULT_LANGUAGE;
    this.syncDocumentLanguage();
  }

  setLanguage(nextLanguage: Language) {
    this.current = nextLanguage;

    if (!browser) return;
    localStorage.setItem(STORAGE_KEY, nextLanguage);
    this.syncDocumentLanguage();
  }

  t(key: MessageKey) {
    return messages[this.current][key];
  }

  private syncDocumentLanguage() {
    document.documentElement.lang = this.current;
  }
}

export const language = new LanguageState();
