import streamlit as st
import pandas as pd

st.title("📧 Personalized Email Generator")

cohort_file = st.file_uploader("Upload user cohort CSV", type=["csv"])
event_file = st.file_uploader("Upload event log CSV", type=["csv"])

if cohort_file is not None:
    st.write("✅ Cohort file uploaded successfully!")
    df = pd.read_csv(cohort_file)
    st.dataframe(df.head())

if event_file is not None:
    st.write("✅ Event file uploaded successfully!")
    df2 = pd.read_csv(event_file)
    st.dataframe(df2.head())
