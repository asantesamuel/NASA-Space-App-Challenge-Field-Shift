import type { EnvironmentalWindowFinding, MetricCoverage } from '../../api/farms';
import type { RotationOption, ScheduledCropEvent } from '../../api/recommendations';
import { categoryTone, cropColor, dayNumber, formatDay, label } from './format';

function coverageText(coverage: MetricCoverage): string {
  return `${coverage.valid_days}/${coverage.expected_days} observed days valid; ${coverage.missing_days} observed missing${
    coverage.reference_missing_days > 0
      ? `; ${coverage.reference_missing_days} calendar date(s) omitted from every reference year (${coverage.comparison_valid_days} comparison dates)`
      : ''
  }`;
}

export function StatusPill({ status }: { status: string }) {
  const tone = status === 'ready' || status === 'complete' || status === 'ranked' || status === 'cached'
    ? 'ready'
    : status === 'partial' || status === 'pending' || status === 'loading'
      ? 'partial'
      : status === 'error' || status === 'unavailable' || status === 'no_options'
        ? 'alert'
        : 'neutral';
  return <span className={`status-pill tone-${tone}`}>{label(status)}</span>;
}

export function CategoryPill({ category, prefix }: { category: string | null | undefined; prefix?: string }) {
  const tone = categoryTone(category);
  const text = category ? `${prefix ? `${prefix} ` : ''}${category}` : 'Unavailable';
  return <span className={`category-pill tone-${tone}`}>{text}</span>;
}

export function SequenceRail({
  steps,
}: {
  steps: { key: string; name: string; detail?: string }[];
}) {
  return (
    <ol className="sequence-rail">
      {steps.map((step, index) => (
        <li key={`${step.key}-${index}`}>
          <span className="sequence-node" style={{ background: cropColor(step.key) }} aria-hidden="true">
            {index + 1}
          </span>
          <span className="sequence-copy">
            <strong>{step.name}</strong>
            {step.detail && <small>{step.detail}</small>}
          </span>
        </li>
      ))}
    </ol>
  );
}

function BarPair({
  title,
  observedLabel,
  observed,
  referenceLabel,
  reference,
  unit,
  note,
}: {
  title: string;
  observedLabel: string;
  observed: number | null;
  referenceLabel: string;
  reference: number | null;
  unit: string;
  note?: string | null;
}) {
  const max = Math.max(observed ?? 0, reference ?? 0, 0.001);
  const width = (value: number | null) => (value == null ? 0 : Math.max((value / max) * 100, value > 0 ? 4 : 0));
  return (
    <div className="bar-pair" role="img" aria-label={`${title}. ${observedLabel} ${observed == null ? 'unavailable' : `${observed.toFixed(1)} ${unit}`}. ${referenceLabel} ${reference == null ? 'unavailable' : `${reference.toFixed(1)} ${unit}`}.`}>
      <div className="bar-pair-title">
        <strong>{title}</strong>
        {note && <span>{note}</span>}
      </div>
      <div className="bar-row">
        <span>{observedLabel}</span>
        <div className="bar-track"><div className="bar-fill observed" style={{ width: `${width(observed)}%` }} /></div>
        <b>{observed == null ? '—' : `${observed.toFixed(1)} ${unit}`}</b>
      </div>
      <div className="bar-row">
        <span>{referenceLabel}</span>
        <div className="bar-track"><div className="bar-fill reference" style={{ width: `${width(reference)}%` }} /></div>
        <b>{reference == null ? '—' : `${reference.toFixed(1)} ${unit}`}</b>
      </div>
    </div>
  );
}

function DeltaGauge({ delta }: { delta: number | null | undefined }) {
  if (delta == null) {
    return <p className="gauge-empty">Temperature difference from the normal is unavailable.</p>;
  }
  const capped = Math.max(-1, Math.min(1, delta / 3));
  const hotter = delta > 0;
  return (
    <div className="delta-gauge" role="img" aria-label={`Mean daily maximum temperature is ${delta > 0 ? '+' : ''}${delta.toFixed(1)} degrees Celsius versus the 1991 to 2020 normal.`}>
      <div className="delta-label">
        <span>Cooler</span>
        <strong>{delta > 0 ? '+' : ''}{delta.toFixed(1)} °C vs normal</strong>
        <span>Hotter</span>
      </div>
      <div className="delta-track">
        <i className="delta-center" />
        <i
          className={hotter ? 'delta-bar hotter' : 'delta-bar cooler'}
          style={hotter
            ? { left: '50%', width: `${capped * 50}%` }
            : { right: '50%', width: `${Math.abs(capped) * 50}%` }}
        />
      </div>
    </div>
  );
}

export function WeatherCharts({ finding }: { finding: EnvironmentalWindowFinding }) {
  const comparedRainfall = finding.rainfall_comparison_total_mm ?? finding.rainfall_total_mm;
  const ratio = finding.rainfall_ratio == null ? null : `${finding.rainfall_ratio.toFixed(2)}× the normal`;
  return (
    <div className="weather-charts">
      <BarPair
        title="Rainfall"
        observedLabel="Observed"
        observed={comparedRainfall}
        referenceLabel="1991–2020 median"
        reference={finding.rainfall_reference_median_mm}
        unit="mm"
        note={ratio}
      />
      {finding.rainfall_total_mm != null && finding.rainfall_comparison_total_mm != null && finding.rainfall_total_mm !== finding.rainfall_comparison_total_mm && (
        <p className="chart-note">Full-window rainfall total is {finding.rainfall_total_mm.toFixed(1)} mm. The bar uses the comparison total of {finding.rainfall_comparison_total_mm.toFixed(1)} mm.</p>
      )}
      {finding.window_type === 'crop_event' && (
        <>
          <div className="temp-block">
            <div className="bar-pair-title">
              <strong>Mean daily maximum temperature</strong>
              <span>{finding.mean_t2m_max_c == null ? 'Unavailable' : `${finding.mean_t2m_max_c.toFixed(1)} °C`}</span>
            </div>
            {finding.comparison_mean_t2m_max_c != null && finding.reference_mean_t2m_max_c != null && (
              <p className="chart-note">
                Comparison window {finding.comparison_mean_t2m_max_c.toFixed(1)} °C versus normal {finding.reference_mean_t2m_max_c.toFixed(1)} °C.
              </p>
            )}
            <DeltaGauge delta={finding.temperature_delta_c} />
          </div>
          <BarPair
            title="Longest dry spell"
            observedLabel="This window"
            observed={finding.longest_dry_spell_days ?? null}
            referenceLabel="Normal 75th percentile"
            reference={finding.reference_dry_spell_p75_days ?? null}
            unit="days"
            note={finding.longest_dry_spell_text}
          />
        </>
      )}
    </div>
  );
}

