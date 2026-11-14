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
import { RefreshIcon } from '../components/icons';
import PlotTabs from '../components/PlotTabs';

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

  if (loading || loadedFarmId !== farmId) return <LoadingState message="Loading stored climate…" />;
  if (error || !farm) return <ErrorState message={error || 'This plot could not be found.'} onRetry={() => { setLoading(true); void loadContext(); }} />;

  const encodedFarmId = encodeURIComponent(farm.id);

  return (
    <div className="page">
      <header className="page-header with-tabs">
        <div className="page-head-main">
          <h1>{farm.name}</h1>
          <ul className="meta-list">
            <li>{farm.location.label}</li>
            <li><b>{farm.crop_history.length}</b> crop event{farm.crop_history.length === 1 ? '' : 's'} analysed</li>
            {environment?.data_through && <li>Stored through <b>{formatDay(environment.data_through)}</b></li>}
          </ul>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" type="button" disabled={refreshing} onClick={() => void loadContext(true)}>
            <RefreshIcon />{refreshing ? 'Checking…' : 'Refresh status'}
          </button>
          <Link className="btn btn-primary" to={`/plots/${encodedFarmId}/recommendations`}>View recommendations</Link>
        </div>
      </header>
      <PlotTabs farmId={farm.id} />

      <div className="page-body">
        <EnvironmentalPanel status={environment} analysis={environment?.analysis || null} />
      </div>
    </div>
  );
}
