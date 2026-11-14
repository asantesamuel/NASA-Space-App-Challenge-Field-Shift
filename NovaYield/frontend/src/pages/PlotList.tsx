import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  farmApi,
  type FarmEnvironmentalStatusResponse,
  type FarmResponse,
} from '../api/farms';
import ErrorState from '../components/common/ErrorState';
import LoadingState from '../components/common/LoadingState';
import { SequenceRail, StatusPill } from '../components/dss/charts';
import { formatDay, label } from '../components/dss/format';
import { AlertIcon, PlusIcon, SproutIcon } from '../components/icons';

export default function PlotList() {
  const [farms, setFarms] = useState<FarmResponse[]>([]);
  const [climateStatuses, setClimateStatuses] = useState<Record<string, FarmEnvironmentalStatusResponse>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusLoading, setStatusLoading] = useState<string | null>(null);

  const loadPlots = useCallback(async () => {
    try {
      const loadedFarms = await farmApi.listFarms();
      setError(null);
      setFarms(loadedFarms);
      const entries = await Promise.all(loadedFarms.map(async (farm) => {
        try {
          return [farm.id, await farmApi.getEnvironment(farm.id)] as const;
        } catch {
          return null;
        }
      }));
      setClimateStatuses(Object.fromEntries(
        entries.filter((item): item is NonNullable<typeof item> => item !== null),
      ));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load your plots.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadPlots);
  }, [loadPlots]);

  const refreshClimateStatus = async (farmId: string) => {
    setStatusLoading(farmId);
    try {
      const result = await farmApi.getEnvironment(farmId);
      setClimateStatuses((current) => ({ ...current, [farmId]: result }));
    } catch {
      // Keep the last known state visible if a manual refresh cannot reach the API.
    } finally {
      setStatusLoading(null);
    }
  };

  if (loading) return <LoadingState message="Loading your plots…" />;
  if (error) return <ErrorState message={error} onRetry={() => { setLoading(true); void loadPlots(); }} />;

  return (
    <div className="page">
      <header className="page-header">
        <div className="page-head-main">
          <h1>My plots</h1>
          <p className="page-desc">Open a plot to review its profile, historical climate, and rotation recommendations.</p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-primary" to="/plots/new"><PlusIcon />Add plot</Link>
        </div>
      </header>

      {farms.length === 0 ? (
        <section className="empty">
          <span className="empty-icon"><SproutIcon /></span>
          <h2>No plots yet</h2>
          <p>Add a plot and enter the crops you have grown on it. NovaYield keeps each plot and its recommendations together.</p>
          <Link className="btn btn-primary" to="/plots/new">Set up your first plot</Link>
        </section>
      ) : (
        <section className="panel" aria-labelledby="saved-plots-heading">
          <div className="panel-header">
            <h2 className="panel-title" id="saved-plots-heading">Saved plots</h2>
            <span className="badge">{farms.length} plot{farms.length === 1 ? '' : 's'}</span>
          </div>

          <ul className="plot-list">
            {farms.map((farm) => {
              const climate = climateStatuses[farm.id];
              const climateSummary = climate?.data_through
                ? `Through ${formatDay(climate.data_through)}${climate.spatial_resolution ? ` · ${climate.spatial_resolution}` : ''}`
                : climate?.safe_message || 'Climate status not checked yet.';
              const id = encodeURIComponent(farm.id);

              return (
                <li key={farm.id} className="plot-row">
                  <div>
                    <Link className="plot-name" to={`/plots/${id}`}>{farm.name}</Link>
                    <ul className="meta-list plot-facts" aria-label="Plot details">
                      <li>{farm.location.label}</li>
                      {farm.soil_texture && <li>{farm.soil_texture.label} soil</li>}
                      {farm.labour_capacity && <li>{farm.labour_capacity} labour</li>}
                      <li>{farm.farmer_priority ? label(farm.farmer_priority) : 'No priority'}</li>
                    </ul>
                  </div>

                  <div className="plot-actions">
                    <Link className="btn btn-secondary btn-sm" to={`/plots/${id}`}>View</Link>
                    <Link className="btn btn-primary btn-sm" to={`/plots/${id}/recommendations`}>Recommendations</Link>
                  </div>

                  <div className="plot-body">
                    <div>
                      <p className="col-label">Crop history</p>
                      {farm.crop_history.length > 0 ? (
                        <SequenceRail steps={farm.crop_history.map((event) => ({
                          key: event.crop.key,
                          name: event.crop.label,
                          detail: event.start_date && event.end_date
                            ? `${formatDay(event.start_date)} – ${formatDay(event.end_date)}`
                            : 'Dates need review',
                        }))} />
                      ) : (
                        <p className="alert alert-warning"><AlertIcon />Needs dated crop history</p>
                      )}
                    </div>

                    <div>
                      <p className="col-label">Climate data</p>
                      <div className="plot-climate">
                        <StatusPill status={climate?.status || 'pending'} />
                        <span>{climateSummary}</span>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          disabled={statusLoading !== null}
                          onClick={() => void refreshClimateStatus(farm.id)}
                        >
                          {statusLoading === farm.id ? 'Checking…' : 'Refresh'}
                        </button>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
