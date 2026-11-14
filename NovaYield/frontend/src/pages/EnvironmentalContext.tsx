import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  farmApi,
  type FarmEnvironmentalStatusResponse,
  type FarmResponse,
} from '../api/farms';
import ErrorState from '../components/common/ErrorState';
import LoadingState from '../components/common/LoadingState';
import EnvironmentalPanel from '../components/dss/EnvironmentalPanel';
import { formatDay } from '../components/dss/format';

export default function EnvironmentalContext() {
  const { farmId = '' } = useParams();
  const [farm, setFarm] = useState<FarmResponse | null>(null);
  const [environment, setEnvironment] = useState<FarmEnvironmentalStatusResponse | null>(null);
  const [loadedFarmId, setLoadedFarmId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadContext = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    try {
      const [farmResult, environmentResult] = await Promise.all([
        farmApi.getFarm(farmId),
        farmApi.getEnvironment(farmId),
      ]);
      setFarm(farmResult);
      setEnvironment(environmentResult);
      setError(null);
      setLoadedFarmId(farmId);
    } catch (cause) {
      setLoadedFarmId(farmId);
      setError(cause instanceof Error ? cause.message : 'Could not load environmental context.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [farmId]);

  useEffect(() => {
    void Promise.resolve().then(() => loadContext());
  }, [loadContext]);

  if (loading || loadedFarmId !== farmId) return <LoadingState message="Loading stored environmental context…" />;
  if (error || !farm) return <ErrorState message={error || 'This plot could not be found.'} onRetry={() => { setLoading(true); void loadContext(); }} />;

  const encodedFarmId = encodeURIComponent(farm.id);

  return (
    <div className="page-container comparison-page environment-page">
      <header className="page-heading-row">
        <div>
          <Link className="back-link" to={`/plots/${encodedFarmId}`}>← {farm.name}</Link>
          <p className="kicker">Environmental context</p>
          <h1>Stored climate for {farm.name}</h1>
          <p className="lede">Review historical NASA POWER conditions aligned to the actual crop-history dates recorded for this plot.</p>
        </div>
        <button className="secondary-btn" type="button" disabled={refreshing} onClick={() => void loadContext(true)}>
          {refreshing ? 'Checking stored context…' : 'Refresh status'}
        </button>
      </header>

      <div className="environment-plot-summary">
        <span><b>Location</b> {farm.location.label}</span>
        <span><b>History windows</b> {farm.crop_history.length} reported crop event{farm.crop_history.length === 1 ? '' : 's'}</span>
        {environment?.data_through && <span><b>Stored through</b> {formatDay(environment.data_through)}</span>}
      </div>

      <EnvironmentalPanel status={environment} analysis={environment?.analysis || null} />

      <section className="context-next-step">
        <div>
          <p className="kicker">Next step</p>
          <h2>Review this plot’s recommendations</h2>
          <p>The recommendation page uses available stored context and shows which weather adjustment, if any, was applied.</p>
        </div>
        <Link className="submit-btn" to={`/plots/${encodedFarmId}/recommendations`}>Open recommendations</Link>
      </section>
    </div>
  );
}
