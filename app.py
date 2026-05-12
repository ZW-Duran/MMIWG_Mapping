import pandas as pd
import plotly.graph_objects as go
import json
import os

def main():
    print("Loading data from data.csv...")
    if not os.path.exists('data.csv'):
        print("Error: 'data.csv' not found in the current directory.")
        return
        
    df_raw = pd.read_csv('data.csv')

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

    df = df.dropna(subset=['Lat', 'Lon'])
    df = df[df['Cases'] > 0]

    print("Merging data with identical coordinates...")
    df = df.groupby(['Lat', 'Lon', 'State']).agg({
        'Cases': 'sum',
        'Address': 'first' 
    }).reset_index()

    df['MarkerSize'] = (df['Cases'] * 1.5 + 5).clip(upper=12)
    state_sum = df.groupby('State')['Cases'].sum().reset_index()

    print("Initializing map visualization...")
    fig = go.Figure()

    # --- Layer 1: State Heatmap ---
    fig.add_trace(go.Choropleth(
        locations=state_sum['State'],
        z=state_sum['Cases'],
        locationmode='USA-states', 
        colorscale='Reds',        
        colorbar=dict(
            title="Total Cases",
            orientation="h",       # 将渐变色带改为水平
            yanchor="top",         # 锚定在顶部
            y=-0.05,               # 将它向下推移至地图下方
            xanchor="center",      # 水平居中
            x=0.5,
            len=0.6,               # 限制色带长度为地图宽度的 60% 防止过长
            thickness=15           # 调整色带粗细
        ),
        marker_line_color='white', 
        hovertemplate='<b>State: %{location}</b><br>Total Cases: %{z}<extra></extra>' 
    ))

    # --- Layer 2: Indigenous Reservations (Read from local file) ---
    geojson_filename = 'reservations.geojson' # 修复：去掉了多余的 s，与你本地的实际文件名匹配
    
    if os.path.exists(geojson_filename):
        print(f"Reading local GeoJSON: {geojson_filename}...")
        try:
            with open(geojson_filename, 'r', encoding='utf-8') as f:
                res_geojson = json.load(f)
            
            # CRITICAL: Plotly needs an 'id' field at the feature level to map locations
            # We will use the list index as a temporary ID
            features = res_geojson.get('features', [])
            
            # 我们将多边形按名字归类到不同的字典中，以便分别画在不同的图层并生成图例
            categories = {}
            
            for i, feature in enumerate(features):
                feature_id = str(feature.get('id', i))
                feature['id'] = feature_id
                
                props = feature.get('properties', {})
                name = props.get('NAME') or props.get('NAMELSAD') or props.get('name') or "Unknown Reservation"
                
                # 基于多边形的名称进行简单的类型分类
                name_lower = name.lower()
                if 'hawaiian' in name_lower:
                    cat = 'Native Hawaiian Area'
                elif 'alaska' in name_lower or 'anvsa' in name_lower:
                    cat = 'Alaska Native Village'
                elif 'oklahoma' in name_lower or 'otsa' in name_lower:
                    cat = 'Oklahoma Tribal Area'
                elif 'trust land' in name_lower and 'reservation' not in name_lower:
                    cat = 'Trust Land'
                else:
                    cat = 'American Indian Reservation'

                # 将 feature 归入对应的分类
                if cat not in categories:
                    categories[cat] = {'features': [], 'ids': [], 'names': []}
                
                categories[cat]['features'].append(feature)
                categories[cat]['ids'].append(feature_id)
                categories[cat]['names'].append(name)

                # 修复 Winding Order 问题：反转多边形的绘制方向
                geom = feature.get('geometry')
                if geom:
                    gtype = geom.get('type')
                    if gtype == 'Polygon':
                        geom['coordinates'] = [ring[::-1] for ring in geom.get('coordinates', [])]
                    elif gtype == 'MultiPolygon':
                        geom['coordinates'] = [[ring[::-1] for ring in poly] for poly in geom.get('coordinates', [])]

            print(f"Successfully categorized {len(features)} reservation boundaries.")

            # 为不同类别的保留地定义不同的颜色
            color_map = {
                'American Indian Reservation': 'rgb(46, 139, 87)',  # 绿色
                'Alaska Native Village': 'rgb(70, 130, 180)',       # 钢蓝色
                'Native Hawaiian Area': 'rgb(255, 140, 0)',         # 深橙色
                'Oklahoma Tribal Area': 'rgb(218, 165, 32)',        # 金菊色
                'Trust Land': 'rgb(154, 205, 50)'                   # 黄绿色
            }
            
            # 循环遍历分类，每一类画一个 Choropleth 从而生成图例
            for cat, data in categories.items():
                cat_geojson = {"type": "FeatureCollection", "features": data['features']}
                color = color_map.get(cat, 'rgb(128, 128, 128)')
                
                fig.add_trace(go.Choropleth(
                    name=cat,                  # 开启图例并设置分类名称
                    showlegend=True,
                    geojson=cat_geojson,
                    featureidkey="id",
                    locations=data['ids'],
                    z=[1] * len(data['ids']),
                    zmin=0,
                    zmax=1,
                    colorscale=[[0, color], [1, color]],
                    marker=dict(
                        opacity=0.6,           # 稍微提高透明度让色块更明显
                        line=dict(width=0)     # 核心优化：宽度设为0，去掉边界描边，渲染性能提升数倍！
                    ),
                    showscale=False,
                    text=data['names'],
                    hovertemplate='<b>%{text}</b><br>' + cat + '<extra></extra>' 
                ))
        except Exception as e:
            print(f"Error reading or plotting GeoJSON file: {e}")
    else:
        print(f"Warning: '{geojson_filename}' not found in the current directory.")

    # --- Layer 3: Case Pins ---
    print("Plotting case locations...")
    hover_texts = "<b>Address:</b> " + df['Address'] + "<br><b>Cases:</b> " + df['Cases'].astype(int).astype(str)

    fig.add_trace(go.Scattergeo(
        name='Cases',
        lon=df['Lon'],
        lat=df['Lat'],
        locationmode='USA-states',
        mode='markers',
        marker=dict(
            symbol='circle',      
            size=df['MarkerSize'],
            color='rgba(0, 85, 255, 0.9)', 
            line=dict(width=1, color='white')
        ),
        text=hover_texts,
        hovertemplate='%{text}<extra></extra>'
    ))

    fig.update_layout(
        title_text='MMIWG Distribution & Indigenous Reservations',
        geo=dict(
            scope='usa',
            projection_type='albers usa',
            showlakes=True,
            lakecolor='white',
            showland=True,
            landcolor='rgb(250, 250, 250)',
        ),
        margin={"r":0, "t":50, "l":0, "b":80}  # 将底部边距从 0 改为 80，为水平色带留出显示空间
    )

    output_filename = 'mmiwg_interactive_map.html'
    fig.write_html(output_filename)
    print(f"Process complete. File saved as: '{output_filename}'")

if __name__ == '__main__':
    main()