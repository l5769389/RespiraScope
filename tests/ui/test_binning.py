import pytest


SOURCE = {'filtered': [[0,0],[10,1],[20,4],[30,9],[40,16],[50,25],[60,20],[70,15],[80,10],[90,5],[100,0]],
          'valleys': [[0,0],[100,0]], 'peaks': [[50,25]]}


def compute(page, ui_server, options, source=SOURCE):
    page.goto(ui_server['ui'] + '/monitor/')
    return page.evaluate('''async ({source,options}) => {
      const {buildRespiratoryBins} = await import('./modules/respiratory-bins.js');
      return buildRespiratoryBins(source, options);
    }''', {'source': source, 'options': options})


def test_time_bins_both_directions(page, ui_server):
    bins = compute(page, ui_server, {'basis':'time'})
    assert [b['bin'] for b in bins] == [1,2,3,4,5,1,2,3,4,5]
    assert [b['end'] for b in bins[:5]] == [10,20,30,40,50]
    assert bins[5]['direction'] == 'exhale'


def test_free_amplitude_uses_crossings(page, ui_server):
    bins = compute(page, ui_server, {'basis':'amplitude','amplitudeMode':'free'})
    assert len(bins) == 10
    assert bins[0]['end'] == 22
    assert bins[5]['end'] == 60


def test_fixed_amplitude_excludes_outside_values(page, ui_server):
    bins = compute(page, ui_server, {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':20})
    assert len(bins) == 10
    assert bins[0]['start'] == 22
    assert bins[4]['end'] == pytest.approx(40+40/9)
    assert bins[5]['start'] == 60
    assert bins[9]['end'] == 90


def test_shallow_breath_only_occupies_reached_bins(page, ui_server):
    bins = compute(page, ui_server, {'basis':'amplitude','amplitudeMode':'fixed','lower':0,'upper':100})
    assert [(b['direction'],b['bin']) for b in bins] == [('inhale',1),('inhale',2),('exhale',4),('exhale',5)]


def test_gaps_and_unbounded_tails_remain_unassigned(page, ui_server):
    source = {**SOURCE,'filtered':[p for p in SOURCE['filtered'] if p[0]<20 or p[0]>60]}
    assert compute(page,ui_server,{'basis':'time','gap':25},source) == []
    assert compute(page,ui_server,{'basis':'time'},{**SOURCE,'peaks':[],'valleys':[]}) == []


def test_invalid_fixed_bounds_and_reversed_sensor(page, ui_server):
    assert compute(page,ui_server,{'basis':'amplitude','amplitudeMode':'fixed','lower':20,'upper':5}) == []
    assert compute(page,ui_server,{'basis':'time','inhaleRising':False})[0]['direction'] == 'exhale'


def test_unequal_durations_still_have_five_bins_each(page,ui_server):
    source = {'filtered':[[0,0],[50,100],[150,0]],'peaks':[[50,100]],'valleys':[[0,0],[150,0]]}
    bins=compute(page,ui_server,{'basis':'time','gap':200},source)
    assert [b['end']-b['start'] for b in bins] == [10,10,10,10,10,20,20,20,20,20]


def test_free_amplitude_rescales_each_breath(page,ui_server):
    source={'filtered':[[0,0],[50,100],[100,0],[150,20],[200,0]],'peaks':[[50,100],[150,20]],'valleys':[[0,0],[100,0],[200,0]]}
    bins=compute(page,ui_server,{'basis':'amplitude','amplitudeMode':'free','gap':100},source)
    assert len(bins) == 20
    assert [b['end'] for b in bins[10:15]] == [110,120,130,140,150]


def test_fixed_bin_export_contains_empty_bands_and_extremum_flags(page, ui_server):
    page.goto(ui_server['ui']+'/monitor/')
    result=page.evaluate("""async source=>{
      const {buildRespiratoryBins,buildBinningMetadata,extremumRange}=await import('./modules/respiratory-bins.js');
      const options={basis:'amplitude',amplitudeMode:'fixed',lower:0,upper:100};
      return {metadata:buildBinningMetadata(options,buildRespiratoryBins(source,options)),
        flags:[-1,0,25,100,101].map(value=>extremumRange(value,options))};
    }""", SOURCE)
    metadata=result['metadata']
    assert metadata['amplitudeEdges']==list(range(0,101,20))
    assert metadata['amplitudeBounds']=={'lower':0,'upper':100}
    assert len(metadata['groups'])==10
    assert [g['amplitudeBand'] for g in metadata['groups'] if g['direction']=='inhale' and g['intervals']]==[1,2]
    assert all(not g['intervals'] for g in metadata['groups'] if g['amplitudeBand']>=3)
    assert result['flags']==['below','inside','inside','inside','above']


@pytest.mark.parametrize('options', [
    {'basis':'time'},
    {'basis':'amplitude','amplitudeMode':'free'},
    {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':20},
    {'basis':'amplitude','amplitudeMode':'fixed','lower':0,'upper':100},
    {'basis':'amplitude','amplitudeMode':'fixed','lower':5,'upper':20,'inhaleRising':False},
])
def test_frontend_and_backend_export_identical_bins(page, ui_server, options):
    from ct_breath.breath_process.record_manager import RecordManager
    from ct_breath.http.schemas import FilterConfig
    manager = RecordManager()
    manager.record_start_sequence, manager.record_end_sequence = 0,100
    payload = manager.build_record_data(FilterConfig(), filtered_data=SOURCE['filtered'],
        peak_data=SOURCE['peaks'], valley_data=SOURCE['valleys'], analysis=options)
    assert compute(page, ui_server, options) == payload['respiratoryBins']
