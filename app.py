import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os
from scipy.interpolate import RegularGridInterpolator

# Set page configuration
st.set_page_config(page_title="Building Energy Analysis Tool", layout="wide")

@st.cache_data
def load_data(file_path):
    return pd.read_csv(file_path)

def main():
    st.title("Building Energy Comparison & Contour Plot")
    
    # 1. Sidebar: Sector Selection (Subfolders)
    st.sidebar.header("1. Sector Selection")
    sector = st.sidebar.radio("Select Building Sector", ["Commercial", "Residential"])
    
    # Define folder path based on selection
    folder_path = sector # Assuming folder names match these strings
    
    # 2. Sidebar: File Selection within Subfolder
    st.sidebar.header(f"2. {sector} Data Source")
    
    if not os.path.exists(folder_path):
        st.error(f"Folder '{folder_path}' not found. Please ensure it exists in your repository.")
        return

    if sector == "Commercial":
        # List all CSVs in the Commercial folder
        csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
        if not csv_files:
            st.error("No CSV files found in the 'Commercial' folder.")
            return
        selected_filename = st.sidebar.selectbox("Select CSV Data File", csv_files)
    else:
        # Residential logic: specifically look for results_static.csv
        selected_filename = "results_static.csv"
        if not os.path.exists(os.path.join(folder_path, selected_filename)):
            st.error(f"'{selected_filename}' not found in the 'Residential' folder.")
            return
        st.sidebar.info(f"Loading: {selected_filename}")

    # Full path to the file
    full_path = os.path.join(folder_path, selected_filename)
    df = load_data(full_path)

    # 3. Sidebar: Filtering & Settings
    st.sidebar.header("3. Analysis Settings")
    cz_list = sorted(df['Climate Zone'].unique())
    selected_cz = st.sidebar.selectbox("Select Climate Zone", cz_list)

    available_metrics = [col for col in ['TotalSource', 'CoolingSource', 'HeatingSource'] if col in df.columns]
    source_option = st.sidebar.radio("Select Metric", available_metrics)

    filtered_df = df[df['Climate Zone'] == selected_cz]

    try:
        # Prepare data
        pivot_df = filtered_df.pivot(index='U', columns='SHGC', values=source_option)
        pivot_df = pivot_df.sort_index().sort_index(axis=1)
        
        y_vals = pivot_df.index.values    
        x_vals = pivot_df.columns.values  
        z_vals = pivot_df.values          

        # 4. Sidebar: User Inputs for Comparison
        st.sidebar.header("4. Configuration Comparison")
        
        with st.sidebar.expander("Point 1 (Reference)", expanded=True):
            u1 = st.number_input("U-Value 1 [BTU/(hr·ft²·F)]", 
                                 min_value=float(y_vals.min()), max_value=float(y_vals.max()), 
                                 value=float(y_vals.mean()), step=0.01, key='u1')
            s1 = st.number_input("SHGC 1 [-]", 
                                 min_value=float(x_vals.min()), max_value=float(x_vals.max()), 
                                 value=float(x_vals.mean()), step=0.01, key='s1')

        with st.sidebar.expander("Point 2 (Comparison)", expanded=True):
            u2 = st.number_input("U-Value 2 [BTU/(hr·ft²·F)]", 
                                 min_value=float(y_vals.min()), max_value=float(y_vals.max()), 
                                 value=float(y_vals.min()), step=0.01, key='u2')
            s2 = st.number_input("SHGC 2 [-]", 
                                 min_value=float(x_vals.min()), max_value=float(x_vals.max()), 
                                 value=float(x_vals.min()), step=0.01, key='s2')

        # 2D Interpolation
        interp_func = RegularGridInterpolator((y_vals, x_vals), z_vals)
        val1 = float(interp_func([u1, s1])[0])
        val2 = float(interp_func([u2, s2])[0])
        pct_diff = ((val2 - val1) / val1) * 100 if val1 != 0 else 0

        # UI Results
        st.subheader(f"Results: {sector} | {selected_filename} | {selected_cz}")
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric(f"Point 1 {source_option}", f"{val1:.2f} MBTU")
        res_col2.metric(f"Point 2 {source_option}", f"{val2:.2f} MBTU")
        res_col3.metric("Difference", f"{pct_diff:.2f}%", delta=f"{pct_diff:.2f}%", delta_color="inverse")

        # Create Plotly Contour Plot
        fig = go.Figure()
        fig.add_trace(go.Contour(
            z=z_vals, x=x_vals, y=y_vals,
            colorscale='Viridis',
            colorbar=dict(title=f"{source_option} (MBTU)"),
            contours=dict(coloring='heatmap', showlabels=True, labelfont=dict(size=12, color='white')),
            hovertemplate = "<b>SHGC (-):</b> %{x}<br><b>U:</b> %{y}<br><b>Value:</b> %{z:.2f} MBTU<extra></extra>"
        ))

        # Markers
        fig.add_trace(go.Scatter(x=[s1], y=[u1], mode='markers+text', name='Point 1', text=["P1"], textposition="top center",
                                 marker=dict(color='white', size=12, symbol='circle', line=dict(width=2, color='black'))))
        fig.add_trace(go.Scatter(x=[s2], y=[u2], mode='markers+text', name='Point 2', text=["P2"], textposition="top center",
                                 marker=dict(color='red', size=12, symbol='x', line=dict(width=2, color='white'))))

        fig.update_layout(xaxis_title='SHGC [-]', yaxis_title='U-Value [BTU/(hr·ft²·F)]', width=900, height=700)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Analysis Error: {e}")

if __name__ == "__main__":
    main()
