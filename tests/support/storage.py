"""Decode persisted index bins for existing behavioral assertions."""
def stored_bins(record):
    if 'respiratoryBins' in record:
        return record['respiratoryBins']
    groups=record['binningData']['bins']
    if isinstance(groups,dict):
        groups=groups['inhale']+groups['exhale']
    points=record['filtered']
    rows=[]
    for group, intervals in enumerate(groups):
        for start,end in intervals:
            assert type(start) is int and type(end) is int and 0 <= start < end <= len(points)
            rows.append(dict(start=points[start][0],end=points[end][0] if end<len(points) else record['endSeq'],
                direction='inhale' if group<len(groups)//2 else 'exhale',bin=group%(len(groups)//2)+1))
    return sorted(rows,key=lambda row:row['start'])
