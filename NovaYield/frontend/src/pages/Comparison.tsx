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

function RotationCard({ option }: { option: RotationOption }) {
  return (
    <article className="rotation-option">
      <div className="rotation-head">
        <div className="rank-seal" aria-hidden="true">{option.rank}</div>
        <div>
          <p className="kicker">Option {option.rank}</p>
          <h3>{option.events.map((event) => event.crop_name).join(' → ')}</h3>
          <p className="rotation-meta">{option.score.toFixed(2)} / 3 relative score</p>
        </div>
      </div>
      <SequenceRail
        steps={option.events.map((event) => ({
          key: event.crop_key,
          name: event.crop_name,
          detail: label(event.season_key),
        }))}
      />
      <DiversityMeter transitions={option.diversity_transitions} />
      <p className="disclaimer">Diversity is a soft tie-break preference. It never removes a sequence.</p>
      <h4>Scheduled future crop events</h4>
      <HarvestHorizon events={option.events} />
      <ol className="event-schedule">
        {option.events.map((event) => (
          <li key={event.order}>
            <span className="sequence-node">{event.order}</span>
            <div>
              <strong>{event.crop_name}</strong>
              <p className="event-detail">
                Plant <time dateTime={event.planting_date}>{formatDay(event.planting_date)}</time>
                {' '}· Expected harvest <time dateTime={event.harvest_earliest}>{formatDay(event.harvest_earliest)}</time>
                {' '}to <time dateTime={event.harvest_latest}>{formatDay(event.harvest_latest)}</time>
              </p>
              <p className="event-detail">{label(event.season_key)} · {label(event.calendar_status)} calendar evidence · {event.calendar_source}</p>
            </div>
          </li>
        ))}
      </ol>
      <h4>Ratings and weights by step</h4>
      <div className="step-stack">
        {option.step_scores.map((step) => (
          <article key={step.order} className="step-card">
            <h4>Step {step.order} · {label(step.crop_key)} · {step.weighted_score.toFixed(2)} / 3</h4>
            <RatingBars ratings={step.ratings} weights={step.weights} />
            <ul>{step.rationale.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
          </article>
        ))}
      </div>
      {(option.benefits.length > 0 || option.trade_offs.length > 0) && (
        <div className="insight-columns">
          {option.benefits.length > 0 && (
            <article>
              <h4>Relative strengths</h4>
              <ul>{option.benefits.map((item, index) => <li key={index}>{item}</li>)}</ul>
            </article>
          )}
          {option.trade_offs.length > 0 && (
            <article>
              <h4>Trade-offs</h4>
              <ul>{option.trade_offs.map((item, index) => <li key={index}>{item}</li>)}</ul>
            </article>
          )}
        </div>
      )}
      {option.assumptions.length > 0 && <details><summary>Assumptions and limitations</summary><ul>{option.assumptions.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}
      {option.evidence.length > 0 && <details><summary>Evidence references</summary><ul>{option.evidence.map((url) => <li key={url}><a href={url} target="_blank" rel="noreferrer">{url}</a></li>)}</ul></details>}
      <p className="alert alert-warning">The score is a relative rule-based comparison. It is not a probability, guaranteed yield, measured soil outcome, profitability estimate, or forecast.</p>
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
    return <div className="page-container"><p className="alert alert-warning">Choose a saved plot first.</p><Link to="/plots">Go to your plots</Link></div>;
  }

  const adjustmentText = analysis?.weather_weight_adjustment === 'applied'
    ? 'Applied for the first recommended crop only.'
    : analysis?.weather_weight_adjustment === 'not_triggered'
      ? 'Not triggered by the latest historical crop window.'
      : 'Unavailable; the base weight was retained.';

  return (
    <div className="page-container comparison-page">
      <header className="dss-hero">
        <div>
          {farm && <Link className="back-link" to={`/plots/${encodeURIComponent(farm.id)}`}>← {farm.name}</Link>}
          <p className="kicker">Rotation recommendations</p>
          <h1>{farm?.name ? `${farm.name} recommendations` : 'Plot recommendations'}</h1>
          {farm && (
            <div className="fact-row">
              <span className="fact-chip"><b>Place</b> {farm.location.label}</span>
              {farm.soil_texture && <span className="fact-chip"><b>Soil</b> {farm.soil_texture.label}</span>}
              {farm.irrigation_access && <span className="fact-chip"><b>Water access</b> {farm.irrigation_access.label}</span>}
              {farm.labour_capacity && <span className="fact-chip"><b>Labour</b> {farm.labour_capacity}</span>}
              <span className="fact-chip"><b>Priority</b> {farm.farmer_priority ? label(farm.farmer_priority) : 'None saved'}</span>
              <span className="fact-chip"><b>History</b> {farm.crop_history.length} dated event{farm.crop_history.length === 1 ? '' : 's'}</span>
            </div>
          )}
        </div>
        <button type="button" className="submit-btn" disabled={generating || !farm || farm.history_status !== 'complete'} onClick={() => void generate()}>
          {generating ? 'Preparing recommendation…' : 'Generate recommendations'}
        </button>
      </header>
      {farm && farm.crop_history.length > 0 && (
        <SequenceRail
          steps={farm.crop_history.map((event) => ({
            key: event.crop.key,
            name: event.crop.label,
            detail: event.start_date && event.end_date ? `${formatDay(event.start_date)} – ${formatDay(event.end_date)}` : 'Dates need review',
          }))}
        />
      )}
      {error && <p className="alert alert-error" role="alert">{error}</p>}
      {farm && farm.history_status !== 'complete' && <p className="alert alert-warning">Re-enter actual crop dates before generating a new recommendation. Legacy crop names are not converted into dated history.</p>}

      <section className="context-summary" aria-label="Environmental context status">
        <div>
          <p className="kicker">Environmental context</p>
          <strong>{environmentStatus?.status ? label(environmentStatus.status) : 'Checking status'}</strong>
          <p>{environmentStatus?.data_through
            ? `Stored NASA POWER context through ${formatDay(environmentStatus.data_through)}.`
            : 'Stored climate context and period coverage are available on the environmental context page.'}</p>
        </div>
        {farm && <Link className="secondary-btn" to={`/plots/${encodeURIComponent(farm.id)}/environment`}>View climate context</Link>}
      </section>
      {analysis?.weather_adjustment_reason && (
        <p className={analysis.weather_weight_adjustment === 'applied' ? 'callout' : 'callout caution'}>
          <strong>Water-weight adjustment:</strong> {adjustmentText} {analysis.weather_adjustment_reason}
        </p>
      )}
      {farm?.history_status === 'complete' && (
        <section className="priority-adjustment" aria-labelledby="priority-heading">
          <div className="section-heading">
            <div>
              <p className="kicker">This run</p>
              <h2 id="priority-heading">Optional priority</h2>
            </div>
          </div>
          <label htmlFor="run-priority">Choose one priority</label>
          <select id="run-priority" className="form-select" value={priority} onChange={(event) => setPriority(event.target.value as FarmerPriority | '')}>
            <option value="">Use the saved farm priority</option>
            <option value="water_security">Water security</option>
            <option value="soil_health">Soil health</option>
            <option value="fast_turnover">Fast turnover</option>
            <option value="low_labour">Low labour</option>
          </select>
          <p>A priority changes criterion weights and can change the order. The option cards show the ratings, weights, and trade-offs used.</p>
        </section>
      )}

      {history.length > 0 && (
        <section className="section-card" aria-labelledby="history-results-heading">
          <div className="section-heading">
            <div>
              <p className="kicker">Archive</p>
              <h2 id="history-results-heading">Saved recommendation results</h2>
            </div>
          </div>
          <div className="result-history-list">
            {history.map((item) => (
              <button key={item.id} type="button" className={item.id === selectedResult?.id ? 'secondary-btn run-chip active-result' : 'secondary-btn run-chip'} onClick={() => selectSaved(item)}>
                {new Date(item.created_at).toLocaleString()}
                <small>{item.product_direction?.status || item.decision_status || 'Earlier result format'}</small>
              </button>
            ))}
          </div>
        </section>
      )}

      {selectedResult && !recommendation && (
        <section className="result-overview">
          <h2>Earlier saved result</h2>
          <p>This result remains stored and can still be retrieved. It uses an earlier decision format, so it cannot be shown using the current crop-calendar and scoring presentation. Generate a new result to use the current product direction.</p>
          <p>Saved {new Date(selectedResult.created_at).toLocaleString()} · {selectedResult.schema_version}</p>
        </section>
      )}

      {recommendation && (
        <>
          <section className="result-overview" aria-labelledby="recommendation-heading">
            <div className="section-heading">
              <div>
                <p className="kicker">Result</p>
                <h2 id="recommendation-heading">Recommendation status: {label(recommendation.status)}</h2>
              </div>
              <StatusPill status={recommendation.status} />
            </div>
            <p>Four relative criteria are used: water resilience, soil effect, growth speed from maturity, and labour feasibility. The farmer-selected priority adds weight to one criterion. Crop-group diversity is the first tie-break after score and has no numeric bonus.</p>
            {recommendation.selected_priority && <p>Priority used: <strong>{label(recommendation.selected_priority)}</strong>.</p>}
            {recommendation.weather_context_status !== 'ready' && <p className="alert alert-warning">Weather context is {label(recommendation.weather_context_status)}. Missing weather is not filled in; no weather adjustment is assumed unless an available indicator meets the documented condition.</p>}
            {recommendation.reason && <p className="alert alert-warning">{recommendation.reason}</p>}
            <div className="stat-row">
              <article><strong>{recommendation.options.length}</strong><span>Options returned, maximum three</span></article>
              <article><strong>{recommendation.exclusion_counts.labour_capacity || 0}</strong><span>Excluded by labour capacity</span></article>
              <article><strong>{recommendation.exclusion_counts.candidate_disabled || 0}</strong><span>Missing or disabled candidate records</span></article>
              <article><strong>{recommendation.exclusion_counts.calendar_or_horizon || 0}</strong><span>No calendar within the horizon</span></article>
            </div>
            <details>
              <summary>How this result was produced</summary>
              <p>Engine {recommendation.engine_version} · Crop catalog {recommendation.catalogue_version} · Calendar {recommendation.calendar_version} · Configuration {recommendation.configuration_version}</p>
            </details>
          </section>
          {recommendation.options.length > 0 ? (
            <section aria-labelledby="options-heading">
              <div className="section-heading">
                <div>
                  <p className="kicker">Compare</p>
                  <h2 id="options-heading">Ranked rotation options</h2>
                </div>
              </div>
              <ScoreBoard options={recommendation.options.slice(0, 3)} />
              <div className="rotation-options">
                {recommendation.options.slice(0, 3).map((option: RotationOption) => <RotationCard key={option.rank} option={option} />)}
              </div>
            </section>
          ) : <p className="empty-state">No valid three-event rotation fits the current crop, labour, and location-calendar rules.</p>}
        </>
      )}
    </div>
  );
}
