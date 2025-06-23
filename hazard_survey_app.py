# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import geopandas as gpd
import os, shutil, zipfile, re, smtplib
from datetime import datetime, date
from shapely.geometry import Point
from streamlit_folium import st_folium
from email.message import EmailMessage
from dotenv import load_dotenv
import folium
from docx import Document
from fpdf import FPDF

# --- Load environment variables ---
load_dotenv()
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# --- File paths ---
EXCEL_PATH = "RiskAssessmentTool.xlsm"
GEOJSON_PATH = "KZN_wards.geojson"
BASE_DIR = "C:/tmp/kzn"
TODAY_FOLDER = datetime.now().strftime("%d_%b_%Y")
SAVE_DIR = os.path.join(BASE_DIR, TODAY_FOLDER)
os.makedirs(SAVE_DIR, exist_ok=True)

# --- Cleanup old folders ---
def cleanup_old_folders(base_dir, days=30):
    now = datetime.now()
    pattern = re.compile(r"\d{2}_[A-Za-z]{3}_\d{4}")
    for folder in os.listdir(base_dir):
        path = os.path.join(base_dir, folder)
        if os.path.isdir(path) and pattern.fullmatch(folder):
            try:
                if (now - datetime.strptime(folder, "%d_%b_%Y")).days > days:
                    shutil.rmtree(path)
            except:
                continue
cleanup_old_folders(BASE_DIR)

# --- Load data ---
@st.cache_data
def load_hazards():
    df = pd.ExcelFile(EXCEL_PATH).parse("Hazard information")
    return df.iloc[1:, 0].dropna().tolist()

@st.cache_data
def load_ward_gdf():
    return gpd.read_file(GEOJSON_PATH).to_crs(epsg=4326)

hazards = load_hazards()
gdf = load_ward_gdf()

# --- App layout ---
st.set_page_config(page_title="KZN Hazard Risk Assessment", layout="wide")
st.image("Logo.png", width=240)
st.image("SRK_Logo.png", width=200)
st.title("KZN Hazard Risk Assessment Survey")

# --- Interactive Map ---
st.subheader("Select a Ward from the Map")
m = folium.Map(location=[-29.5, 31.1], zoom_start=7)
folium.GeoJson(
    data=gdf.__geo_interface__,
    name="Wards",
    tooltip=folium.GeoJsonTooltip(fields=gdf.columns[:1].tolist()),
    popup=folium.GeoJsonPopup(fields=gdf.columns[:1].tolist()),
    highlight_function=lambda x: {"fillColor": "#ffaf00", "color": "black", "weight": 2},
).add_to(m)

map_data = st_folium(m, height=500)

clicked_ward = None
if "last_active_drawing" in map_data and map_data["last_active_drawing"]:
    props = map_data["last_active_drawing"].get("properties", {})
    clicked_ward = props.get(gdf.columns[0])
elif "last_clicked" in map_data and map_data["last_clicked"]:
    lng = map_data["last_clicked"]["lng"]
    lat = map_data["last_clicked"]["lat"]
    pt = Point(lng, lat)
    for _, row in gdf.iterrows():
        if row.geometry.contains(pt):
            clicked_ward = row[gdf.columns[0]]
            break

if clicked_ward:
    st.success(f"Selected Ward: {clicked_ward}")

# --- Hazard Selection ---
st.markdown("<hr>", unsafe_allow_html=True)
st.subheader("Select Applicable Hazards")
selected = st.multiselect("Choose hazards:", hazards)
include_other = st.checkbox("Add a custom hazard (Other)")
custom = st.text_input("Specify other hazard:") if include_other else ""

