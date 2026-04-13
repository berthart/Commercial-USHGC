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

def get_commercial_baseline(no_window_df, filename, climate_zone, metric):
    """Finds baseline from NoWindow.csv for Commercial files."""
    name_clean = filename.split('_')[0].lower()
    mapping = {
        "largeoffice": "OfficeLarge",
        "mediumoffice": "OfficeMedium",
        "smalloffice": "OfficeSmall",
        "primaryschool": "SchoolPrimary",
        "hotellarge": "HotelLarge",
        "hotelsmall": "HotelSmall"
    }
    prop_type = mapping.get(name_clean)
    if not prop_type:
        for pt in no_window_df['Property Type'].unique():
            if name_clean in pt.lower() or pt.lower() in name_clean:
                prop_type = pt
                break
    if prop_type:
        match = no_window_df[(no_window_df['Property Type'] == prop_type) & 
                             (no_window_df['Climate Zone'] == climate_zone)]
        if not match.empty:
            return match[metric].values[0]
    return None

def main():
    st.title("Building Energy Comparison & Contour Plot")
    
    # Load Commercial Baseline Data
    no_window_df = load_data('NoWindow.csv') if os.path.exists('NoWindow.csv') else None

    # 1. Sidebar: Sector Selection
    st.sidebar.header("1. Sector Selection")
    sector = st.sidebar.radio("Select Building Sector", ["Commercial", "Residential"])
    folder_path = sector 
    
    # 2. Sidebar: File Selection
    st.sidebar.header(f"2. {sector} Data Source")
    if not os.path.exists(folder_path):
        st.error(f"Folder '{folder_path}' not found.")
        return

    if sector == "Commercial":
        csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
        if not csv_files:
            st.error("No CSV files found in 'Commercial'.")
            return
        selected_filename = st.sidebar.selectbox("Select CSV Data File", csv_files)
    else:
        selected_filename = "results_static.csv"
        if not os.path.exists(os.path.join(folder_path, selected_filename)):
            st.error(f"'{selected_filename}' not found in 'Residential' folder.")
            return
        st.sidebar.info(f"Loading: {selected_filename}")

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
        # Prepare Grid Data
        pivot_df = filtered_df.pivot(index='U', columns='SHGC', values=source_option)
        pivot_df = pivot_df.sort_index().sort_index(axis=1)
        y_vals, x_vals, z_vals = pivot_df.index.values, pivot_df.columns.values, pivot_df.values          

        # Initialize Interpolator (Allowing extrapolation for SHGC=0 if data starts at 0.01)
        interp_func = RegularGridInterpolator((y_vals, x_vals), z_vals, bounds_error=False, fill_value=None)

        # 4. Sidebar: User Inputs
        st.sidebar.header("4. Configuration Comparison")
        u1 = st.sidebar.number_input("U-Value 1", min_value=float(y_vals.min()), max_value=float(y_vals.max()), value=float(y_vals.mean()), step=0.01, key='u1')
        s1 = st.sidebar.number_input("SHGC 1", min_value=float(x_vals.min()), max_value=float(x_vals.max()), value=float(x_vals.mean()), step=0.01, key='s1')
        u2 = st.sidebar.number_input("U-Value 2", min_value=float(y_vals.min()), max_value=float(y_vals.max()), value=float(y_vals.min()), step=0.01, key='u2')
        s2 = st.sidebar.number_input("SHGC 2", min_value=float(x_vals.min()), max_value=float(x_vals.max()), value=float(x_vals.min()), step=0.01, key='s2')

        val1, val2 = float(interp_func([u1, s1])[0]), float(interp_func([u2, s2])[0])
        pct_diff = ((val2 - val1) / val1) * 100 if val1 != 0 else 0

        # UI Results
        st.subheader(f"Results: {sector} | {selected_filename} | {selected_cz}")
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric(f"Point 1 {source_option}", f"{val1:.2f} MBTU")
        res_col2.metric(f"Point 2 {source_option}", f"{val2:.2f} MBTU")
        res_col3.metric("Difference", f"{pct_diff:.2f}%", delta=f"{pct_diff:.2f}%", delta_color="inverse")

        # Define Baseline Value for "Zero Energy" Line
        baseline_val = None
        if sector == "Commercial" and no_window_df is not None:
            baseline_val = get_commercial_baseline(no_window_df, selected_filename, selected_cz, source_option)
        elif sector == "Residential":
            if 'Wall_U' in filtered_df.columns:
                wall_u = filtered_df['Wall_U'].iloc[0]
                # Calculate energy at SHGC=0 and U=Wall_U
                baseline_val = float(interp_func([wall_u, 0])[0])
            else:
                st.warning("Column 'Wall_U' not found in residential data. Zero energy line cannot be calculated.")

        # Create Plotly Figure
        fig = go.Figure()
        fig.add_trace(go.Contour(
            z=z_vals, x=x_vals, y=y_vals,
            colorscale='Viridis',
            colorbar=dict(title=f"{source_option} (MBTU)"),
            contours=dict(coloring='heatmap', showlabels=True, labelfont=dict(size=12, color='white')),
            name="Energy Data"
        ))

        # Add Zero-Energy Isoline
        if baseline_val is not None:
            fig.add_trace(go.Contour(
                z=z_vals, x=x_vals, y=y_vals,
                showscale=False,
                contours=dict(start=baseline_val, end=baseline_val, coloring='none', showlabels=True),
                line=dict(width=5, dash='dash', color='white'),
                name="Zero Energy Baseline"
            ))
            st.info(f"The dashed line represents the 'Zero Energy' baseline ({baseline_val:.2f} MBTU).")

        # Markers
        fig.add_trace(go.Scatter(x=[s1], y=[u1], mode='markers+text', name='P1', text=["P1"], textposition="top center",
                                 marker=dict(color='white', size=12, symbol='circle', line=dict(width=2, color='black'))))
        fig.add_trace(go.Scatter(x=[s2], y=[u2], mode='markers+text', name='P2', text=["P2"], textposition="top center",
                                 marker=dict(color='red', size=12, symbol='x', line=dict(width=2, color='white'))))

        fig.update_layout(xaxis_title='SHGC [-]', yaxis_title='U-Value [BTU/(hr·ft²·F)]', width=900, height=700)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Analysis Error: {e}")

if __name__ == "__main__":
    main()
