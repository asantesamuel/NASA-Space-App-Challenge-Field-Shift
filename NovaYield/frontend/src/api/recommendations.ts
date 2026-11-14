import { api } from './client';
import type {
  EnvironmentalAnalysis,
  FarmEnvironmentalStatusResponse,
  FarmerPriority,
} from './farms';

export interface ScheduledCropEvent {
  order: number;
  crop_key: string;
  crop_name: string;
  planting_date: string;
  harvest_earliest: string;
  harvest_latest: string;
  season_key: string;
  calendar_source: string;
  calendar_version: string;
  calendar_status: string;
}

export interface RotationStepScore {
  order: number;
  crop_key: string;
  ratings: Record<'water_resilience' | 'soil_health' | 'growth_speed' | 'labour', number>;
  weights: Record<'water_resilience' | 'soil_health' | 'growth_speed' | 'labour', number>;
  weighted_score: number;
  weather_adjustment: 'applied' | 'not_triggered' | null;
  rationale: string[];
}

export interface RotationOption {
  rank: number;
  crops: [string, string, string];
  score: number;
  diversity_transitions: number;
  events: [ScheduledCropEvent, ScheduledCropEvent, ScheduledCropEvent];
  step_scores: [RotationStepScore, RotationStepScore, RotationStepScore];
  benefits: string[];
  trade_offs: string[];
  assumptions: string[];
  evidence: string[];
}

export interface RotationGeneration {
  status: 'ranked' | 'no_options';
  engine_version: string;
  scheduler_version: string;
  catalogue_version: string;
  calendar_version: string;
  configuration_version: string;
  weather_context_status: string;
  weather_weight_adjustment: 'applied' | 'not_triggered' | null;
  selected_priority: FarmerPriority | null;
  criteria: string[];
  options: RotationOption[];
  exclusion_counts: Record<string, number>;
  reason: string | null;
}

export interface SavedProductResult {
  id: string;
  farm_id: string;
  schema_version: string;
  created_at: string;
  decision_status?: string | null;
  history_event_snapshots?: {
    event_id: string;
    crop_key: string;
    sequence_order: number;
    start_date: string | null;
    end_date: string | null;
    production_system_key: string | null;
  }[];
  product_direction?: RotationGeneration | null;
  environmental_analysis?: EnvironmentalAnalysis | null;
  climate_cell_key?: string | null;
  climate_data_through?: string | null;
  crop_catalog_version?: string | null;
  calendar_version?: string | null;
  analysis_config_version?: string | null;
  engine_version?: string | null;
  scoring_result?: {
    options: unknown[];
    ranking?: { status: string } | null;
    provisional?: boolean;
  } | null;
}

export interface ProductDirectionRecommendationResponse {
  id: string;
  farm_id: string;
  created_at: string;
  environmental_status: FarmEnvironmentalStatusResponse;
  environmental_analysis: EnvironmentalAnalysis;
  recommendation: RotationGeneration;
}

export const recommendationApi = {
  listForFarm: (farmId: string) => api.get<SavedProductResult[]>(
    `/farms/${encodeURIComponent(farmId)}/rotation-results`,
  ),
  getEnvironment: (farmId: string) => api.get<FarmEnvironmentalStatusResponse>(
    `/farms/${encodeURIComponent(farmId)}/environment`,
  ),
  generateForFarm: (farmId: string, priority?: FarmerPriority | null) => api.post<ProductDirectionRecommendationResponse>(
    `/farms/${encodeURIComponent(farmId)}/recommendations`,
    priority ? { priority } : {},
  ),
};
