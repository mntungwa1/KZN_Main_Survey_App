# hazard_app.spec
from PyInstaller.utils.hooks import collect_all

# Collect Streamlit and Folium
streamlit_data, streamlit_bin, streamlit_hidden = collect_all('streamlit')
folium_data, folium_bin, folium_hidden = collect_all('folium')

a = Analysis(
    ['launch.py'],
    pathex=[],
    binaries=streamlit_bin + folium_bin,
    datas=[
        ('hazard_survey_app.py', '.'), 
        ('Logo.png', '.'), 
        ('SRK_Logo.png', '.'), 
        ('KZN_wards.geojson', '.'), 
        ('RiskAssessmentTool.xlsm', '.'), 
        ('.env', '.'),
        *streamlit_data,
        *folium_data
    ],
    hiddenimports=[
        *streamlit_hidden,
        *folium_hidden,
        'pandas', 'geopandas', 'shapely', 'docx', 'fpdf',
        'dotenv', 'streamlit_folium'
    ],
    noarchive=False
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='launch',
    console=True
)
