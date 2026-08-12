export type UserRole = 'owner' | 'employee';
export type AccountType = 'individual' | 'company';

export interface UpdateProfileData {
  email?: string;
  company_name?: string;
  display_name?: string;
  current_password?: string;
  new_password?: string;
  new_password_confirm?: string;
}

export interface DeleteAccountData {
  password: string;
  confirm_username: string;
}

export interface UserProfile {
  username: string;
  email: string;
  role: UserRole;
  account_type: AccountType;
  owner_id?: number | null;
  company_name?: string | null;
  display_name?: string;
  email_verified?: boolean;
  company_email_domains?: string[];
}

export interface Employee {
  id: number;
  username: string;
  email: string;
  display_name: string;
  email_verified: boolean;
  created_at: string;
}

export interface EmployeeFormData {
  username: string;
  email: string;
  display_name: string;
  password: string;
  password_confirm: string;
}

export interface LeadRequest {
  id: number;
  category: string;
  category_label: string;
  status: 'pending' | 'approved' | 'rejected';
  requested_by: number;
  requested_by_username: string;
  isletme_adi: string;
  yetkili: string;
  sehir: string;
  instagram: string;
  whatsapp: string;
  eposta: string;
  ilk_iletisim_kanali: string;
  ilk_mesaj_tarihi: string;
  ilk_mesaj_saati: string;
  durum: string;
  oncelik: string;
  takip_1: string;
  takip_2: string;
  demo_gonderildi: boolean;
  demo_tarihi: string;
  gorusme_tarihi: string;
  gorusme_saati: string;
  teklif: string;
  sonuc: string;
  notlar: string;
  tag_ids: string[];
  rejection_note: string;
  reviewed_by_username: string;
  reviewed_at?: string | null;
  approved_lead_id?: number | null;
  created_at: string;
  updated_at: string;
}

export type LeadRequestFormData = Omit<
  LeadFormData,
  'satis_tutari' | 'satis_tarihi'
> & {
  category: string;
};

export interface Category {
  id: string;
  label: string;
  icon: string;
  lead_count?: number;
  created_at?: string;
}

export interface CategoryFormData {
  label: string;
  icon: string;
  id?: string;
}

export interface Tag {
  id: string;
  label: string;
  color: string;
  is_system?: boolean;
  lead_count?: number;
  created_at?: string;
}

export interface TagFormData {
  label: string;
  color: string;
  id?: string;
}

export const TAG_COLOR_OPTIONS = [
  { id: 'amber', label: 'Altın' },
  { id: 'orange', label: 'Turuncu' },
  { id: 'blue', label: 'Mavi' },
  { id: 'purple', label: 'Mor' },
  { id: 'slate', label: 'Gri' },
  { id: 'red', label: 'Kırmızı' },
  { id: 'green', label: 'Yeşil' },
  { id: 'cyan', label: 'Camgöbeği' },
  { id: 'emerald', label: 'Zümrüt' },
  { id: 'indigo', label: 'İndigo' },
] as const;

export const TAG_COLOR_CLASSES: Record<string, string> = {
  amber: 'bg-amber-100 text-amber-800',
  orange: 'bg-orange-100 text-orange-800',
  blue: 'bg-blue-100 text-blue-800',
  purple: 'bg-purple-100 text-purple-800',
  slate: 'bg-slate-100 text-slate-700',
  red: 'bg-red-100 text-red-800',
  green: 'bg-green-100 text-green-800',
  cyan: 'bg-cyan-100 text-cyan-800',
  emerald: 'bg-emerald-100 text-emerald-800',
  indigo: 'bg-indigo-100 text-indigo-800',
};

export interface Lead {
  id: number;
  category: string;
  isletme_adi: string;
  yetkili: string;
  sehir: string;
  instagram: string;
  whatsapp: string;
  eposta: string;
  ilk_iletisim_kanali: string;
  ilk_mesaj_tarihi: string;
  ilk_mesaj_saati: string;
  durum: string;
  oncelik: string;
  takip_1: string;
  takip_2: string;
  demo_gonderildi: boolean;
  demo_tarihi: string;
  gorusme_tarihi: string;
  gorusme_saati: string;
  teklif: string;
  sonuc: string;
  satis_tutari: number;
  satis_tarihi: string;
  notlar: string;
  tags?: Tag[];
  created_at: string;
  updated_at: string;
}

