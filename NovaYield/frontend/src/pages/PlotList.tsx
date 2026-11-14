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
    <div className="page-container field-page">
      <header className="page-heading-row">
        <div>
          <p className="kicker">Workspace</p>
          <h1>My plots</h1>
          <p className="lede">Open a plot to review its profile, historical climate context, and rotation recommendations.</p>
        </div>
        <Link className="submit-btn" to="/plots/new">Add a plot</Link>
      </header>

      {farms.length === 0 ? (
        <section className="empty-state plot-empty-state">
          <h2>No plots yet</h2>
          <p>Add a decision plot and enter the crop events you know. NovaYield will keep each plot and its recommendations together.</p>
          <Link className="submit-btn" to="/plots/new">Set up your first plot</Link>
        </section>
      ) : (
        <section className="saved-farms" aria-labelledby="saved-farms-heading">
          <div className="section-heading">
            <div>
              <p className="kicker">Farm workspace</p>
              <h2 id="saved-farms-heading">Saved plots</h2>
            </div>
            <span className="meta-chip">{farms.length} plot{farms.length === 1 ? '' : 's'}</span>
          </div>

          <ul className="plot-list">
            {farms.map((farm) => {
              const climate = climateStatuses[farm.id];
              const climateSummary = climate?.data_through
                ? `Stored regional climate through ${formatDay(climate.data_through)}${climate.spatial_resolution ? ` · ${climate.spatial_resolution}` : ''}`
                : climate?.safe_message || 'Climate archive status has not been checked yet.';

              return (
                <li key={farm.id} className="plot-card">
                  <div className="plot-card-top">
                    <div>
                      <p className="kicker">Decision plot</p>
                      <h3><Link to={`/plots/${encodeURIComponent(farm.id)}`}>{farm.name}</Link></h3>
                      <p>{farm.location.label}</p>
                    </div>
                    <StatusPill status={climate?.status || 'pending'} />
                  </div>

                  <div className="plot-summary-grid" aria-label="Plot details">
                    {farm.soil_texture && <span><small>Soil context</small><strong>{farm.soil_texture.label}</strong></span>}
                    {farm.irrigation_access && <span><small>Irrigation access</small><strong>{farm.irrigation_access.label}</strong></span>}
                    {farm.labour_capacity && <span><small>Labour capacity</small><strong>{farm.labour_capacity}</strong></span>}
                    <span><small>Priority</small><strong>{farm.farmer_priority ? label(farm.farmer_priority) : 'No preference'}</strong></span>
                  </div>

                  {farm.crop_history.length > 0 ? (
                    <div className="plot-history-preview">
                      <div className="history-preview-heading">
                        <strong>Reported crop history</strong>
                        <span>{farm.crop_history.length} dated event{farm.crop_history.length === 1 ? '' : 's'}</span>
                      </div>
                      <SequenceRail steps={farm.crop_history.map((event) => ({
                        key: event.crop.key,
                        name: event.crop.label,
                        detail: event.start_date && event.end_date
                          ? `${formatDay(event.start_date)} – ${formatDay(event.end_date)}`
                          : 'Dates need review',
                      }))} />
                    </div>
                  ) : (
                    <p className="alert alert-warning plot-warning">This plot needs dated crop history before it can be used for a new recommendation.</p>
                  )}

                  <div className="plot-climate-status">
                    <div>
                      <strong>Environmental context</strong>
                      <p>{climateSummary}</p>
                    </div>
                    <button
                      type="button"
                      className="text-btn"
                      disabled={statusLoading !== null}
                      onClick={() => void refreshClimateStatus(farm.id)}
                    >
                      {statusLoading === farm.id ? 'Checking…' : 'Refresh status'}
                    </button>
                  </div>

                  <div className="saved-farm-actions">
                    <Link className="secondary-btn" to={`/plots/${encodeURIComponent(farm.id)}`}>View plot</Link>
                    <Link className="submit-btn" to={`/plots/${encodeURIComponent(farm.id)}/recommendations`}>Open recommendations</Link>
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
