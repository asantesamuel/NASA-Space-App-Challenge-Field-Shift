/** Display helpers. They format values already returned by the API. */

const CROP_COLORS: Record<string, string> = {
  maize: '#3c7650',
  cowpea: '#237347',
  groundnut: '#568364',
  cassava: '#326648',
  yam: '#668e71',
  rice: '#1c5a39',
  'rice-upland': '#497858',
  'rice-rain-fed-lowland': '#2e6c48',
  'rice-irrigated': '#154a31',
  plantain: '#5c8265',
  sorghum: '#416f50',
};

export function label(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function cropColor(cropKey: string | null | undefined): string {
  if (!cropKey) return '#1b6b43';
  return CROP_COLORS[cropKey] ?? '#1b6b43';
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