export interface PaginatedLeads {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LeadImportErrorItem {
  row: number;
  isletme_adi: string;
  error: string;
}

export interface LeadImportResult {
  created: number;
  failed: number;
  skipped: number;
  batch_id?: number | null;
  errors: LeadImportErrorItem[];
}

export interface LeadImportBatch {
  id: number;
  category: string;
  filename: string;
  created_count: number;
  failed_count: number;
  skipped_count: number;
  lead_count: number;
  created_at: string;
}

export interface PlacesUsage {
  month: string;
  sku_type: string;
  used: number;
  free_quota: number;
  remaining: number;
  warning: boolean;
  over_quota: boolean;
}

export interface LeadDiscoveryResult {
  google_place_id: string;
  business_name: string;
  phone_number: string;
  phone_normalized: string;
  address: string;
  rating: number | null;
  rating_count: number | null;
  latitude: number | null;
  longitude: number | null;
  already_in_crm: boolean;
  existing_lead_id: number | null;
  low_digital_presence: boolean;
}

export interface LeadDiscoveryResponse {
  results: LeadDiscoveryResult[];
  queries_used: number;
  total_found: number;
  mapped_category: string;
  text_query: string;
  usage: PlacesUsage;
  warning_message?: string | null;
}

export interface LeadDiscoveryImportResult {
  created: number;
  updated: number;
  skipped: number;
  lead_ids: number[];
}

export type LeadFormData = Omit<Lead, 'id' | 'category' | 'created_at' | 'updated_at' | 'tags'> & {
  tag_ids: string[];
};

export interface Stats {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  demo_gonderildi: number;
  cities: string[];
}

export interface RevenueCategoryItem {
  category: string;
  category_label: string;
  gelir: number;
  satis_sayisi: number;
}

export interface RevenueMonthItem {
  ay: string;
  ay_label: string;
  gelir: number;
}

export interface RevenueSaleItem {
  id: number;
  isletme_adi: string;
  category: string;
  category_label: string;
  sehir: string;
  satis_tutari: number;
  satis_tarihi: string;
  teklif: string;
}

export interface RevenueData {
  toplam_gelir: number;
  bu_ay_gelir: number;
  bu_yil_gelir: number;
  ortalama_satis: number;
  satis_sayisi: number;
  musteri_sayisi: number;
  kategori_dagilimi: RevenueCategoryItem[];
  aylik_gelir: RevenueMonthItem[];
  son_satislar: RevenueSaleItem[];
}

export type ReportPeriod = 'weekly' | 'monthly';

export interface ReportStatusItem {
  durum: string;
  count: number;
}

export interface ReportCategoryItem {
  category: string;
  category_label: string;
  yeni_kayit: number;
  musteri: number;
}

export interface ReportSaleItem {
  isletme_adi: string;
  category_label: string;
  sehir: string;
  satis_tutari: number;
  satis_tarihi: string;
}

export interface ReportData {
  period_type: ReportPeriod;
  period_label: string;
  period_start: string;
  period_end: string;
  yeni_kayit: number;
  yeni_musteri: number;
  donusum_orani: number | null;
  satis_sayisi: number | null;
  toplam_gelir: number | null;
  ortalama_satis: number | null;
  satis_hunisi: FunnelStage[];
  satis_donusum_orani: number;
  durum_dagilimi: ReportStatusItem[];
  kategori_ozet: ReportCategoryItem[];
  donem_satislar: ReportSaleItem[];
  onceki_donem: {
    yeni_kayit: number;
    yeni_musteri: number;
  };
}

export interface AiStatusResponse {
  enabled: boolean;
  configured: boolean;
  month: string;
  tokens_used: number;
  tokens_quota: number;
  tokens_remaining: number;
  request_count: number;
  suggest_message_available: boolean;
  summarize_lead_available?: boolean;
  priorities_available?: boolean;
  batch_runs_available?: boolean;
  agent_runs_available?: boolean;
  daily_email_enabled?: boolean;
  chat_available?: boolean;
  diagnosis_interpret_available?: boolean;
  diagnosis_history_interpret_available?: boolean;
}

export interface IntelligenceInsightItem {
  id: number;
  insight_type: string;
  severity: string;
  entity_type: string;
  entity_id?: number | null;
  title: string;
  summary: string;
  evidence?: Record<string, unknown>;
  source: string;
  created_at: string;
}

export interface DiagnosisImpact {
  affected_lead_count: number;
  high_priority_count: number;
  medium_priority_count: number;
  low_priority_count: number;
  estimated_pipeline_value?: number | null;
}

export interface DiagnosisPriorityLead {
  lead_id: number;
  lead_name: string;
  durum: string;
  existing_lead_score: number;
  diagnosis_modifier: number;
  diagnosis_priority_score: number;
  priority: string;
  reason_codes?: string[];
  idle_days?: number | null;
  offer_age_days?: number | null;
}

export interface DiagnosisItem {
  diagnosis_id: string;
  type: string;
  severity: string;
  title: string;
  description: string;
  metric: string;
  current_value?: number | null;
  previous_value?: number | null;
  change_percent?: number | null;
  evidence?: Record<string, unknown>;
  affected_lead_count: number;
  detected_at: string;
  affected_leads_available?: boolean;
  impact?: DiagnosisImpact;
  top_priority_leads?: DiagnosisPriorityLead[];
}

export interface DiagnosisListResponse {
  generated_at: string;
  duration_ms: number;
  period_type: string;
  anchor: string;
  items: DiagnosisItem[];
}

/** DE-5 diagnosis lifecycle state (DiagnosisCase / Snapshot). */
export type DiagnosisLifecycleState =
  | 'new'
  | 'active'
  | 'improving'
  | 'worsening'
  | 'resolved';

export type DiagnosisHistoryPeriodKey = 'daily' | 'weekly' | 'monthly' | 'current';

export interface DiagnosisSyncResponse {
  period: string;
  created_cases: number;
  updated_cases: number;
  new_snapshots: number;
  resolved_cases: number;
  reopened_cases: number;
  unchanged_cases: number;
  period_keys_in_scope: string[];
  organization_id: number;
}

export interface DiagnosisHistorySnapshot {
  id: number;
  observed_at: string;
  state: string;
  severity: string;
  metric: string;
  current_value?: number | null;
  engine_previous_value?: number | null;
  change_percent?: number | null;
  affected_lead_count: number;
  impact: Record<string, unknown>;
  top_leads: Record<string, unknown>[];
  evidence: Record<string, unknown>;
  fingerprint: string;
  trigger: string;
  created_at: string;
}

/** DE-5.1 trend direction (not DiagnosisCase.state). */
export type DiagnosisTrendDirection =
  | 'newly_detected'
  | 'worsening'
  | 'improving'
  | 'stable'
  | 'resolved'
  | 'reopened';

export interface DiagnosisTrendSnapshotRef {
  observed_at: string;
  state: string;
  severity: string;
  metric: string;
  current_value?: number | null;
  change_percent?: number | null;
  affected_lead_count: number;
  trigger: string;
}

export interface DiagnosisTrendChanges {
  severity_from?: string | null;
  severity_to?: string | null;
  severity_delta: number;
  current_value_from?: number | null;
  current_value_to?: number | null;
  current_value_delta?: number | null;
  metric_direction: number;
  affected_lead_count_from: number;
  affected_lead_count_to: number;
  affected_lead_count_delta: number;
  high_priority_count_from: number;
  high_priority_count_to: number;
  high_priority_count_delta: number;
  medium_priority_count_from: number;
  medium_priority_count_to: number;
  medium_priority_count_delta: number;
  low_priority_count_from: number;
  low_priority_count_to: number;
  low_priority_count_delta: number;
  lead_set_added_count: number;
  lead_set_removed_count: number;
  lead_set_size_from: number;
  lead_set_size_to: number;
}

export interface DiagnosisTrendWorstPoint {
  observed_at: string;
  severity: string;
  metric: string;
  current_value?: number | null;
  affected_lead_count: number;
}

export interface DiagnosisTrendWindowMetrics {
  n: number;
  observation_count: number;
  dominant_direction: string;
  min_current_value?: number | null;
  max_current_value?: number | null;
  min_affected_lead_count?: number | null;
  max_affected_lead_count?: number | null;
  worst_severity?: string | null;
}

export interface DiagnosisTrendMetrics {
  active_duration_seconds?: number | null;
  last_substantive_change_at?: string | null;
  reopen_count: number;
  substantive_count: number;
  total_snapshot_count: number;
  worst_point?: DiagnosisTrendWorstPoint | null;
  window: DiagnosisTrendWindowMetrics;
}

export interface DiagnosisTrendSummary {
  direction: DiagnosisTrendDirection | string;
  reason_codes: string[];
  changes: DiagnosisTrendChanges;
  previous_snapshot?: DiagnosisTrendSnapshotRef | null;
  current_snapshot?: DiagnosisTrendSnapshotRef | null;
  substantive_count: number;
  metrics: DiagnosisTrendMetrics;
}

export interface DiagnosisHistoryResponse {
  diagnosis_id: string;
  diagnosis_type: string;
  period_key: string;
  state: string;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  last_synced_at?: string | null;
  resolved_at?: string | null;
  latest_snapshot_id?: number | null;
  page: number;
  limit: number;
  total: number;
  snapshots: DiagnosisHistorySnapshot[];
  /** Deterministic trend from full case history (not Case.state). */
  trend?: DiagnosisTrendSummary | null;
}

export interface DiagnosisRecommendedAction {
  title: string;
  reason: string;
  priority: 'high' | 'medium' | 'low';
}

export interface DiagnosisInterpretation {
  summary: string;
  why_it_matters: string;
  key_findings: string[];
  recommended_actions: DiagnosisRecommendedAction[];
  confidence: 'high' | 'medium' | 'low';
}

export interface DiagnosisInterpretRequest {
  diagnosis_id: string;
  period: string;
  date?: string | null;
  locale?: string;
  refresh?: boolean;
}

export interface ProposalBridgeItemResult {
  recommendation_index: number;
  outcome: string;
  action_type?: string | null;
  action_id?: string | null;
  created?: boolean;
  skip_reason?: string | null;
}

export interface ProposalBridgeSummary {
  recommendation_count?: number;
  mapped_count?: number;
  no_action_count?: number;
  proposed_count?: number;
  skipped_count?: number;
  created_count?: number;
  action_ids?: string[];
  items?: ProposalBridgeItemResult[];
  bridge_error?: boolean;
}

export interface DiagnosisInterpretResponse {
  diagnosis_id: string;
  interpretation: DiagnosisInterpretation | null;
  run_id: number | null;
  cached: boolean;
  context_fingerprint: string | null;
  disclaimer: string;
  error_code: string | null;
  proposal_bridge?: ProposalBridgeSummary | null;
}

export interface DiagnosisHistoryInterpretation {
  summary: string;
  what_changed: string;
  why_it_matters: string;
  key_points: string[];
  confidence: 'high' | 'medium' | 'low';
}

export interface DiagnosisHistoryInterpretRequest {
  diagnosis_id: string;
  period_key?: string | null;
  locale?: string;
  refresh?: boolean;
}

export interface DiagnosisHistoryInterpretResponse {
  diagnosis_id: string;
  period_key: string;
  interpretation: DiagnosisHistoryInterpretation | null;
  trend_direction: string;
  trend?: {
    direction?: string;
    reason_codes?: string[];
    substantive_count?: number | null;
    metrics?: Record<string, unknown>;
  } | null;
  run_id: number | null;
  cached: boolean;
  generated_at?: string | null;
  context_fingerprint?: string | null;
  disclaimer: string;
  error_code: string | null;
}

export interface SummarizeLeadRequest {
  lead_id: number;
  locale?: string;
}

export interface SummarizeLeadResponse {
  summary: string;
  insights: IntelligenceInsightItem[];
  run_id: number;
  disclaimer: string;
}

export interface PriorityRecommendation {
  lead_id: number;
  isletme_adi: string;
  category_label?: string | null;
  durum?: string | null;
  score: number;
  priority: string;
  action_type: string;
  reasons: string[];
  insight_ids?: number[];
}

export interface PrioritiesResponse {
  recommendations: PriorityRecommendation[];
  run_id: number;
  cached?: boolean;
}

export interface AiRunCreateRequest {
  run_type: 'batch_score' | 'agent';
  question?: string;
  locale?: string;
}

export interface AiRunCreateResponse {
  run_id: number;
  status: string;
  run_type: string;
}

export interface AiRunDetail {
  id: number;
  run_type: string;
  status: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown> | null;
  steps: Record<string, unknown>[];
  error_code?: string | null;
  created_at: string;
  updated_at: string;
  duration_ms?: number | null;
}

export interface AiRunListResponse {
  items: AiRunDetail[];
}

export interface ActionProposalItem {
  id: number;
  lead_id?: number | null;
  lead_name?: string | null;
  proposed_action: string;
  payload: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface AiActionItem {
  action_id: string;
  action_type: string;
  target_entity: string;
  target_entity_id?: number | null;
  parameters: Record<string, unknown>;
  reason: string;
  source_diagnosis_id?: string | null;
  source_interpret_run_id?: number | null;
  status: string;
  requires_confirmation: boolean;
  lead_name?: string | null;
  idempotency_key?: string | null;
  created_at: string;
  updated_at?: string;
  approved_at?: string | null;
  executed_at?: string | null;
  execution_result?: Record<string, unknown>;
  execute_enabled_v1?: boolean;
}

export interface AiActionExecuteResponse {
  action: AiActionItem;
  activity_id?: number | null;
  already_executed?: boolean;
}

export interface AiActionListResponse {
  items: AiActionItem[];
}

export interface CompanyProfile {
  version?: string;
  computed_at: string;
  period_label?: string | null;
  yeni_kayit?: number | null;
  yeni_musteri?: number | null;
  satis_donusum_orani?: number | null;
  pipeline_conversion?: number | null;
  cevap_bekleyen_sayisi?: number;
  bugunku_gorevler?: number;
  best_lead_source?: {
    source?: string;
    label?: string;
    win_rate_pct?: number;
    sample_size?: number;
  } | null;
  lost_or_stalled_leads?: number;
  top_insights?: { title?: string; severity?: string }[];
  total_leads?: number;
}

export interface AiChatRequest {
  message: string;
  history?: { role: 'user' | 'assistant'; content: string }[];
  locale?: string;
  conversation_id?: number;
}

export interface AiChatResponse {
  reply: string;
  run_id: number;
  disclaimer: string;
  conversation_id?: number | null;
}

export interface AssistantConversation {
  id: number;
  user_id: number;
  organization_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;
}

export interface AssistantMessage {
  id: number;
  conversation_id: number;
  role: 'user' | 'assistant' | string;
  content: string;
  created_at: string;
  run_id?: number | null;
}

export interface AssistantConversationListResponse {
  items: AssistantConversation[];
}

export interface AssistantConversationDetailResponse {
  conversation: AssistantConversation;
  messages: AssistantMessage[];
}

export interface SuggestMessageRequest {
  lead_id: number;
  template_id: 'intro' | 'followUp' | 'demo' | 'meeting';
  locale?: string;
}

export interface SuggestMessageResponse {
  text: string;
  run_id: number;
  disclaimer: string;
}

export const ONCELIK_OPTIONS = [
  {
    value: 'yuksek',
    label: 'Yüksek',
    description: 'Acil takip gerektirir',
    bgClass: 'bg-red-100',
    textClass: 'text-red-800',
    barClass: 'bg-red-500',
    ringClass: 'ring-red-300',
    icon: '↑',
  },
  {
    value: 'orta',
    label: 'Orta',
    description: 'Standart takip',
    bgClass: 'bg-amber-100',
    textClass: 'text-amber-800',
    barClass: 'bg-amber-500',
    ringClass: 'ring-amber-300',
    icon: '→',
  },
  {
    value: 'dusuk',
    label: 'Düşük',
    description: 'Düşük aciliyet',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-700',
    barClass: 'bg-slate-400',
    ringClass: 'ring-slate-300',
    icon: '↓',
  },
] as const;

export type OncelikValue = (typeof ONCELIK_OPTIONS)[number]['value'];

export function getOncelikOption(oncelik: string) {
  return ONCELIK_OPTIONS.find((o) => o.value === oncelik);
}

export function getOncelikBadgeClass(oncelik: string) {
  const option = getOncelikOption(oncelik);
  return option ? `${option.bgClass} ${option.textClass}` : 'bg-amber-100 text-amber-800';
}

export interface DashboardItem {
  id: number;
  isletme_adi: string;
  category: string;
  category_label: string;
  date: string;
  durum: string;
  detail?: string;
}

export interface DashboardTaskItem extends DashboardItem {
  type: string;
  type_label: string;
  days_until?: number;
}

export interface ReminderItem extends DashboardItem {
  last_contact_date: string;
  days_waiting: number;
}

export interface AutomationNotification {
  kind: string;
  id: number;
  isletme_adi: string;
  category_label: string;
  date: string;
  durum: string;
  message: string;
  days_until?: number | null;
  type?: string | null;
}

export interface DailyCategoryContactStat {
  category: string;
  category_label: string;
  iletisim_sayisi: number;
}

export interface DailyContactAnalytics {
  date: string;
  date_label: string;
  toplam_iletisim: number;
  kategori_bazli: DailyCategoryContactStat[];
}

export interface DailySummarySnippet {
  date: string;
  yeni_kayit: number;
  yeni_musteri: number;
  satis_sayisi?: number | null;
  toplam_gelir?: number | null;
  donusum_orani?: number | null;
  toplam_iletisim?: number;
  kategori_iletisim?: DailyCategoryContactStat[];
}

export interface FunnelStage {
  key: string;
  label: string;
  count: number;
  conversion_rate: number | null;
  overall_rate: number;
}

export interface FunnelData {
  satis_hunisi: FunnelStage[];
  satis_donusum_orani: number;
}

export interface ConversionStage {
  key: string;
  label: string;
  count: number;
  asama_basari_orani: number | null;
  onceki_asama_orani: number | null;
  toplam_orani: number;
}

export interface CityStat {
  sehir: string;
  toplam: number;
  cevap: number;
  satis: number;
  cevap_orani: number;
  satis_orani: number;
}

export interface CategoryStat {
  category: string;
  category_label: string;
  toplam: number;
  cevap: number;
  satis: number;
  cevap_orani: number;
  satis_orani: number;
}

export interface HourStat {
  saat: number;
  saat_label: string;
  mesaj_sayisi: number;
  cevap_sayisi: number;
  cevap_orani: number;
}

export interface DayStat {
  gun: number;
  gun_label: string;
  mesaj_sayisi: number;
  cevap_sayisi: number;
  cevap_orani: number;
}

export interface AnalyticsData extends FunnelData {
  donusum_oranlari: ConversionStage[];
  sehir_analizi: CityStat[];
  kategori_analizi: CategoryStat[];
  saat_analizi: HourStat[];
  gun_analizi: DayStat[];
}

export type AnalyticsView =
  | 'satis-hunisi'
  | 'analiz-donusum'
  | 'analiz-sehir'
  | 'analiz-kategori'
  | 'analiz-saat'
  | 'analiz-gun'
  | 'analiz-gunluk-iletisim';

export const ANALYTICS_VIEWS: AnalyticsView[] = [
  'satis-hunisi',
  'analiz-donusum',
  'analiz-sehir',
  'analiz-kategori',
  'analiz-saat',
  'analiz-gun',
  'analiz-gunluk-iletisim',
];

export type IntelligenceView =
  | 'intel-overview'
  | 'intel-diagnoses'
  | 'intel-actions'
  | 'intel-assistant';

export const INTELLIGENCE_VIEWS: IntelligenceView[] = [
  'intel-overview',
  'intel-diagnoses',
  'intel-actions',
  'intel-assistant',
];

export interface DashboardData {
  toplam_kayit: number;
  aktif_takip: number;
  bugunku_gorevler: number;
  bu_hafta_eklenen: number;
  cevap_bekleyen_sayisi: number;
  cevap_bekleyen_gun: number;
  bugunku_gorevler_liste: DashboardTaskItem[];
  son_gorusmeler: DashboardItem[];
  yaklasan_takipler: DashboardTaskItem[];
  son_musteriler: DashboardItem[];
  cevap_bekleyen_liste: ReminderItem[];
  otomasyon_bildirimleri: AutomationNotification[];
  gunluk_ozet?: DailySummarySnippet | null;
}

export interface Activity {
  id: number;
  lead_id: number;
  activity_type: string;
  title: string;
  description: string;
  activity_date: string;
  created_at: string;
}

export interface LeadAttachment {
  id: number;
  lead_id: number;
  label: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  version_number: number;
  replaces_attachment_id?: number | null;
  is_archived: boolean;
  archived_at?: string | null;
  archived_by_username?: string | null;
  uploaded_by_username?: string | null;
  created_at: string;
}

export interface ActivityType {
  id: string;
  label: string;
}

export interface ActivityFormData {
  activity_type: string;
  description: string;
  activity_date: string;
}

export const ACTIVITY_TYPE_OPTIONS: ActivityType[] = [
  { id: 'mesaj_gonderildi', label: 'Mesaj gönderildi' },
  { id: 'demo_gonderildi', label: 'Demo gönderildi' },
  { id: 'teklif_verildi', label: 'Teklif verildi' },
  { id: 'telefon_gorusmesi', label: 'Telefon görüşmesi yapıldı' },
  { id: 'gorusme_planlandi', label: 'Görüşme planlandı' },
  { id: 'gorusme_yapildi', label: 'Görüşme yapıldı' },
  { id: 'takip_yapildi', label: 'Takip yapıldı' },
  { id: 'durum_degisti', label: 'Durum değişti' },
  { id: 'satis_kaydedildi', label: 'Satış kaydedildi' },
  { id: 'kayit_olusturuldu', label: 'Kayıt oluşturuldu' },
  { id: 'diger', label: 'Diğer' },
];

export const DURUM_STATUSES = [
  {
    value: 'Yeni',
    label: 'Yeni',
    description: 'Henüz iletişime geçilmedi',
    bgClass: 'bg-slate-100',
    textClass: 'text-slate-700',
    barClass: 'bg-slate-500',
    ringClass: 'ring-slate-300',
    order: 1,
    group: 'active' as const,
  },
  {
    value: 'İletişime Geçildi',
    label: 'İletişime Geçildi',
    description: 'İlk mesaj veya arama yapıldı',
    bgClass: 'bg-sky-100',
    textClass: 'text-sky-800',
    barClass: 'bg-sky-500',
    ringClass: 'ring-sky-300',
    order: 2,
    group: 'active' as const,
  },
  {
    value: 'Takip Bekliyor',
    label: 'Takip Bekliyor',
    description: 'Cevap veya aksiyon bekleniyor',
    bgClass: 'bg-amber-100',
    textClass: 'text-amber-800',
    barClass: 'bg-amber-500',
    ringClass: 'ring-amber-300',
    order: 3,
    group: 'active' as const,
  },
  {
    value: 'Demo Gönderildi',
    label: 'Demo Gönderildi',
    description: 'Demo paylaşıldı',
    bgClass: 'bg-indigo-100',
    textClass: 'text-indigo-800',
    barClass: 'bg-indigo-500',
    ringClass: 'ring-indigo-300',
    order: 4,
    group: 'active' as const,
  },
  {
    value: 'Görüşme Planlandı',
    label: 'Görüşme Planlandı',
    description: 'Görüşme tarihi belirlendi',
    bgClass: 'bg-violet-100',
    textClass: 'text-violet-800',
    barClass: 'bg-violet-500',
    ringClass: 'ring-violet-300',
    order: 5,
    group: 'active' as const,
  },
  {
    value: 'Teklif Verildi',
    label: 'Teklif Verildi',
    description: 'Fiyat teklifi sunuldu',
    bgClass: 'bg-cyan-100',
    textClass: 'text-cyan-800',
    barClass: 'bg-cyan-500',
    ringClass: 'ring-cyan-300',
    order: 6,
    group: 'active' as const,
  },
  {
    value: 'Müşteri',
    label: 'Müşteri',
    description: 'Satış tamamlandı',
    bgClass: 'bg-emerald-100',
    textClass: 'text-emerald-800',
    barClass: 'bg-emerald-500',
    ringClass: 'ring-emerald-300',
    order: 7,
    group: 'won' as const,
  },
  {
    value: 'Olumsuz',
    label: 'Olumsuz',
    description: 'Satış gerçekleşmedi',
    bgClass: 'bg-red-100',
    textClass: 'text-red-800',
    barClass: 'bg-red-500',
    ringClass: 'ring-red-300',
    order: 8,
    group: 'lost' as const,
  },
  {
    value: 'Cevap Yok',
    label: 'Cevap Yok',
    description: 'Geri dönüş alınamadı',
    bgClass: 'bg-gray-100',
    textClass: 'text-gray-600',
    barClass: 'bg-gray-400',
    ringClass: 'ring-gray-300',
    order: 9,
    group: 'lost' as const,
  },
] as const;

export type DurumValue = (typeof DURUM_STATUSES)[number]['value'];

export const DURUM_OPTIONS = DURUM_STATUSES.map((s) => s.value);

export const FUNNEL_STAGE_COLORS: Record<string, string> = {
  iletisim: 'bg-slate-500',
  cevap: 'bg-sky-500',
  demo: 'bg-indigo-500',
  teklif: 'bg-cyan-500',
  satis: 'bg-emerald-500',
};

export function getDurumStatus(durum: string) {
  return DURUM_STATUSES.find((s) => s.value === durum);
}

export function getDurumBadgeClass(durum: string) {
  const status = getDurumStatus(durum);
  return status ? `${status.bgClass} ${status.textClass}` : 'bg-slate-100 text-slate-700';
}

export function getDurumBarClass(durum: string) {
  return getDurumStatus(durum)?.barClass || 'bg-slate-500';
}

export const ILETISIM_KANALLARI = [
  'Instagram DM',
  'WhatsApp',
  'Telefon',
  'E-posta',
  'Yüz yüze',
  'Diğer',
];

export const EMPTY_LEAD: LeadFormData = {
  isletme_adi: '',
  yetkili: '',
  sehir: '',
  instagram: '',
  whatsapp: '',
  eposta: '',
  ilk_iletisim_kanali: '',
  ilk_mesaj_tarihi: '',
  ilk_mesaj_saati: '',
  durum: 'Yeni',
  oncelik: 'orta',
  takip_1: '',
  takip_2: '',
  demo_gonderildi: false,
  demo_tarihi: '',
  gorusme_tarihi: '',
  gorusme_saati: '',
  teklif: '',
  sonuc: '',
  satis_tutari: 0,
  satis_tarihi: '',
  notlar: '',
  tag_ids: [],
};

export const EMPTY_LEAD_REQUEST: LeadRequestFormData = {
  category: '',
  isletme_adi: '',
  yetkili: '',
  sehir: '',
  instagram: '',
  whatsapp: '',
  eposta: '',
  ilk_iletisim_kanali: '',
  ilk_mesaj_tarihi: '',
  ilk_mesaj_saati: '',
  durum: 'Yeni',
  oncelik: 'orta',
  takip_1: '',
  takip_2: '',
  demo_gonderildi: false,
  demo_tarihi: '',
  gorusme_tarihi: '',
  gorusme_saati: '',
  teklif: '',
  sonuc: '',
  notlar: '',
  tag_ids: [],
};

export const EMPTY_EMPLOYEE: EmployeeFormData = {
  username: '',
  email: '',
  display_name: '',
  password: '',
  password_confirm: '',
};

export const EMPTY_TAG: TagFormData = {
  label: '',
  color: 'slate',
  id: '',
};

export const EMPTY_CATEGORY: CategoryFormData = {
  label: '',
  icon: 'building-2',
  id: '',
};
