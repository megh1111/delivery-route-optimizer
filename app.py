import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import st_folium
import random
import pandas as pd
from folium.features import DivIcon

# Page Config
st.set_page_config(page_title="India Last-Mile Optimizer", layout="wide")

st.title("AI Route Optimizer: Last-Mile Delivery")
st.markdown("Optimizing delivery sequences in high-congestion urban Indian neighborhoods.")

# Initialize Session State to keep data persistent across reruns
if 'map_obj' not in st.session_state:
    st.session_state.map_obj = None
if 'route_summary' not in st.session_state:
    st.session_state.route_summary = None
if 'total_time' not in st.session_state:
    st.session_state.total_time = 0

# Sidebar Inputs
st.sidebar.header("Delivery Settings")
place_name = st.sidebar.text_input("Enter Neighborhood (e.g. Indiranagar, Bengaluru)", "Indiranagar, Bengaluru, India")
num_stops = st.sidebar.slider("Number of Delivery Stops", 2, 10, 5)
traffic_multiplier = st.sidebar.slider("Traffic Congestion Factor", 1.0, 3.0, 1.5)

@st.cache_data
def load_map(location):
    # Fetch road network
    G = ox.graph_from_place(location, network_type='drive')
    # Realistic speeds for Indian urban traffic (km/h)
    hwy_speeds = {
        'residential': 10, 
        'tertiary': 18, 
        'secondary': 25, 
        'primary': 35
    }
    G = ox.add_edge_speeds(G, hwy_speeds=hwy_speeds, fallback=15)
    G = ox.add_edge_travel_times(G)
    return G

try:
    graph = load_map(place_name)
    nodes_list = list(graph.nodes())

    if st.sidebar.button("Optimize Route"):
        with st.spinner("Analyzing traffic and calculating best path..."):
            # 1. Pick random delivery stops
            delivery_points = random.sample(nodes_list, num_stops)
            depot = delivery_points[0]
            
            # 2. Optimization Logic (Greedy Nearest Neighbor)
            current = depot
            unvisited = set(delivery_points[1:])
            full_route_nodes = []
            total_time_mins = 0
            stops_data = []

            while unvisited:
                # Find the next closest stop based on travel_time (seconds)
                next_node = min(unvisited, key=lambda node: nx.shortest_path_length(graph, current, node, weight='travel_time'))
                
                # Calculate path and cost
                path_segment = nx.shortest_path(graph, current, next_node, weight='travel_time')
                raw_seconds = nx.shortest_path_length(graph, current, next_node, weight='travel_time')
                
                # Convert seconds to minutes and apply traffic factor
                segment_time_mins = (raw_seconds / 60) * traffic_multiplier
                
                full_route_nodes.extend(path_segment[:-1])
                total_time_mins += segment_time_mins
                stops_data.append({
                    "Step": len(stops_data) + 1,
                    "Est. Time (min)": round(segment_time_mins, 2)
                })
                
                unvisited.remove(next_node)
                current = next_node
            
            # 3. Build the Map
            start_node_data = graph.nodes[depot]
            m = folium.Map(location=[start_node_data['y'], start_node_data['x']], zoom_start=15, tiles="cartodbpositron")
            
            # Draw the route line
            route_coords = [(graph.nodes[n]['y'], graph.nodes[n]['x']) for n in full_route_nodes]
            folium.PolyLine(route_coords, color="#2A81CB", weight=5, opacity=0.8).add_to(m)
            
            # Auto-zoom map
            m.fit_bounds(route_coords)
            
            # Add markers for stops with Centered Circular Number Labels
            for i, stop in enumerate(delivery_points):
                p = graph.nodes[stop]
                icon_color = 'red' if i == 0 else 'blue'
                
                # Pin Marker
                folium.Marker(
                    [p['y'], p['x']], 
                    icon=folium.Icon(color=icon_color, icon='info-sign')
                ).add_to(m)
                
                # Centered Number Label
                folium.Marker(
                    [p['y'], p['x']],
                    icon=DivIcon(
                        icon_size=(30,30),
                        icon_anchor=(15,45), # Aligns center of circle with pin top
                        html=f'''
                            <div style="
                                font-size: 10pt; 
                                color: white; 
                                font-weight: bold; 
                                background-color: rgba(0,0,0,0.7); 
                                border-radius: 50%; 
                                width: 22px; 
                                height: 22px; 
                                display: flex; 
                                justify-content: center; 
                                align-items: center;
                                border: 1.5px solid white;">
                                {i}
                            </div>''',
                    )
                ).add_to(m)
            
            # Save results to Session State
            st.session_state.map_obj = m
            st.session_state.route_summary = pd.DataFrame(stops_data)
            st.session_state.total_time = round(total_time_mins, 2)

    # 4. Render Layout
    if st.session_state.map_obj:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Interactive Route Map")
            # stability fix: key and returned_objects
            st_folium(
                st.session_state.map_obj, 
                width=800, 
                height=550,
                key="stable_final_map",
                returned_objects=[] 
            )
        
        with col2:
            st.subheader("Route Analytics")
            st.metric("Total Travel Time", f"{st.session_state.total_time} mins")
            st.write("Step-by-Step Breakdown:")
            st.dataframe(st.session_state.route_summary, hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"Something went wrong. Please check your area name or try again. Error: {e}")