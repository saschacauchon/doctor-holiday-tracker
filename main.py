# =============================================================================
# Import libraries
# =============================================================================
import streamlit as st
import pandas as pd
from datetime import datetime
import json
import requests
from io import StringIO
import os
import altair as alt

# =============================================================================
# Get Metabase URL from .streamlit/secrets.toml file
# =============================================================================
st.set_page_config(layout="wide")
METABASE_URL = st.secrets['METABASE_URL']


# =================================================================================================================
# Basic methods to retrieve the data from metabase and create json data to track doctors who got replaced
# =================================================================================================================
def fetch_data_from_url(url):
    """Fetch CSV data from the provided Metabase URL"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        try:
            csv_data = StringIO(response.content.decode('utf-8'))
            return pd.read_csv(csv_data)
        except UnicodeDecodeError:
            csv_data = StringIO(response.content.decode('latin-1'))
            return pd.read_csv(csv_data)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

def load_tracking_data():
    """Load the saved tracking data from session state"""
    if 'tracking_data' not in st.session_state:
        st.session_state.tracking_data = {}
    return st.session_state.tracking_data

if not os.path.exists('data'):
    os.makedirs('data')

def save_tracking_data(tracking_data):
    """Save tracking data to a JSON file in the data directory"""
    with open('data/tracking_data.json', 'w') as f:
        json.dump(tracking_data, f)

def load_tracking_data_from_file():
    """Load tracking data from JSON file in the data directory"""
    try:
        with open('data/tracking_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# ===============
# Main app
# ===============
def main():
    st.title("Suivi des congés - Doctopus")

    col_link, col_button = st.columns([4, 1])

    with col_link:
        st.info('URL Metabase: ' + METABASE_URL, icon="ℹ️")

    with col_button:
        if st.button("🔄 Rafraîchir les données"):
            st.session_state.data = fetch_data_from_url(METABASE_URL)
    
    if 'data' not in st.session_state:
        st.session_state.data = fetch_data_from_url(METABASE_URL)
    
    df = st.session_state.data
    
    if df is not None:
        tracking_data = load_tracking_data_from_file()
        st.session_state.tracking_data = tracking_data
        
        st.markdown("<hr>", unsafe_allow_html=True)
        st.subheader("📊 Tableau de bord")

        holiday_per_week = df.groupby('week').size().reset_index(name='count')
            
        # Count replaced doctors per week
        replaced_rpps_with_week = [item.split('_') for item in tracking_data.keys()]
        replaced_data = []
        
        for rpps_week in replaced_rpps_with_week:
            if len(rpps_week) == 2:  # Ensure format is correct
                replaced_data.append({
                    'rpps': rpps_week[0],
                    'week': rpps_week[1]
                })
        
        replaced_df = pd.DataFrame(replaced_data)
        if not replaced_df.empty:
            replaced_per_week = replaced_df.groupby('week').size().reset_index(name='count')
            # Merge with all weeks for complete data
            all_weeks = pd.DataFrame({'week': holiday_per_week['week'].unique()})
            replaced_per_week = all_weeks.merge(replaced_per_week, on='week', how='left').fillna(0)
        else:
            replaced_per_week = pd.DataFrame({
                'week': holiday_per_week['week'].unique(),
                'count': [0] * len(holiday_per_week['week'].unique())
            })
        
        # Create dashboard metrics
        dashboard_cols = st.columns(3)
        
        with dashboard_cols[0]:
            st.metric(label="Nombre total de médecins", value=len(df))
        
        with dashboard_cols[1]:
            st.metric(label="Médecins remplacés", value=len(tracking_data))
        
        with dashboard_cols[2]:
            replacement_percentage = round((len(tracking_data) / len(df) * 100), 1) if len(df) > 0 else 0
            st.metric(label="Taux de remplacement", value=replacement_percentage)

        
        # Create charts
        chart_cols = st.columns(2)
        
        with chart_cols[0]:
            st.markdown("### 🏖️ Médecins en congés par semaine")
            holidays_chart = alt.Chart(holiday_per_week).mark_bar().encode(
                x=alt.X('week:N', title='Semaine'),
                y=alt.Y('count:Q', title='Nombre de médecins'),
                color=alt.value('#1E88E5'),
                tooltip=['week', 'count']
            ).properties(height=300)
            st.altair_chart(holidays_chart, use_container_width=True)
        
        with chart_cols[1]:
            st.markdown("### 🔄 Médecins remplacés par semaine")
            replaced_chart = alt.Chart(replaced_per_week).mark_bar().encode(
                x=alt.X('week:N', title='Semaine'),
                y=alt.Y('count:Q', title='Nombre de remplacements'),
                color=alt.value('#43A047'),
                tooltip=['week', 'count']
            ).properties(height=300)
            st.altair_chart(replaced_chart, use_container_width=True)
        
        st.markdown("<hr>", unsafe_allow_html=True)

        col1, col2 = st.columns([3, 1])

        with col1:
            st.subheader("🩺 Liste des médecins")
            
            # Add filters
            col_filter1, col_filter2, col_filter3 = st.columns(3)
            with col_filter1:
                search_term = st.text_input("Rechercher avec nom du médecin:", "")
            with col_filter2:
                contract_filter = st.multiselect(
                    "Filtrer par CSM",
                    options=['All'] + df['csm'].unique().tolist(),
                    default='All'
                )
            with col_filter3: 
                week_filter = st.multiselect(
                    "Filtrer par Semaine",
                    options=['All'] + df['week'].unique().tolist(),
                    default='All'
                )
            
            # Apply filters
            filtered_df = df.copy()
            if search_term:
                filtered_df = filtered_df[filtered_df['medecin'].str.contains(search_term, case=False, na=False)]
            if contract_filter and 'All' not in contract_filter:
                filtered_df = filtered_df[filtered_df['csm'].isin(contract_filter)]
            if week_filter and 'All' not in week_filter:
                filtered_df = filtered_df[filtered_df['week'].isin(week_filter)]
            
            # Display medical staff
            for index, row in filtered_df.iterrows():
                rpps = str(row['numero_rpps'])
                unique_id = f"{rpps}_{row['week']}"
                
                with st.container():
                    col_check, col_info = st.columns([1, 4])
                    
                    with col_check:

                        is_checked = st.checkbox(
                            "Replaced",
                            key=f"checkbox_{unique_id}",
                            value=unique_id in tracking_data
                        )
                        
                        if is_checked and unique_id not in tracking_data:
                            tracking_data[unique_id ] = {
                                'date': datetime.now().strftime('%Y-%m-%d'),
                                'name': row['medecin'],
                                'contract_type': row['type_contract'],
                                'csm': row['csm'],
                                'week': row['week']
                            }
                            save_tracking_data(tracking_data)
                        elif not is_checked and unique_id in tracking_data:
                            del tracking_data[unique_id]
                            save_tracking_data(tracking_data)
                    
                    with col_info:
                        st.markdown(f"""
                            **{row['medecin']}**  
                            RPPS: {row['numero_rpps']} | Semaine: {row['week']} | Contrat: {row['type_contract']} | CSM: {row['csm']}  
                            Heures Planifiées: {row['planified_hours']} | Heures Contractuelles: {row['contractual_hours']}
                        """)
                        
                        if unique_id in tracking_data:
                            replacement_by = st.text_input(
                                "Par qui est remplacé le CDI ?", 
                                key=f"replacement_by_{unique_id}",
                                value=tracking_data[unique_id].get('replacement_by', '')
                            )
                            tracking_data[unique_id]['replacement_by'] = replacement_by
                            save_tracking_data(tracking_data)
                            st.info(f"Marqué comme remplacé le: {tracking_data[unique_id]['date']}")
                    
                    st.divider()
        
        with col2:
            st.subheader("Remplacements")
            total_replaced = len(tracking_data)
            st.write(f"Effectif total remplacé: {total_replaced}")
            
            if total_replaced > 0:
                st.write("Remplacements recents:")
                for rpps, info in sorted(
                    tracking_data.items(),
                    key=lambda x: x[1]['date'],
                    reverse=True
                )[:5]:
                    st.markdown(f"""
                        **{info['name']}**  
                        🗓️ {info['date']} | 👥 {info['csm']}
                    """)
                
                if st.button("Faire un export des données"):
                    tracking_df = pd.DataFrame([
                        {
                            'RPPS': k,
                            'Name': v['name'],
                            'Replacement Date': v['date'],
                            'Contract Type': v['contract_type'],
                            'CSM': v['csm'],
                            'Week': v['week']
                        }
                        for k, v in tracking_data.items()
                    ])
                    csv = tracking_df.to_csv(index=False)
                    st.download_button(
                        "Télécharger CSV",
                        csv,
                        "staff_replacements.csv",
                        "text/csv",
                        key='download-csv'
                    )

if __name__ == "__main__":
    main()