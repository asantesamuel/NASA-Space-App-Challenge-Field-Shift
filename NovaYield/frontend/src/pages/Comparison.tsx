import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  farmApi,
  type EnvironmentalAnalysis,
  type FarmEnvironmentalStatusResponse,
  type FarmResponse,
  type FarmerPriority,
} from '../api/farms';
import {
  recommendationApi,
  type RotationGeneration,
  type RotationOption,
  type SavedProductResult,
} from '../api/recommendations';
import {
  DiversityMeter,
  HarvestHorizon,
  RatingBars,
  ScoreBoard,
  SequenceRail,
  StatusPill,
} from '../components/dss/charts';
import { formatDay, label } from '../components/dss/format';
import { AlertIcon, InfoIcon } from '../components/icons';
import PlotTabs from '../components/PlotTabs';

function RotationCard({ option }: { option: RotationOption }) {
  return (
    <article className="panel">
      <div className="option-head">
        <span className="rank" aria-hidden="true">{option.rank}</span>
        <div className="option-title">
          <p className="section-label">Option {option.rank}</p>
          <h3>{option.events.map((event) => event.crop_name).join(' → ')}</h3>
        </div>
        <div className="option-score">
          <strong>{option.score.toFixed(2)}</strong>
          <span>relative score / 3</span>
        </div>
      </div>

      <div className="option-body">
        <section className="option-section">
          <SequenceRail
            steps={option.events.map((event) => ({
              key: event.crop_key,
              name: event.crop_name,
              detail: label(event.season_key),
            }))}
          />
          <DiversityMeter transitions={option.diversity_transitions} />
          <p className="disclaimer">Diversity is a soft tie-break. It never removes a sequence.</p>
        </section>

        <section className="option-section">
          <h4>Planting and harvest schedule</h4>
          <HarvestHorizon events={option.events} />
          <div className="table-wrap bordered">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Crop</th>
                  <th scope="col">Plant</th>
                  <th scope="col">Expected harvest</th>
                  <th scope="col">Calendar evidence</th>
                </tr>
              </thead>
              <tbody>
                {option.events.map((event) => (
                  <tr key={event.order}>
                    <td className="num">{event.order}</td>
                    <td>
                      <strong>{event.crop_name}</strong>
                      <small>{label(event.season_key)}</small>
                    </td>
                    <td className="num"><time dateTime={event.planting_date}>{formatDay(event.planting_date)}</time></td>
                    <td className="num">
                      <time dateTime={event.harvest_earliest}>{formatDay(event.harvest_earliest)}</time>
                      {' – '}
                      <time dateTime={event.harvest_latest}>{formatDay(event.harvest_latest)}</time>
                    </td>
                    <td>
                      {label(event.calendar_status)}
                      <small>
                        {event.calendar_evidence?.source_url ? (
                          <a href={event.calendar_evidence.source_url} target="_blank" rel="noreferrer">
                            {event.calendar_source}
                          </a>
                        ) : event.calendar_source}
                      </small>
                      {event.calendar_evidence && (
                        <details>
                          <summary>Scope and limitations</summary>
                          {event.calendar_evidence.window_basis && (
                            <small>{label(event.calendar_evidence.window_basis)}</small>
                          )}
                          <small>{event.calendar_evidence.applicability}</small>
                          <small>{event.calendar_evidence.limitations}</small>
                        </details>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="option-section">
          <h4>Ratings and weights by step</h4>
          <div className="step-grid">
            {option.step_scores.map((step) => (
              <article key={step.order} className="step-card">
                <div className="step-card-head">
                  <h4>Step {step.order} · {label(step.crop_key)}</h4>
                  <span>{step.weighted_score.toFixed(2)} / 3</span>
                </div>
                <RatingBars ratings={step.ratings} weights={step.weights} />
                <ul className="reasons">{step.rationale.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
              </article>
            ))}
          </div>
        </section>

        {(option.benefits.length > 0 || option.trade_offs.length > 0) && (
          <div className="insight-columns">
            {option.benefits.length > 0 && (
              <section className="insight positive">
                <h4>Relative strengths</h4>
                <ul className="bullets">{option.benefits.map((item, index) => <li key={index}>{item}</li>)}</ul>
              </section>
            )}
            {option.trade_offs.length > 0 && (
              <section className="insight negative">
                <h4>Trade-offs</h4>
                <ul className="bullets">{option.trade_offs.map((item, index) => <li key={index}>{item}</li>)}</ul>
              </section>
            )}
          </div>
        )}

        {option.assumptions.length > 0 && (
          <details className="disclosure">
            <summary>Assumptions and limitations</summary>
            <div className="disclosure-body"><ul className="bullets">{option.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul></div>
          </details>
        )}
        {option.evidence.length > 0 && (
          <details className="disclosure">
            <summary>Evidence references</summary>
            <div className="disclosure-body">
              <ul className="bullets">{option.evidence.map((url) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul>
            </div>
          </details>
        )}
        <p className="disclaimer">The score is a relative, rule-based comparison. It is not a probability, guaranteed yield, measured soil outcome, profitability estimate, or forecast.</p>
      </div>
    </article>
  );
}

export default function Comparison() {
  const { farmId = '' } = useParams();
  const [farm, setFarm] = useState<FarmResponse | null>(null);
  const [history, setHistory] = useState<SavedProductResult[]>([]);
  const [selectedResult, setSelectedResult] = useState<SavedProductResult | null>(null);
  const [recommendation, setRecommendation] = useState<RotationGeneration | null>(null);
  const [analysis, setAnalysis] = useState<EnvironmentalAnalysis | null>(null);
  const [environmentStatus, setEnvironmentStatus] = useState<FarmEnvironmentalStatusResponse | null>(null);
  const [priority, setPriority] = useState<FarmerPriority | ''>('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!farmId) return;
    let active = true;
    Promise.all([
      farmApi.getFarm(farmId),
      recommendationApi.listForFarm(farmId),
      recommendationApi.getEnvironment(farmId),
    ]).then(([farmResponse, savedResults, climate]) => {
      if (!active) return;
      setFarm(farmResponse);
      setError(null);
      setHistory([...savedResults].sort((left, right) => right.created_at.localeCompare(left.created_at)));
      setEnvironmentStatus(climate);
      const newest = [...savedResults].sort((left, right) => right.created_at.localeCompare(left.created_at))[0];
      if (newest?.product_direction) {
        setSelectedResult(newest);
        setRecommendation(newest.product_direction);
        setAnalysis(newest.environmental_analysis || climate.analysis);
      } else if (climate.analysis) {
        setAnalysis(climate.analysis);
      }
    }).catch((cause: unknown) => {
      if (active) setError(cause instanceof Error ? cause.message : 'Could not load this plot.');
    });
    return () => { active = false; };
  }, [farmId]);

  const generate = async () => {
    if (!farmId) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await recommendationApi.generateForFarm(farmId, priority || undefined);
      setRecommendation(result.recommendation);
      setAnalysis(result.environmental_analysis);
      setEnvironmentStatus(result.environmental_status);
      setSelectedResult(null);
      const saved = await recommendationApi.listForFarm(farmId);
      setHistory([...saved].sort((left, right) => right.created_at.localeCompare(left.created_at)));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not save a recommendation result.');
    } finally {
      setGenerating(false);
    }
  };

  const selectSaved = (item: SavedProductResult) => {
    setSelectedResult(item);
    setRecommendation(item.product_direction || null);
    setAnalysis(item.environmental_analysis || null);
    setError(null);
  };

  if (!farmId) {
    return (
      <div className="page">
        <p className="alert alert-warning"><AlertIcon />Choose a saved plot first.</p>
        <p className="mt-6"><Link to="/plots">Go to your plots</Link></p>
      </div>
    );
  }

  const adjustmentText = analysis?.weather_weight_adjustment === 'applied'
    ? 'Applied for the first recommended crop only.'
    : analysis?.weather_weight_adjustment === 'not_triggered'
      ? 'Not triggered by the latest historical crop window.'
      : 'Unavailable; the base weight was retained.';

  const canGenerate = Boolean(farm) && farm?.history_status === 'complete';

  return (
    <div className="page">
      <header className="page-header with-tabs">
        <div className="page-head-main">
          <h1>{farm?.name || 'Plot'}</h1>
          {farm && (
            <ul className="meta-list">
              <li>{farm.location.label}</li>
              {farm.soil_texture && <li>{farm.soil_texture.label} soil</li>}
              {farm.irrigation_access && <li>{farm.irrigation_access.label}</li>}
              {farm.labour_capacity && <li>{farm.labour_capacity} labour</li>}
              <li>Priority: <b>{farm.farmer_priority ? label(farm.farmer_priority) : 'none saved'}</b></li>
            </ul>
          )}
        </div>
      </header>
      {farm && <PlotTabs farmId={farm.id} />}

      <div className="stack page-body">
        {error && <p className="alert alert-error" role="alert"><AlertIcon />{error}</p>}
        {farm && farm.history_status !== 'complete' && (
          <p className="alert alert-warning"><AlertIcon />Re-enter actual crop dates before generating a new recommendation. Legacy crop names are not converted into dated history.</p>
        )}

        <section className="panel" aria-labelledby="run-heading">
          <div className="panel-header">
            <div>
              <h2 className="panel-title" id="run-heading">Generate recommendations</h2>
              <p className="panel-sub">A priority changes the criterion weights and can change the order. Option cards show the ratings and weights used.</p>
            </div>
          </div>
          <div className="panel-body stack-sm">
            {farm && farm.crop_history.length > 0 && (
              <div>
                <p className="col-label">Based on your crop history</p>
                <SequenceRail
                  steps={farm.crop_history.map((event) => ({
                    key: event.crop.key,
                    name: event.crop.label,
                    detail: event.start_date && event.end_date ? `${formatDay(event.start_date)} – ${formatDay(event.end_date)}` : 'Dates need review',
                  }))}
                />
              </div>
            )}
            <div className="toolbar mt-6">
              <div className="field">
                <label className="label" htmlFor="run-priority">Priority for this run</label>
                <select id="run-priority" className="select" value={priority} onChange={(event) => setPriority(event.target.value as FarmerPriority | '')} disabled={!canGenerate}>
                  <option value="">Use the saved plot priority</option>
                  <option value="water_security">Water security</option>
                  <option value="soil_health">Soil health</option>
                  <option value="fast_turnover">Fast turnover</option>
                  <option value="low_labour">Low labour</option>
                </select>
              </div>
              {history.length > 0 && (
                <div className="field">
                  <label className="label" htmlFor="saved-result">Saved results</label>
                  <select
                    id="saved-result"
                    className="select"
                    value={selectedResult?.id ?? ''}
                    onChange={(event) => {
                      const item = history.find((entry) => entry.id === event.target.value);
                      if (item) selectSaved(item);
                    }}
                  >
                    {!selectedResult && <option value="">Latest run (unsaved view)</option>}
                    {history.map((item) => (
                      <option key={item.id} value={item.id}>
                        {new Date(item.created_at).toLocaleString()} · {label(item.product_direction?.status || item.decision_status || 'earlier_format')}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <button type="button" className="btn btn-primary" disabled={generating || !canGenerate} onClick={() => void generate()}>
                {generating ? 'Preparing…' : 'Generate recommendations'}
              </button>
            </div>
          </div>
          <div className="panel-footer">
            <span className="muted">
              Climate data: <b>{environmentStatus?.status ? label(environmentStatus.status) : 'checking'}</b>
              {environmentStatus?.data_through && <> · stored through {formatDay(environmentStatus.data_through)}</>}
            </span>
            {farm && <Link className="btn btn-ghost btn-sm" to={`/plots/${encodeURIComponent(farm.id)}/environment`}>View climate</Link>}
          </div>
        </section>

        {analysis?.weather_adjustment_reason && (
          <p className={analysis.weather_weight_adjustment === 'applied' ? 'alert alert-success' : 'alert alert-warning'}>
            <InfoIcon />
            <span><strong>Water-weight adjustment.</strong> {adjustmentText} {analysis.weather_adjustment_reason}</span>
          </p>
        )}

        {selectedResult && !recommendation && (
          <section className="panel">
            <div className="panel-header"><h2 className="panel-title">Earlier saved result</h2></div>
            <div className="panel-body stack-sm">
              <p>This result is still stored but uses an earlier decision format, so it can’t be shown with the current crop-calendar and scoring view. Generate a new result to use the current product direction.</p>
              <p className="muted">Saved {new Date(selectedResult.created_at).toLocaleString()} · {selectedResult.schema_version}</p>
            </div>
          </section>
        )}

        {recommendation && (
          <>
            <section className="stack-sm" aria-labelledby="recommendation-heading">
              <div className="row row-between">
                <h2 id="recommendation-heading">Result</h2>
                <StatusPill status={recommendation.status} />
              </div>
              <div className="stats">
                <div className="stat"><strong>{recommendation.options.length}</strong><span>Options returned (max 3)</span></div>
                <div className="stat"><strong>{recommendation.exclusion_counts.labour_capacity || 0}</strong><span>Excluded by labour capacity</span></div>
                <div className="stat"><strong>{recommendation.exclusion_counts.candidate_disabled || 0}</strong><span>Missing or disabled crops</span></div>
                <div className="stat"><strong>{recommendation.exclusion_counts.calendar_or_horizon || 0}</strong><span>No calendar in horizon</span></div>
              </div>
              <p className="disclaimer">
                Four relative criteria are used: water resilience, soil effect, growth speed from maturity, and labour feasibility.
                {recommendation.selected_priority && <> Priority used: <b>{label(recommendation.selected_priority)}</b>.</>}
                {' '}Crop-group diversity is the first tie-break after score and carries no numeric bonus.
              </p>
              {recommendation.weather_context_status !== 'ready' && (
                <p className="alert alert-warning"><AlertIcon />Weather context is {label(recommendation.weather_context_status).toLowerCase()}. Missing weather is not filled in, and no weather adjustment is assumed unless an available indicator meets the documented condition.</p>
              )}
              {recommendation.reason && <p className="alert alert-warning"><AlertIcon />{recommendation.reason}</p>}
              <details className="disclosure">
                <summary>How this result was produced</summary>
                <div className="disclosure-body">
                  Engine {recommendation.engine_version} · Crop catalogue {recommendation.catalogue_version} · Calendar {recommendation.calendar_version} · Configuration {recommendation.configuration_version}
                </div>
              </details>
            </section>

            {recommendation.options.length > 0 ? (
              <section className="stack-sm" aria-labelledby="options-heading">
                <h2 id="options-heading">Ranked rotation options</h2>
                {recommendation.options.some((option) => option.events.some(
                  (event) => event.calendar_version === 'product-direction-kintampo-v1',
                )) && (
                  <p className="disclaimer">
                    Kintampo’s provisional windows are historical planning assumptions.
                    Check current planting guidance with local extension.
                  </p>
                )}
                <ScoreBoard options={recommendation.options.slice(0, 3)} />
                <div className="option-list">
                  {recommendation.options.slice(0, 3).map((option: RotationOption) => <RotationCard key={option.rank} option={option} />)}
                </div>
              </section>
            ) : (
              <p className="empty">No valid three-event rotation fits the current crop, labour, and location-calendar rules.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
