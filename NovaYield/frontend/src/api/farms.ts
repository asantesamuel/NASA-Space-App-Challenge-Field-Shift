import { api } from './client';

export interface CropOption {
  id: string;
  crop_key: string;
  common_name: string;
  scientific_name?: string | null;
  aliases?: string[];
  history_selectable: boolean;
  recommendation_candidate: boolean;
  requires_variety_for_timing?: boolean;
  requires_production_system_for_assessment?: boolean;
  production_system?: string | null;
  water_resilience?: string | null;
  soil_effect?: string | null;
  maturity_days_min?: number | null;
  maturity_days_max?: number | null;
  growth_speed?: string | null;
  labour?: string | null;
  catalog_version?: string;
  source_note?: string | null;
  parameter_evidence?: Record<string, {
    source_urls?: string[];
    evidence_kind?: string;
    confidence?: string;
    applicability?: string;
    limitations?: string;
  }>;
}

export interface CropCatalogResponse {
  catalog_version: string;
  crops: CropOption[];
}

export interface ReferenceOption {
  key: string;
  label: string;
  definition: string;
}

export interface FarmReferenceOptionsResponse {
  catalog_version: string;
  soil_textures: ReferenceOption[];
  irrigation_access: ReferenceOption[];
  labour_capacity: ReferenceOption[];
  farmer_priorities: ReferenceOption[];
  rice_production_systems: ReferenceOption[];
}

export interface SupportedLocationsResponse {
  coverage_notice: string;
  locations: { location_key: string; label: string }[];
}

export type FarmerPriority = 'water_security' | 'soil_health' | 'fast_turnover' | 'low_labour';
export type LabourCapacity = 'Low' | 'Medium' | 'High';
export type RiceSystem = 'upland' | 'rain-fed-lowland' | 'irrigated' | 'unknown';

export interface CropHistoryInput {
  crop_key: string;
  sequence_order: number;
  start_date: string;
  end_date: string;
  production_system_key?: RiceSystem | null;
}

export interface FarmCreateInput {
  name: string;
  location_key: string;
  soil_texture_key: string;
  irrigation_access_key: string;
  history_status: 'complete';
  crop_history: CropHistoryInput[];
  labour_capacity: LabourCapacity;
  available_from?: string | null;
  farmer_priority?: FarmerPriority | null;
}

export interface FarmResponse {
  id: string;
  schema_version: string;
  revision: number;
  name: string;
  location: { location_key?: string; key?: string; label: string };
  soil_texture?: ReferenceOption | null;
  irrigation_access?: ReferenceOption | null;
  history_status: string;
  crop_history: {
    event_id: string;
    crop: { id: string; key: string; label: string };
    sequence_order: number;
    start_date: string | null;
    end_date: string | null;
    production_system_key?: string | null;
  }[];
  labour_capacity?: LabourCapacity | null;
  available_from?: string | null;
  farmer_priority?: FarmerPriority | null;
  environmental_context?: { status: string; warning_code?: string | null } | null;
  legacy_unresolved_inputs?: {
    previous_crops: string[] | null;
    soil_texture: string | null;
    irrigation_access: string | null;
  } | null;
}

export interface MetricCoverage {
  expected_days: number;
  valid_days: number;
  missing_days: number;
  leap_days_excluded: number;
  matching_reference_years: number;
  comparison_valid_days: number;
  reference_missing_days: number;
}

export interface EnvironmentalWindowFinding {
  window_type: 'crop_event' | 'since_harvest';
  crop_key: string | null;
  start_date: string;
  end_date: string;
  status: string;
  rainfall_total_mm: number | null;
  rainfall_comparison_total_mm?: number | null;
  rainfall_reference_median_mm: number | null;
  rainfall_ratio: number | null;
  rainfall_category: string | null;
  rainfall_coverage: MetricCoverage;
  mean_t2m_max_c?: number | null;
  comparison_mean_t2m_max_c?: number | null;
  reference_mean_t2m_max_c?: number | null;
  temperature_delta_c?: number | null;
  temperature_category?: string | null;
  temperature_coverage?: MetricCoverage | null;
  longest_dry_spell_days?: number | null;
  longest_dry_spell_text?: string | null;
  reference_dry_spell_p75_days?: number | null;
  dry_spell_category?: string | null;
  dry_spell_coverage?: MetricCoverage | null;
  missing_parameters: string[];
  notes: string[];
  source: string;
  data_through: string | null;
  method_version: string;
  interpretation: string;
}

export interface EnvironmentalAnalysis {
  status: string;
  reference_period_start: number;
  reference_period_end: number;
  data_through: string | null;
  source: string;
  crop_windows: EnvironmentalWindowFinding[];
  since_harvest: EnvironmentalWindowFinding | null;
  weather_weight_adjustment: 'applied' | 'not_triggered' | null;
  weather_adjustment_reason: string | null;
  missing_parameters: string[];
  method_version: string;
}

export interface FarmEnvironmentalStatusResponse {
  farm_id: string;
  location: { location_key: string; label: string };
  status: 'location_unmapped' | 'pending' | 'loading' | 'ready' | 'partial' | 'error' | 'unavailable';
  cell_key: string | null;
  source: string;
  spatial_resolution: string | null;
  first_date: string | null;
  data_through: string | null;
  completed_chunk_count: number;
  failed_chunk_count: number;
  safe_message: string | null;
  analysis: EnvironmentalAnalysis | null;
}

export const farmApi = {
  listLocations: () => api.get<SupportedLocationsResponse>('/farms/locations'),
  listCrops: () => api.get<CropCatalogResponse>('/crops?usage=history'),
  listReferences: () => api.get<FarmReferenceOptionsResponse>('/farms/reference-options'),
  listFarms: () => api.get<FarmResponse[]>('/farms'),
  getFarm: (farmId: string) => api.get<FarmResponse>(`/farms/${encodeURIComponent(farmId)}`),
  createFarm: (input: FarmCreateInput) => api.post<FarmResponse>('/farms', input),
  updateFarm: (farmId: string, input: Partial<FarmCreateInput>) => api.patch<FarmResponse>(
    `/farms/${encodeURIComponent(farmId)}`,
    input,
  ),
  getEnvironment: (farmId: string) => api.get<FarmEnvironmentalStatusResponse>(
    `/farms/${encodeURIComponent(farmId)}/environment`,
  ),
};
