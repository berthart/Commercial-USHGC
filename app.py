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
    # Load the selected dataset
    df = pd.read_csv(file_path)
    return df

def main():
    st.title("Building Energy Comparison & Contour Plot")
    st.markdown("""
    This tool allows you to select a dataset, compare two window configurations, 
    and see the impact on energy consumption through interactive contour maps and interpolation.
    """)

    # Sidebar: File Selection
    st.sidebar.header("1. Data Source")
    # List all CSV files in the current directory
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    if not csv_files:
        st.error("No CSV files found in the directory.")
        return

    selected_file = st.sidebar.selectbox("Select CSV Data File", csv_files)
    
    # Load data based on selection
    df = load_data(selected_file)

    # Sidebar: Filtering
    st.sidebar.header("2. Analysis Settings")
    
    # Climate Zone Dropdown (depends on selected file)
    cz_list = sorted(df['Climate Zone'].unique())
    selected_cz = st.sidebar.selectbox("Select Climate Zone", cz_list)

    # Metric Radio Button
    # Dynamically find available source columns if they differ between files
    available_metrics = [col for col in ['TotalSource', 'CoolingSource', 'HeatingSource'] if col in df.columns]
    source_option = st.sidebar.radio("Select Metric", available_metrics)

    # Filter data based on selection
    filtered_df = df[df['Climate Zone'] == selected_cz]

    try:
        # Prepare data for Plotting and Interpolation
        pivot_df = filtered_df.pivot(index='U', columns='SHGC', values=source_option)
        pivot_df = pivot_df.sort_index().sort_index(axis=1)
        
        y_vals = pivot_df.index.values    # U-Values
        x_vals = pivot_df.columns.values  # SHGC-Values
        z_vals = pivot_df.values          # Metric Matrix

        # Sidebar: User Inputs for Comparison
        st.sidebar.header("3. Configuration Comparison")
        
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
        
        # Calculate % Difference
        pct_diff = ((val2 - val1) / val1) * 100 if val1 != 0 else 0

        # UI Results Layout
        st.subheader(f"Comparison Results: {selected_file} | {selected_cz}")
        res_col1, res_col2, res_col3 = st.columns(3)
        
        res_col1.metric(f"Point 1 {source_option}", f"{val1:.2f} MBTU")
        res_col2.metric(f"Point 2 {source_option}", f"{val2:.2f} MBTU")
        # delta_color="inverse" means negative change (savings) is green
        res_col3.metric("Difference", f"{pct_diff:.2f}%", delta=f"{pct_diff:.2f}%", delta_color="inverse")

        # Create Plotly Contour Plot
        fig = go.Figure()

        # Add Contour Layer
        fig.add_trace(go.Contour(
            z=z_vals,
            x=x_vals,
            y=y_vals,
            colorscale='Viridis',
            colorbar=dict(title=f"{source_option} (MBTU)"),
            contours=dict(
                coloring='heatmap',
                showlabels=True,
                labelfont=dict(size=12, color='white')
            ),
            hovertemplate = (
                "<b>SHGC (-):</b> %{x}<br>" +
                "<b>U (BTU/hr·ft²·F):</b> %{y}<br>" +
                "<b>" + source_option + ":</b> %{z:.2f} MBTU<extra></extra>"
            )
        ))

        # Add Point 1 Marker
        fig.add_trace(go.Scatter(
            x=[s1], y=[u1],
            mode='markers+text',
            marker=dict(color='white', size=14, symbol='circle', line=dict(width=2, color='black')),
            name='Point 1 (Ref)',
            text=["P1"],
            textposition="top center"
        ))

        # Add Point 2 Marker
        fig.add_trace(go.Scatter(
            x=[s2], y=[u2],
            mode='markers+text',
            marker=dict(color='red', size=14, symbol='x', line=dict(width=2, color='white')),
            name='Point 2 (Comp)',
            text=["P2"],
            textposition="top center"
        ))

        # Update Layout
        fig.update_layout(
            xaxis_title='Solar Heat Gain Coefficient (SHGC) [-]',
            yaxis_title='U-Value [BTU/(hr·ft²·F)]',
            width=900,
            height=700,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
        st.info("The selected file must contain columns: 'Climate Zone', 'U', 'SHGC', and the energy source metrics.")

if __name__ == "__main__":
    main()