submitted = False
if selected or custom:
    with st.form("hazard_form"):
        st.subheader("Respondent Information")
        name = st.text_input("Full Name")
        final_ward = clicked_ward or st.text_input("Ward (if not using map)")
        today = st.date_input("Date", value=date.today())
        user_email = st.text_input("Your Email")

        st.subheader("Hazard Risk Evaluation")
        levels = ["0 - Not applicable", "1 - Low", "2 - Moderate", "3 - High", "4 - Severe"]
        hazards_to_ask = selected + ([custom] if custom else [])
        responses = []
        for hazard in hazards_to_ask:
            st.markdown(f"**{hazard}**")
            responses.append({
                "Name": name,
                "Ward": final_ward,
                "Date": today,
                "Hazard": hazard,
                "Likelihood": st.selectbox("Likelihood:", levels, key=f"{hazard}_like"),
                "Impact": st.selectbox("Impact:", levels, key=f"{hazard}_impact"),
                "Disruption": st.selectbox("Disruption:", levels, key=f"{hazard}_disrupt")
            })

        submitted = st.form_submit_button("Submit Survey")

# --- File generation & email ---
if submitted:
    df = pd.DataFrame(responses)
    base = f"{final_ward}_{today}"
    paths = {
        "csv": os.path.join(SAVE_DIR, f"{base}_responses.csv"),
        "excel": os.path.join(SAVE_DIR, f"{base}_responses.xlsx"),
        "word": os.path.join(SAVE_DIR, f"{base}_responses.docx"),
        "pdf": os.path.join(SAVE_DIR, f"{base}_responses.pdf"),
        "zip": os.path.join(SAVE_DIR, f"{base}_hazard_survey.zip")
    }

    df.to_csv(paths["csv"], index=False)
    df.to_excel(paths["excel"], index=False)

    doc = Document()
    doc.add_heading(f"Hazard Risk Assessment for {final_ward}", 0)
    for _, row in df.iterrows():
        doc.add_paragraph(
            f"Hazard: {row['Hazard']}\n"
            f"Likelihood: {row['Likelihood']}\n"
            f"Impact: {row['Impact']}\n"
            f"Disruption: {row['Disruption']}"
        )
    doc.save(paths["word"])

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Hazard Risk Assessment for {final_ward}", ln=True)
    for _, row in df.iterrows():
        text = (
            f"Hazard: {row['Hazard']}\n"
            f"Likelihood: {row['Likelihood']}\n"
            f"Impact: {row['Impact']}\n"
            f"Disruption: {row['Disruption']}\n"
        )
        pdf.multi_cell(0, 10, txt=text)
    pdf.output(paths["pdf"])

    with zipfile.ZipFile(paths["zip"], "w") as zipf:
        for file_key in ["csv", "excel", "word", "pdf"]:
            zipf.write(paths[file_key], arcname=os.path.basename(paths[file_key]))

    def send_email(recipient, files, name, ward, today):
        try:
            msg = EmailMessage()
            msg["Subject"] = "KZN Hazard Survey Submission"
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = ", ".join([recipient, "dingaanm@gmail.com"])
            msg.set_content("Attached are your hazard survey results.")

            msg.add_alternative(f"""
    <html>
    <body>
        <p>Dear {name},</p>
        <p>Thank you for completing the hazard risk assessment survey for ward: <strong>{ward}</strong>, submitted on <strong>{today}</strong>.</p>
        <p><strong>Summary of files attached:</strong></p>
        <ul>
        {''.join(f"<li>{os.path.basename(f)}</li>" for f in files)}
        </ul>
        <p>Regards,<br>Disaster Risk Survey System</p>
    </body>
    </html>
    """, subtype='html')

            for file in files:
                with open(file, 'rb') as f:
                    msg.add_attachment(
                        f.read(),
                        maintype='application',
                        subtype='octet-stream',
                        filename=os.path.basename(file)
                    )

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)

        except Exception as e:
            st.error(f"Email failed: {e}")

    send_email(user_email, [paths[k] for k in ["csv", "excel", "word", "pdf"]], name, final_ward, today)
    st.success("Submission completed and email sent.")
