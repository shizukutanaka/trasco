import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import enTranslation from './i18n/en.json';
import jaTranslation from './i18n/ja.json';

const resources = {
  en: {
    translation: enTranslation
  },
  ja: {
    translation: jaTranslation
  }
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: navigator.language.split('-')[0] === 'ja' ? 'ja' : 'en',
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
