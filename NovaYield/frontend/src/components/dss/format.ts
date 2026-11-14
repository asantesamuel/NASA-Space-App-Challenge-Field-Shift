/** Display helpers. They format values already returned by the API. */

/* One distinguishable hue per crop; each keeps 4.5:1 contrast with white text. */
const CROP_COLORS: Record<string, string> = {
  maize: '#966512',
  cowpea: '#3b6a96',
  groundnut: '#8c4f35',
  cassava: '#4a7a35',
  yam: '#6f5199',
  rice: '#1d7068',
  'rice-upland': '#1d7068',
  'rice-rain-fed-lowland': '#1d7068',
  'rice-irrigated': '#1d7068',
  plantain: '#76801a',
  sorghum: '#a04431',
};
const DEFAULT_CROP_COLOR = '#4b5a52';

export function label(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function cropColor(cropKey: string | null | undefined): string {
  if (!cropKey) return DEFAULT_CROP_COLOR;
  return CROP_COLORS[cropKey] ?? DEFAULT_CROP_COLOR;
}

export function formatDay(iso: string | null | undefined): string {
  if (!iso) return 'Unknown date';
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number);
  if (!year || !month || !day) return iso;
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export function dayNumber(iso: string): number {
  const [year, month, day] = iso.slice(0, 10).split('-').map(Number);
  return Date.UTC(year, month - 1, day);
}

export type CategoryTone = 'adverse' | 'favorable' | 'neutral' | 'unknown';

export function categoryTone(category: string | null | undefined): CategoryTone {
  if (!category) return 'unknown';
  if (category === 'Drier' || category === 'Hotter' || category === 'Longer than usual') return 'adverse';
  if (category === 'Wetter' || category === 'Cooler' || category === 'Shorter than usual') return 'favorable';
  if (category === 'Normal' || category === 'Not longer than usual') return 'neutral';
  return 'unknown';
}

export function priorityLabel(priority: string | null | undefined): string {
  if (!priority) return 'No extra priority';
  return label(priority);
}
