import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { farmApi, type FarmResponse } from '../api/farms';
import ErrorState from '../components/common/ErrorState';
import LoadingState from '../components/common/LoadingState';
import { SequenceRail } from '../components/dss/charts';
import { formatDay, label } from '../components/dss/format';

export default function PlotDetails() {
  const { farmId = '' } = useParams();
  const [farm, setFarm] = useState<FarmResponse | null>(null);
  const [loadedFarmId, setLoadedFarmId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    farmApi.getFarm(farmId)
      .then((result) => {
        if (!active) return;
        setFarm(result);
        setError(null);
        setLoadedFarmId(farmId);
      })
      .catch((cause: unknown) => {
        if (active) {
          setError(cause instanceof Error ? cause.message : 'Could not load this plot.');
          setLoadedFarmId(farmId);
        }
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [farmId]);

  if (loading || loadedFarmId !== farmId) return <LoadingState message="Loading plot details…" />;
  if (error || !farm) return <ErrorState message={error || 'This plot could not be found.'} />;

  const encodedFarmId = encodeURIComponent(farm.id);

  return (
    <div className="page-container plot-detail-page">
      <header className="page-heading-row">
        <div>
          <Link className="back-link" to="/plots">← My plots</Link>
          <p className="kicker">Plot overview</p>
          <h1>{farm.name}</h1>
          <p className="lede">Review this decision plot’s profile and dated crop history, then open its climate context or recommendation results.</p>
        </div>
        <Link className="secondary-btn" to={`/plots/${encodedFarmId}/edit`}>Edit plot</Link>
      </header>

      {farm.history_status !== 'complete' && (
        <p className="alert alert-warning">This plot needs actual dated crop history before a new recommendation can be generated. Legacy crop names have not been converted into dated events.</p>
      )}

      <section className="plot-detail-card" aria-labelledby="plot-profile-heading">
        <div className="section-heading">
          <div>
            <p className="kicker">Farm profile</p>
            <h2 id="plot-profile-heading">Plot details</h2>
          </div>
        </div>
        <dl className="plot-detail-grid">
          <div><dt>Supported location</dt><dd>{farm.location.label}</dd></div>
          <div><dt>Soil context</dt><dd>{farm.soil_texture?.label || 'Not provided'}</dd></div>
          <div><dt>Irrigation access</dt><dd>{farm.irrigation_access?.label || 'Not provided'}</dd></div>
          <div><dt>Available labour</dt><dd>{farm.labour_capacity || 'Not provided'}</dd></div>
          <div><dt>Main priority</dt><dd>{farm.farmer_priority ? label(farm.farmer_priority) : 'No additional priority'}</dd></div>
          <div><dt>Available from</dt><dd>{farm.available_from ? formatDay(farm.available_from) : 'Based on latest harvest and today'}</dd></div>
        </dl>
      </section>

      <section className="plot-detail-card" aria-labelledby="history-heading">
        <div className="section-heading">
          <div>
            <p className="kicker">Farmer-reported history</p>
            <h2 id="history-heading">Past crop events</h2>
          </div>
          <span className="meta-chip">{farm.crop_history.length} event{farm.crop_history.length === 1 ? '' : 's'}</span>
        </div>
        {farm.crop_history.length ? (
          <SequenceRail steps={farm.crop_history.map((event) => ({
            key: event.crop.key,
            name: event.crop.label,
            detail: event.start_date && event.end_date
              ? `${formatDay(event.start_date)} – ${formatDay(event.end_date)}`
              : 'Dates need review',
          }))} />
        ) : <p>No dated crop events are recorded for this plot.</p>}
      </section>

      <section className="plot-next-steps" aria-labelledby="next-steps-heading">
        <div>
          <p className="kicker">Plot workspace</p>
          <h2 id="next-steps-heading">What would you like to review?</h2>
          <p>Environmental context and recommendations are kept on separate pages so each view has a clear purpose.</p>
        </div>
        <div className="saved-farm-actions">
          <Link className="secondary-btn" to={`/plots/${encodedFarmId}/environment`}>View environmental context</Link>
          <Link className="submit-btn" to={`/plots/${encodedFarmId}/recommendations`}>View recommendations</Link>
        </div>
      </section>
    </div>
  );
}
