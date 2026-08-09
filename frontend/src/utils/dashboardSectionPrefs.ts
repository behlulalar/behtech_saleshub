const STORAGE_KEY = 'crm_dashboard_sections_v1';

type SectionId = 'aiPriorities' | 'awaitingReply';

type Stored = Partial<Record<SectionId, boolean>>;

function readAll(): Stored {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Stored;
  } catch {
    return {};
  }
}

export function readDashboardSectionOpen(section: SectionId, defaultOpen = true): boolean {
  const value = readAll()[section];
  return typeof value === 'boolean' ? value : defaultOpen;
}

export function writeDashboardSectionOpen(section: SectionId, open: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...readAll(), [section]: open }));
  } catch {
    /* quota / private mode */
  }
}
