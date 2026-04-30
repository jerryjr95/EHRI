def risk_band(score):
    if score < 2: return 'Safe'
    if score < 4: return 'Mild'
    if score < 6: return 'Moderate'
    if score < 8: return 'High'
    return 'Severe'

def advice(band):
    mapping = {
        'Safe':['Maintain healthy routine'],
        'Mild':['Hydrate','Monitor symptoms'],
        'Moderate':['Reduce outdoor exposure','Rest'],
        'High':['Consult clinician','Use mask outdoors'],
        'Severe':['Seek urgent medical care']
    }
    return mapping[band]