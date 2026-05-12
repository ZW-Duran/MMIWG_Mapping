import pandas as pd
import plotly.graph_objects as go
import json

def main():
    print("Loading data from data.csv...")
    df_raw = pd.read_csv('data.csv')

    # Column Mapping: D=3(State), E=4(Address), F=5(Lat), G=6(Lon), P=15(Cases)
    try:
        df = pd.DataFrame({
            'State': df_raw.iloc[:, 3].astype(str).str.strip().str.upper(),
            'Address': df_raw.iloc[:, 4].astype(str),
            'Lat': pd.to_numeric(df_raw.iloc[:, 5], errors='coerce'),
            'Lon': pd.to_numeric(df_raw.iloc[:, 6], errors='coerce'),
            'Cases': pd.to_numeric(df_raw.iloc[:, 15], errors='coerce').fillna(0)
        })
    except IndexError:
        print("Error: CSV structure mismatch. Please check the columns.")
        return

    # Data Cleaning: Remove rows with invalid coordinates and zero cases
    df = df.dropna(subset=['Lat', 'Lon'])
    df = df[df['Cases'] > 0]

    # --- Step: Merge identical coordinates ---
    print("Merging data with identical coordinates...")
    # Group by Lat and Lon. We also include State and Address to keep them in the result.
    # We sum the Cases, and for Address, we take the first unique one.
    df = df.groupby(['Lat', 'Lon', 'State']).agg({
        'Cases': 'sum',
        'Address': 'first' 
    }).reset_index()

    # Calculate dynamic marker size (Capped at 12)
    # We use a slightly different scale to accommodate summed cases
    df['MarkerSize'] = (df['Cases'] * 1.5 + 5).clip(upper=12)

    # Aggregate total cases for the State Heatmap (Layer 1)
    state_sum = df.groupby('State')['Cases'].sum().reset_index()

    print("Initializing map visualization...")
    fig = go.Figure()

    # --- Layer 1: State Heatmap (Choropleth) ---
    fig.add_trace(go.Choropleth(
        locations=state_sum['State'],
        z=state_sum['Cases'],
        locationmode='USA-states', 
        colorscale='Reds',        
        colorbar_title="Total Cases",
        marker_line_color='white', 
        hovertemplate='<b>State: %{location}</b><br>Total Cases: %{z}<extra></extra>' 
    ))

    # --- Layer 2: Indigenous Reservations (GeoJSON) ---
    print("Checking for reservations.geojson...")
    try:
        with open('reservations.geojson', 'r', encoding='utf-8') as f:
            res_geojson = json.load(f)

        res_ids = [str(i) for i in range(len(res_geojson['features']))]
        for i, feature in enumerate(res_geojson['features']):
            feature['id'] = str(i)
            
        res_names = [f['properties'].get('NAME', 'Reservation') for f in res_geojson['features']]

        fig.add_trace(go.Choropleth(
            geojson=res_geojson,
            locations=res_ids,
            z=[1] * len(res_ids), 
            colorscale=[[0, 'rgba(46, 139, 87, 0.3)'], [1, 'rgba(46, 139, 87, 0.3)']], 
            showscale=False,
            marker_line_color='rgba(46, 139, 87, 0.5)',
            marker_line_width=0.5,
            text=res_names,
            hovertemplate='<b>%{text}</b><extra></extra>' 
        ))
        print("Reservation layer added.")
    except FileNotFoundError:
        print("Notice: 'reservations.geojson' not found. Skipping Layer 2.")

    # --- Layer 3: Case Pins (Scattergeo with 'diamond' symbol) ---
    print("Plotting merged case pins...")
    hover_texts = "<b>Address:</b> " + df['Address'] + "<br><b>Total Cases at this location:</b> " + df['Cases'].astype(int).astype(str)

    fig.add_trace(go.Scattergeo(
        lon=df['Lon'],
        lat=df['Lat'],
        locationmode='USA-states',
        mode='markers',
        marker=dict(
            symbol='circle',      
            size=df['MarkerSize'],
            color='rgba(0, 85, 255, 0.8)', 
            line=dict(width=0.5, color='white')
        ),
        text=hover_texts,
        hovertemplate='%{text}<extra></extra>'
    ))

    # Final Layout Tweaks
    fig.update_layout(
        title_text='MMIWG: Missing and Murdered Indigenous Women and Girls Distribution',
        geo=dict(
            scope='usa',
            projection_type='albers usa',
            showlakes=True,
            lakecolor='white',
            landcolor='rgb(250, 250, 250)',
            subunitcolor='rgb(200, 200, 200)'
        ),
        margin={"r":0, "t":50, "l":0, "b":0}
    )

    output_filename = 'mmiwg_map.html'
    fig.write_html(output_filename)
    print(f"Process complete. Output saved to: '{output_filename}'")

if __name__ == '__main__':
    main()