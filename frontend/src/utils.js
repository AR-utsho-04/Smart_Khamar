import i18n from './i18n';

const loc = () => (i18n.language === 'bn' ? 'bn-BD' : 'en-GB');
export const fmtDate = (v) => (v ? new Date(v).toLocaleDateString(loc(), { day: '2-digit', month: 'short', year: 'numeric' }) : '-');
export const fmtDateTime = (v) => (v ? new Date(v).toLocaleString(loc(), { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '-');
export const pct = (p) => `${Math.round((p || 0) * 100)}%`;
export const pick = (obj, base) => (i18n.language === 'bn' ? obj[`${base}_bn`] : obj[`${base}_en`]) || obj[`${base}_en`];
export const todayInput = () => new Date().toISOString().slice(0, 10);
export const nowLocalInput = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};