export function CoverageNotes({ finding }: { finding: EnvironmentalWindowFinding }) {
  return (
    <ul className="coverage-notes">
      <li>Rainfall coverage: {coverageText(finding.rainfall_coverage)}</li>
      {finding.window_type === 'crop_event' && finding.temperature_coverage && (
        <li>Temperature coverage: {coverageText(finding.temperature_coverage)}</li>
      )}
      {finding.window_type === 'crop_event' && finding.dry_spell_coverage && (
        <li>Dry-spell coverage: {coverageText(finding.dry_spell_coverage)}</li>
      )}
    </ul>
  );
}

const CRITERIA = [
  ['water_resilience', 'Water resilience'],
  ['soil_health', 'Soil effect'],
  ['growth_speed', 'Growth speed'],
  ['labour', 'Labour'],
] as const;

export function RatingBars({
  ratings,
  weights,
}: {
  ratings: Record<string, number>;
  weights: Record<string, number>;
}) {
  return (
    <div className="rating-bars" role="img" aria-label="Relative ratings from 1 to 3 and the weights used for this step.">
      {CRITERIA.map(([key, name]) => {
        const rating = ratings[key] ?? 0;
        const weight = weights[key] ?? 0;
        return (
          <div className="rating-row" key={key}>
            <span>{name}</span>
            <div className="rating-track" title={`Rating ${rating} of 3, weight ${weight}`}>
              <div className="rating-fill" style={{ width: `${(rating / 3) * 100}%` }} />
              {[1, 2].map((mark) => <i key={mark} style={{ left: `${(mark / 3) * 100}%` }} />)}
            </div>
            <b>{rating}/3</b>
            <em>×{weight}</em>
          </div>
        );
      })}
    </div>
  );
}

export function HarvestHorizon({ events }: { events: ScheduledCropEvent[] }) {
  const start = Math.min(...events.map((event) => dayNumber(event.planting_date)));
  const end = Math.max(...events.map((event) => dayNumber(event.harvest_latest)));
  const span = Math.max(end - start, 1);
  const place = (iso: string) => ((dayNumber(iso) - start) / span) * 100;
  const summary = events.map((event) => `${event.crop_name} planted ${formatDay(event.planting_date)}, harvest ${formatDay(event.harvest_earliest)} to ${formatDay(event.harvest_latest)}`).join('. ');

  return (
    <div className="horizon" role="img" aria-label={`Planting and harvest windows. ${summary}`}>
      {events.map((event) => {
        const plant = place(event.planting_date);
        const early = place(event.harvest_earliest);
        const late = place(event.harvest_latest);
        return (
          <div className="horizon-row" key={event.order}>
            <span>{event.crop_name}</span>
            <div className="horizon-track">
              <div className="horizon-grow" style={{ left: `${plant}%`, width: `${Math.max(early - plant, 1.5)}%`, background: cropColor(event.crop_key) }} />
              <div className="horizon-window" style={{ left: `${early}%`, width: `${Math.max(late - early, 1.5)}%` }} />
            </div>
          </div>
        );
      })}
      <div className="horizon-legend">
        <span><i className="swatch grow" /> Planting to earliest harvest</span>
        <span><i className="swatch window" /> Possible harvest window</span>
        <span>{formatDay(events[0].planting_date)} – {formatDay(events[events.length - 1].harvest_latest)}</span>
      </div>
    </div>
  );
}

export function ScoreBoard({ options }: { options: RotationOption[] }) {
  const max = 3;
  return (
    <div className="score-board" role="img" aria-label={options.map((option) => `Option ${option.rank} scores ${option.score.toFixed(2)} out of 3`).join('. ')}>
      {options.map((option) => (
        <div className="score-row" key={option.rank}>
          <span className="score-rank">#{option.rank}</span>
          <div className="score-copy">
            <strong>{option.events.map((event) => event.crop_name).join(' → ')}</strong>
            <div className="score-track">
              <div style={{ width: `${(option.score / max) * 100}%` }} />
            </div>
          </div>
          <b>{option.score.toFixed(2)}<small>/ 3</small></b>
        </div>
      ))}
      <p>Scores are relative weighted ratings. A higher bar is a better fit under the rules used for this run, not a predicted yield.</p>
    </div>
  );
}

export function DiversityMeter({ transitions }: { transitions: number }) {
  return (
    <div className="diversity-meter" aria-label={`${transitions} of 2 adjacent seasons change crop group.`}>
      <span>Crop-group changes</span>
      <div>
        {[0, 1].map((index) => <i key={index} className={index < transitions ? 'on' : ''} />)}
      </div>
      <b>{transitions} / 2</b>
    </div>
  );
}
