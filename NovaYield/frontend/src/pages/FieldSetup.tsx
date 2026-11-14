import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  farmApi,
  type CropOption,
  type FarmCreateInput,
  type FarmReferenceOptionsResponse,
  type FarmResponse,
  type FarmerPriority,
  type LabourCapacity,
  type RiceSystem,
  type SupportedLocationsResponse,
} from '../api/farms';
import ErrorState from '../components/common/ErrorState';
import LoadingState from '../components/common/LoadingState';
import { AlertIcon, ArrowLeftIcon, PlusIcon } from '../components/icons';

interface CropEventRow {
  id: number;
  cropKey: string;
  startDate: string;
  endDate: string;
  riceSystem: RiceSystem | '';
}

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function FieldSetup() {
  const { farmId } = useParams();
  const navigate = useNavigate();
  const nextRowId = useRef(2);
  const [locations, setLocations] = useState<SupportedLocationsResponse | null>(null);
  const [references, setReferences] = useState<FarmReferenceOptionsResponse | null>(null);
  const [crops, setCrops] = useState<CropOption[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [locationKey, setLocationKey] = useState('');
  const [soilKey, setSoilKey] = useState('');
  const [irrigationKey, setIrrigationKey] = useState('');
  const [labourCapacity, setLabourCapacity] = useState<LabourCapacity | ''>('');
  const [farmerPriority, setFarmerPriority] = useState<FarmerPriority | ''>('');
  const [availableFrom, setAvailableFrom] = useState('');
  const [historyRows, setHistoryRows] = useState<CropEventRow[]>([
    { id: 1, cropKey: '', startDate: '', endDate: '', riceSystem: '' },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [editingFarm, setEditingFarm] = useState<FarmResponse | null>(null);
  const [farmLoading, setFarmLoading] = useState(Boolean(farmId));
  const [loadedFarmId, setLoadedFarmId] = useState<string | null>(null);
  const [farmError, setFarmError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([farmApi.listLocations(), farmApi.listReferences(), farmApi.listCrops()])
      .then(([locationResult, referenceResult, cropResult]) => {
        if (!active) return;
        setLocations(locationResult);
        setReferences(referenceResult);
        setCrops(cropResult.crops.filter((crop) => crop.history_selectable));
      })
      .catch((cause: unknown) => {
        if (active) setCatalogError(cause instanceof Error ? cause.message : 'Could not load setup choices.');
      })
      .finally(() => { if (active) setCatalogLoading(false); });

    if (farmId) {
      farmApi.getFarm(farmId)
        .then((farm) => {
          if (!active) return;
          setFarmError(null);
          setLoadedFarmId(farmId);
          const rows = farm.crop_history.length
            ? farm.crop_history.map((event, index) => ({
              id: index + 1,
              cropKey: event.crop.key,
              startDate: event.start_date || '',
              endDate: event.end_date || '',
              riceSystem: (event.production_system_key || '') as RiceSystem | '',
            }))
            : [{ id: 1, cropKey: '', startDate: '', endDate: '', riceSystem: '' as const }];
          setEditingFarm(farm);
          setName(farm.name);
          setLocationKey(farm.location.location_key || farm.location.key || '');
          setSoilKey(farm.soil_texture?.key || '');
          setIrrigationKey(farm.irrigation_access?.key || '');
          setLabourCapacity(farm.labour_capacity || '');
          setFarmerPriority(farm.farmer_priority || '');
          setAvailableFrom(farm.available_from || '');
          setHistoryRows(rows);
          setSubmitError(null);
          nextRowId.current = rows.length + 1;
        })
        .catch((cause: unknown) => {
          if (active) {
            setFarmError(cause instanceof Error ? cause.message : 'Could not load this plot for editing.');
            setLoadedFarmId(farmId);
          }
        })
        .finally(() => { if (active) setFarmLoading(false); });
    }
    return () => { active = false; };
  }, [farmId]);

  const updateRow = (id: number, change: Partial<CropEventRow>) => {
    setHistoryRows((rows) => rows.map((row) => row.id === id
      ? { ...row, ...change, riceSystem: change.cropKey && change.cropKey !== 'rice' ? '' : change.riceSystem ?? row.riceSystem }
      : row));
  };

  const validate = (): string | null => {
    if (!name.trim() || !locationKey || !soilKey || !irrigationKey || !labourCapacity) {
      return 'Enter a plot name and choose its location, soil texture, irrigation access, and labour capacity.';
    }
    if (historyRows.length < 1 || historyRows.length > 3) return 'Enter one to three past crop events.';
    for (const [index, row] of historyRows.entries()) {
      if (!row.cropKey || !row.startDate || !row.endDate) return 'Choose a crop and enter its actual planting and harvest dates.';
      if (row.endDate < row.startDate) return 'A harvest or removal date cannot be before its planting date.';
      if (row.startDate > todayUtc() || row.endDate > todayUtc()) return 'Historical crop dates cannot be in the future.';
      if (index > 0 && row.startDate <= historyRows[index - 1].endDate) {
        return 'Crop events must be oldest first and cannot overlap on a single plot.';
      }
    }
    const lastHarvest = historyRows.at(-1)?.endDate;
    if (availableFrom && lastHarvest && availableFrom < lastHarvest) {
      return 'The plot cannot be available before its last reported harvest.';
    }
    return null;
  };

  const buildPayload = (): FarmCreateInput => ({
    name: name.trim(),
    location_key: locationKey,
    soil_texture_key: soilKey,
    irrigation_access_key: irrigationKey,
    history_status: 'complete',
    labour_capacity: labourCapacity as LabourCapacity,
    available_from: availableFrom || null,
    farmer_priority: farmerPriority || null,
    crop_history: historyRows.map((row, index) => ({
      crop_key: row.cropKey,
      sequence_order: index + 1,
      start_date: row.startDate,
      end_date: row.endDate,
      ...(row.cropKey === 'rice' ? { production_system_key: row.riceSystem || 'unknown' } : {}),
    })),
  });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    const validationError = validate();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }
    setSubmitting(true);
    try {
      const payload = buildPayload();
      const farm = editingFarm
        ? await farmApi.updateFarm(editingFarm.id, payload)
        : await farmApi.createFarm(payload);
      navigate(`/plots/${encodeURIComponent(farm.id)}`);
    } catch (cause) {
      setSubmitError(cause instanceof Error ? cause.message : 'Could not save this plot.');
    } finally {
      setSubmitting(false);
    }
  };

  if (catalogLoading || farmLoading || (farmId && loadedFarmId !== farmId)) return <LoadingState message="Loading plot setup…" />;
  if (farmError) {
    return <ErrorState title="Could not open this plot" message={farmError} />;
  }

  const backTo = editingFarm ? `/plots/${encodeURIComponent(editingFarm.id)}` : '/plots';
  const selectedSoil = references?.soil_textures.find((option) => option.key === soilKey);
  const selectedIrrigation = references?.irrigation_access.find((option) => option.key === irrigationKey);

  return (
    <div className="page page-narrow">
      <header className="page-header">
        <div className="page-head-main">
          <Link className="back-link btn btn-ghost btn-sm" to={backTo}>
            <ArrowLeftIcon />{editingFarm ? editingFarm.name : 'My plots'}
          </Link>
          <h1 id="setup-heading">{editingFarm ? `Edit ${editingFarm.name}` : 'Add a plot'}</h1>
          <p className="page-desc">Describe one plot and the crops you have grown on it. NovaYield resolves the location to a private reference point and never shows coordinates.</p>
        </div>
      </header>

      {catalogError && <p className="alert alert-error" role="alert"><AlertIcon />{catalogError}</p>}
      {!catalogError && locations && references && (
        <form onSubmit={handleSubmit} aria-labelledby="setup-heading" className="panel">
          <div className="panel-body">
            {editingFarm?.history_status === 'legacy_unresolved' && (
              <p className="alert alert-warning mb-6">
                <AlertIcon />
                This older profile contains crop text without dates. Re-enter only the crop events and dates you know; NovaYield has not inferred any of them.
              </p>
            )}

            <fieldset className="form-section">
              <div className="form-section-head">
                <h2>Plot</h2>
                <p>{locations.coverage_notice} NASA climate represents a regional grid cell, not a sensor on this plot.</p>
              </div>
              <div className="form-grid">
                <div className="field">
                  <label className="label" htmlFor="plot-name">Plot name</label>
                  <input id="plot-name" className="input" required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="North plot" />
                </div>
                <div className="field">
                  <label className="label" htmlFor="location">Location</label>
                  <select id="location" className="select" required value={locationKey} onChange={(event) => setLocationKey(event.target.value)}>
                    <option value="">Choose a location</option>
                    {locations.locations.map((item) => <option key={item.location_key} value={item.location_key}>{item.label}</option>)}
                  </select>
                </div>
              </div>
            </fieldset>

            <fieldset className="form-section">
              <div className="form-section-head">
                <h2>Conditions and capacity</h2>
                <p>These are recorded as context. Soil and irrigation are not measurements and do not change the score on their own.</p>
              </div>
              <div className="form-grid">
                <div className="field">
                  <label className="label" htmlFor="soil">Soil texture</label>
                  <select id="soil" className="select" required value={soilKey} onChange={(event) => setSoilKey(event.target.value)}>
                    <option value="">Choose an option</option>
                    {references.soil_textures.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                  {selectedSoil?.definition && <span className="hint">{selectedSoil.definition}</span>}
                </div>
                <div className="field">
                  <label className="label" htmlFor="irrigation">Irrigation access</label>
                  <select id="irrigation" className="select" required value={irrigationKey} onChange={(event) => setIrrigationKey(event.target.value)}>
                    <option value="">Choose an option</option>
                    {references.irrigation_access.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                  <span className="hint">{selectedIrrigation?.definition || 'Access does not show how much water reaches a crop.'}</span>
                </div>
                <div className="field">
                  <label className="label" htmlFor="labour">Labour capacity</label>
                  <select id="labour" className="select" required value={labourCapacity} onChange={(event) => setLabourCapacity(event.target.value as LabourCapacity | '')}>
                    <option value="">Choose a capacity</option>
                    {references.labour_capacity.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label className="label" htmlFor="priority">Main priority <span className="opt">(optional)</span></label>
                  <select id="priority" className="select" value={farmerPriority} onChange={(event) => setFarmerPriority(event.target.value as FarmerPriority | '')}>
                    <option value="">No additional priority</option>
                    {references.farmer_priorities.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                  <span className="hint">Shifts the relative emphasis. It cannot override crop, labour, or calendar constraints.</span>
                </div>
                <div className="field">
                  <label className="label" htmlFor="available-from">Available from <span className="opt">(optional)</span></label>
                  <input id="available-from" className="input" type="date" min={historyRows.at(-1)?.endDate || undefined} value={availableFrom} onChange={(event) => setAvailableFrom(event.target.value)} />
                  <span className="hint">Leave blank to start from the later of today and your latest reported harvest.</span>
                </div>
              </div>
            </fieldset>

            <fieldset className="form-section" aria-labelledby="history-heading">
              <div className="form-section-head">
                <h2 id="history-heading">Crop history</h2>
                <p>Enter one to three events, oldest first. Gaps are fine and mean the plot sat idle. Overlapping events are not supported.</p>
              </div>
              {historyRows.map((row, index) => (
                <div key={row.id} className="repeat-item">
                  <div className="repeat-head">
                    <h3>Event {index + 1}</h3>
                    {historyRows.length > 1 && (
                      <button type="button" className="btn btn-danger-ghost btn-sm" onClick={() => setHistoryRows((rows) => rows.filter((item) => item.id !== row.id))}>Remove</button>
                    )}
                  </div>
                  <div className="repeat-grid">
                    <div className="field">
                      <label className="label" htmlFor={`crop-${row.id}`}>Crop</label>
                      <select id={`crop-${row.id}`} className="select" required value={row.cropKey} onChange={(event) => updateRow(row.id, { cropKey: event.target.value, riceSystem: '' })}>
                        <option value="">Choose a crop</option>
                        {crops.map((crop) => <option key={crop.id} value={crop.crop_key}>{crop.common_name}</option>)}
                      </select>
                    </div>
                    {row.cropKey === 'rice' && (
                      <div className="field">
                        <label className="label" htmlFor={`rice-system-${row.id}`}>Rice production system</label>
                        <select id={`rice-system-${row.id}`} className="select" value={row.riceSystem} onChange={(event) => updateRow(row.id, { riceSystem: event.target.value as RiceSystem | '' })}>
                          <option value="">Choose a system</option>
                          {references.rice_production_systems.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                        </select>
                        <span className="hint">Unknown stays unknown. Irrigation access does not imply a system.</span>
                      </div>
                    )}
                    <div className="field">
                      <label className="label" htmlFor={`start-${row.id}`}>Planted</label>
                      <input id={`start-${row.id}`} className="input" type="date" required max={todayUtc()} value={row.startDate} onChange={(event) => updateRow(row.id, { startDate: event.target.value })} />
                    </div>
                    <div className="field">
                      <label className="label" htmlFor={`end-${row.id}`}>Harvested or removed</label>
                      <input id={`end-${row.id}`} className="input" type="date" required max={todayUtc()} value={row.endDate} onChange={(event) => updateRow(row.id, { endDate: event.target.value })} />
                    </div>
                  </div>
                </div>
              ))}
              {historyRows.length < 3 && (
                <div>
                  <button type="button" className="btn btn-secondary" onClick={() => setHistoryRows((rows) => [...rows, { id: nextRowId.current++, cropKey: '', startDate: '', endDate: '', riceSystem: '' }])}>
                    <PlusIcon />Add another event
                  </button>
                </div>
              )}
            </fieldset>

            {submitError && <p className="alert alert-error mt-6" role="alert"><AlertIcon />{submitError}</p>}

            <div className="form-actions">
              <Link className="btn btn-secondary" to={backTo}>Cancel</Link>
              <button type="submit" disabled={submitting} className="btn btn-primary">
                {submitting ? 'Saving…' : editingFarm ? 'Save changes' : 'Save plot'}
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
