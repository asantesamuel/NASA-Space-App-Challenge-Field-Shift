import type {
  EnvironmentalAnalysis,
  EnvironmentalWindowFinding,
  FarmEnvironmentalStatusResponse,
} from '../../api/farms';
import DataSourceBadge from '../common/DataSourceBadge';
import {
  CategoryPill,
  CoverageNotes,
  StatusPill,
  WeatherCharts,
} from './charts';
import { formatDay, label } from './format';

function WeatherWindow({ finding }: { finding: EnvironmentalWindowFinding }) {
  const title = finding.window_type === 'since_harvest'
    ? 'Since the latest harvest'
    : `${label(finding.crop_key || 'Crop')} history`;

  return (
    <article className="weather-card">
      <div className="weather-card-head">
        <div>
          <h3>{title}</h3>
          <p className="rotation-meta">
            <time dateTime={finding.start_date}>{formatDay(finding.start_date)}</time>
            {' '}to{' '}
            <time dateTime={finding.end_date}>{formatDay(finding.end_date)}</time>
            {' '}· Data through {finding.data_through ? formatDay(finding.data_through) : 'unknown'}
          </p>
        </div>
        <StatusPill status={finding.status} />
      </div>
      <div className="pill-row">
        <CategoryPill prefix="Rain" category={finding.rainfall_category} />
        {finding.window_type === 'crop_event' && <CategoryPill prefix="Heat" category={finding.temperature_category} />}
        {finding.window_type === 'crop_event' && <CategoryPill category={finding.dry_spell_category} />}
      </div>
      <WeatherCharts finding={finding} />
      <CoverageNotes finding={finding} />
      {finding.notes.length > 0 && <ul>{finding.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>}
      {finding.window_type === 'since_harvest' && <p className="disclaimer">This is a historical weather note. It does not measure soil moisture.</p>}
    </article>
  );
}

export default function EnvironmentalPanel({
  status,
  analysis,
}: {
  status: FarmEnvironmentalStatusResponse | null;
  analysis: EnvironmentalAnalysis | null;
}) {
  const rangeText = analysis?.crop_windows.length
    ? `${analysis.reference_period_start}–${analysis.reference_period_end} normal · observed through ${analysis.data_through || 'unknown'}`
    : status?.data_through ? `Archive through ${status.data_through}` : 'No stored dates yet';
  const badgeStatus = status?.status === 'ready' || status?.status === 'partial'
    ? 'cached'
    : status?.status || 'unavailable';

  return (
    <section className="environmental-panel" aria-labelledby="environment-heading">
      <div className="section-heading">
        <div>
          <p className="kicker">Climate record</p>
          <h2 id="environment-heading">Stored environmental context</h2>
        </div>
        {status && <StatusPill status={status.status} />}
      </div>
      <DataSourceBadge
        status={badgeStatus}
        source={status?.source || 'NASA POWER Daily API'}
        dateRange={rangeText}
        resolution={status?.spatial_resolution}
      />
      {status?.safe_message && <p className="alert alert-warning">{status.safe_message}</p>}
      {status?.status === 'partial' && <p>Missing source values remain null; each window below shows its valid and missing day counts.</p>}
      {analysis?.crop_windows.length ? (
        <div className="insight-grid">
          {analysis.crop_windows.map((finding, index) => (
            <WeatherWindow key={`${finding.crop_key}-${finding.start_date}-${index}`} finding={finding} />
          ))}
          {analysis.since_harvest && <WeatherWindow finding={analysis.since_harvest} />}
        </div>
      ) : <p>Weather indicators remain unavailable until the background climate loader finishes.</p>}
      <p className="disclaimer">These are historical NASA grid-cell conditions, not a forecast, farm sensor, soil-moisture reading, or crop-damage estimate.</p>
    </section>
  );
}
