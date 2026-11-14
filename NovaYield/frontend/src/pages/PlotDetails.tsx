import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { farmApi, type FarmResponse } from '../api/farms';
import ErrorState from '../components/common/ErrorState';
import LoadingState from '../components/common/LoadingState';
import { SequenceRail } from '../components/dss/charts';
import { formatDay, label } from '../components/dss/format';
import { AlertIcon } from '../components/icons';
import PlotTabs from '../components/PlotTabs';

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

  if (loading || loadedFarmId !== farmId) return <LoadingState message="Loading plot…" />;
  if (error || !farm) return <ErrorState message={error || 'This plot could not be found.'} />;

  const encodedFarmId = encodeURIComponent(farm.id);

  return (
    <div className="page">
      <header className="page-header with-tabs">
        <div className="page-head-main">
          <h1>{farm.name}</h1>
          <p className="page-desc">{farm.location.label}</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-secondary" to={`/plots/${encodedFarmId}/edit`}>Edit plot</Link>
          <Link className="btn btn-primary" to={`/plots/${encodedFarmId}/recommendations`}>View recommendations</Link>
        </div>
      </header>
      <PlotTabs farmId={farm.id} />

      <div className="stack page-body">
        {farm.history_status !== 'complete' && (
          <p className="alert alert-warning">
            <AlertIcon />
            This plot needs actual dated crop history before a new recommendation can be generated. Legacy crop names have not been converted into dated events.
          </p>
        )}

        <section className="panel" aria-labelledby="plot-profile-heading">
          <div className="panel-header">
            <h2 className="panel-title" id="plot-profile-heading">Plot details</h2>
          </div>
          <dl className="panel-body kv">
            <div><dt>Location</dt><dd>{farm.location.label}</dd></div>
            <div><dt>Soil texture</dt><dd>{farm.soil_texture?.label || 'Not provided'}</dd></div>
            <div><dt>Irrigation access</dt><dd>{farm.irrigation_access?.label || 'Not provided'}</dd></div>
            <div><dt>Labour capacity</dt><dd>{farm.labour_capacity || 'Not provided'}</dd></div>
            <div><dt>Main priority</dt><dd>{farm.farmer_priority ? label(farm.farmer_priority) : 'None'}</dd></div>
            <div><dt>Available from</dt><dd>{farm.available_from ? formatDay(farm.available_from) : 'Latest harvest or today'}</dd></div>
          </dl>
        </section>

        <section className="panel" aria-labelledby="history-heading">
          <div className="panel-header">
            <div>
              <h2 className="panel-title" id="history-heading">Crop history</h2>
              <p className="panel-sub">Reported by you, oldest first.</p>
            </div>
            <span className="badge">{farm.crop_history.length} event{farm.crop_history.length === 1 ? '' : 's'}</span>
          </div>
          <div className="panel-body">
            {farm.crop_history.length ? (
              <SequenceRail large steps={farm.crop_history.map((event) => ({
                key: event.crop.key,
                name: event.crop.label,
                detail: event.start_date && event.end_date
                  ? `${formatDay(event.start_date)} – ${formatDay(event.end_date)}`
                  : 'Dates need review',
              }))} />
            ) : <p className="muted">No dated crop events are recorded for this plot.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
