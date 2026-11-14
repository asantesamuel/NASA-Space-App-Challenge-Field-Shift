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

  if (catalogLoading || farmLoading || (farmId && loadedFarmId !== farmId)) return <div className="page-container"><p role="status">Loading plot setup…</p></div>;
  if (farmError) return <div className="page-container"><p className="alert alert-error" role="alert">{farmError}</p><Link to="/plots">Back to my plots</Link></div>;

  return (
    <div className="page-container field-page">
      <section className="form-card" aria-labelledby="setup-heading">
        <div className="form-header">
          <Link className="back-link" to={editingFarm ? `/plots/${encodeURIComponent(editingFarm.id)}` : '/plots'}>
            {editingFarm ? `← ${editingFarm.name}` : '← My plots'}
          </Link>
          <p className="kicker">{editingFarm ? 'Farm management' : 'Add a plot'}</p>
          <h1 id="setup-heading">{editingFarm ? `Edit ${editingFarm.name}` : 'Set up a plot'}</h1>
          <p>Enter one to three dated crop events for one decision plot. NovaYield uses the location key to resolve its private reference point; coordinates are not returned to the screen.</p>
        </div>

        {catalogError && <p className="alert alert-error" role="alert">{catalogError}</p>}
        {!catalogError && locations && references && (
          <form onSubmit={handleSubmit} className="form-grid">
                {editingFarm?.history_status === 'legacy_unresolved' && (
                  <p className="alert alert-warning form-span">This older profile contains crop text without dates. Re-enter only the crop events and dates you know; NovaYield has not inferred any of them.</p>
                )}
                <p className="alert alert-warning form-span">{locations.coverage_notice} Locations are supported place references. NASA climate represents a regional grid cell, not a sensor on this plot.</p>
                <div className="form-group">
                  <label htmlFor="plot-name">Plot name</label>
                  <input id="plot-name" className="form-input" required maxLength={120} value={name} onChange={(event) => setName(event.target.value)} placeholder="For example, North plot" />
                </div>
                <div className="form-group">
                  <label htmlFor="location">Supported location</label>
                  <select id="location" className="form-select" required value={locationKey} onChange={(event) => setLocationKey(event.target.value)}>
                    <option value="">Choose a location</option>
                    {locations.locations.map((item) => <option key={item.location_key} value={item.location_key}>{item.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="soil">Soil texture</label>
                  <select id="soil" className="form-select" required value={soilKey} onChange={(event) => setSoilKey(event.target.value)}>
                    <option value="">Choose an option</option>
                    {references.soil_textures.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                  {soilKey && <small>{references.soil_textures.find((option) => option.key === soilKey)?.definition}</small>}
                  <small>Soil texture is recorded as context; it is not a water-storage measurement or scoring input.</small>
                </div>
                <div className="form-group">
                  <label htmlFor="irrigation">Irrigation access</label>
                  <select id="irrigation" className="form-select" required value={irrigationKey} onChange={(event) => setIrrigationKey(event.target.value)}>
                    <option value="">Choose an option</option>
                    {references.irrigation_access.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                  {irrigationKey && <small>{references.irrigation_access.find((option) => option.key === irrigationKey)?.definition}</small>}
                  <small>Irrigation access does not reveal how much water reaches a crop.</small>
                </div>
                <div className="form-group">
                  <label htmlFor="labour">Available labour capacity</label>
                  <select id="labour" className="form-select" required value={labourCapacity} onChange={(event) => setLabourCapacity(event.target.value as LabourCapacity | '')}>
                    <option value="">Choose a capacity</option>
                    {references.labour_capacity.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label htmlFor="priority">One main priority (optional)</label>
                  <select id="priority" className="form-select" value={farmerPriority} onChange={(event) => setFarmerPriority(event.target.value as FarmerPriority | '')}>
                    <option value="">No additional priority</option>
                    {references.farmer_priorities.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                  </select>
                  <small>Selecting a priority changes relative emphasis; it cannot override crop, labour, or calendar constraints.</small>
                </div>
                <div className="form-group">
                  <label htmlFor="available-from">Earliest date this plot is available (optional)</label>
                  <input id="available-from" className="form-input" type="date" min={historyRows.at(-1)?.endDate || undefined} value={availableFrom} onChange={(event) => setAvailableFrom(event.target.value)} />
                  <small>If left blank, NovaYield starts scheduling from the later of today and your latest reported harvest.</small>
                </div>

                <section className="form-span form-section" aria-labelledby="history-heading">
                  <h2 id="history-heading">Past crop events</h2>
                  <p>Enter one to three events, oldest first. Gaps between events are allowed and mean the plot was idle for some period. Overlapping events are not supported by this MVP.</p>
                  {historyRows.map((row, index) => (
                    <div key={row.id} className="history-row">
                      <div className="history-row-heading">
                        <h3>Event {index + 1}</h3>
                        {historyRows.length > 1 && <button type="button" className="text-btn" onClick={() => setHistoryRows((rows) => rows.filter((item) => item.id !== row.id))}>Remove</button>}
                      </div>
                      <div className="history-row-grid">
                        <div className="form-group">
                          <label htmlFor={`crop-${row.id}`}>Crop</label>
                          <select id={`crop-${row.id}`} className="form-select" required value={row.cropKey} onChange={(event) => updateRow(row.id, { cropKey: event.target.value, riceSystem: '' })}>
                            <option value="">Choose a crop</option>
                            {crops.map((crop) => <option key={crop.id} value={crop.crop_key}>{crop.common_name}</option>)}
                          </select>
                        </div>
                        {row.cropKey === 'rice' && (
                          <div className="form-group">
                            <label htmlFor={`rice-system-${row.id}`}>Rice production system</label>
                            <select id={`rice-system-${row.id}`} className="form-select" value={row.riceSystem} onChange={(event) => updateRow(row.id, { riceSystem: event.target.value as RiceSystem | '' })}>
                              <option value="">Choose or select “I do not know”</option>
                              {references.rice_production_systems.map((option) => <option key={option.key} value={option.key}>{option.label}</option>)}
                            </select>
                            <small>Unknown stays unknown; irrigation access does not infer rice ecology.</small>
                          </div>
                        )}
                        <div className="form-group">
                          <label htmlFor={`start-${row.id}`}>Planting date</label>
                          <input id={`start-${row.id}`} className="form-input" type="date" required max={todayUtc()} value={row.startDate} onChange={(event) => updateRow(row.id, { startDate: event.target.value })} />
                        </div>
                        <div className="form-group">
                          <label htmlFor={`end-${row.id}`}>Harvest or removal date</label>
                          <input id={`end-${row.id}`} className="form-input" type="date" required max={todayUtc()} value={row.endDate} onChange={(event) => updateRow(row.id, { endDate: event.target.value })} />
                        </div>
                      </div>
                    </div>
                  ))}
                  {historyRows.length < 3 && <button type="button" className="secondary-btn" onClick={() => setHistoryRows((rows) => [...rows, { id: nextRowId.current++, cropKey: '', startDate: '', endDate: '', riceSystem: '' }])}>Add another event</button>}
                </section>

                {submitError && <p className="alert alert-error form-span" role="alert">{submitError}</p>}
                <div className="form-actions">
                  <button type="submit" disabled={submitting} className="submit-btn">{submitting ? 'Saving plot…' : editingFarm ? 'Save plot changes' : 'Save plot'}</button>
                  <Link className="secondary-btn" to={editingFarm ? `/plots/${encodeURIComponent(editingFarm.id)}` : '/plots'}>Cancel</Link>
                </div>
              </form>
        )}
      </section>
    </div>
  );
}
