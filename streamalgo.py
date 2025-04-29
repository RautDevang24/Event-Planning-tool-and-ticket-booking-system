import math
import requests
from urllib.parse import quote
from datetime import datetime
import numpy as np
import streamlit as st
from streamlit_js_eval import streamlit_js_eval
from visualize import visualize_event_space

# Hardcoded Google API Key
API_KEY = "your google api key"

st.set_page_config(page_title="Event Planner", page_icon="🎉", layout="centered")

# Custom CSS for Black and Red Theme
st.markdown("""
    <style>
    body {
        background-color: #000000;
        color: #FF4B4B;
    }
    .stButton>button {
        background-color: #FF4B4B;
        color: white;
        border: none;
    }
    .stTextInput>div>div>input {
        background-color: #1e1e1e;
        color: white;
    }
    .stNumberInput>div>input {
        background-color: #1e1e1e;
        color: white;
    }
    .stSelectbox>div>div {
        background-color: #1e1e1e;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)


def get_lat_lon(location):
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": location, "key": API_KEY}
    response = requests.get(base_url, params=params)
    data = response.json()
    if data["status"] == "OK":
        lat = data["results"][0]["geometry"]["location"]["lat"]
        lon = data["results"][0]["geometry"]["location"]["lng"]
        return lat, lon
    else:
        st.error("Location not found!")
        return None, None


def get_event_factor(date, calendar_id="en.indian#holiday@group.v.calendar.google.com"):
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    date_str = date_obj.strftime("%Y-%m-%d")

    time_min = f"{date_str}T00:00:00Z"
    time_max = f"{date_str}T23:59:59Z"
    calendar_encoded = quote(calendar_id, safe='')
    base_url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_encoded}/events"
    params = {"key": API_KEY, "timeMin": time_min, "timeMax": time_max, "singleEvents": True}
    response = requests.get(base_url, params=params)
    data = response.json()

    if "items" in data and len(data["items"]) > 0 and date_obj.weekday() >= 5:
        return 2  # Festival/holiday + weekend
    elif "items" in data and len(data["items"]) > 0:
        return 1.5  # Festival/holiday
    elif date_obj.weekday() >= 5:
        return 1.2  # Weekend
    else:
        return 1.0

def get_geolocation():
    try:
        response = requests.get('https://ipinfo.io/json')
        data = response.json()
        loc = data['loc'].split(',')
        return {"latitude": float(loc[0]), "longitude": float(loc[1])}
    except:
        return None
    
def calculate_emergency_exits(crowd_at_a_time):
    T = 2
    U = crowd_at_a_time / (50 * T)
    U = math.ceil(U) if U % 1 >= 0.3 else math.floor(U)
    E = (U / 6) + 1
    E = math.ceil(E) if E % 1 >= 0.75 else math.floor(E)
    total_width = U * 0.75
    suggested_exit_width = round(total_width / E, 2)
    return {
        "Total Exit Units Required": U,
        "Number of Emergency Exits Required": E,
        "Suggested Exit Width (meters) per Exit": suggested_exit_width
    }


def format_time(hour_float):
    hour = int(hour_float)
    minutes = int((hour_float - hour) * 60)
    return f"{hour:02d}:{minutes:02d}"


def main():
    st.title("🎉 Event Space Planning Tool")
    st.subheader("Plan your safe, optimized event layout")

    # Select shape outside the form
    shape = st.selectbox("🔺 Event Shape", ["Circle", "Rectangle"])
    event_type = st.selectbox("🎭 Event Type", ["Open Ground", "Stage Event / Religious Place"])
    location_option = st.radio("📍 How would you like to set your location?", ("Enter Address", "Use My Current Location"))
    

    with st.form("event_form"):
        user_date = st.date_input("📅 Event Date").strftime("%Y-%m-%d")
        # location = st.text_input("📍 Event Location")
        # Location input option
        if location_option == "Enter Address":
            location = st.text_input("📍 Event Location (Text)")
            latitude, longitude = None, None

        if shape == "Rectangle":
            length = st.number_input("📏 Length (m)", min_value=1.0, step=1.0)
            width = st.number_input("📐 Width (m)", min_value=1.0, step=1.0)
            radius = None
        else:
            radius = st.number_input("🔵 Radius (m)", min_value=1.0, step=1.0)
            length = width = None

        upper_bound = st.number_input("🕐 Event Start Time (24h)", min_value=0, max_value=23)
        lower_bound = st.number_input("🕑 Event End Time (24h)", min_value=0, max_value=23)


        if event_type != "Open Ground":
            stage_or_structure_area = st.number_input("🏟️ Stage/Structure Area (sq m)", min_value=0.0, step=1.0)
        else:
            stage_or_structure_area = 0.0

        submitted = st.form_submit_button("Calculate")

    if submitted:
        # latitude, longitude = get_lat_lon(location)
        # if latitude is None:
        #     return
        if location_option != "Enter Address":
          st.write("📡 Click the button below to fetch your current location:")
          # location_button = st.button("Get My Location")
          latitude, longitude = None, None
          if submitted:
              location = get_geolocation()
              if location:
                 latitude = location["latitude"]
                 longitude = location["longitude"]
                 st.success(f"📍 Location fetched: Latitude {latitude}, Longitude {longitude}")
              else:
                 st.error("Unable to retrieve your location. Please make sure location services are enabled.")
        if location_option == "Enter Address":
          latitude, longitude = get_lat_lon(location)
          if latitude is None:
            return
        else:
          if not latitude or not longitude:
            st.error("Location not fetched. Please click the 'Get My Location' button.")
            return
          latitude = float(latitude)
          longitude = float(longitude)


        if shape == "Rectangle":
            aoe = length * width
        else:
            aoe = math.pi * (radius ** 2)

        event_factor = get_event_factor(user_date)
        avg_poss_crowd = 6000
        possible_crowd = avg_poss_crowd * event_factor
        avg_human_space = 1.5

        effective_area = (0.8 * aoe) - stage_or_structure_area
        buffer_area = 0.2 * aoe
        at_a_time = effective_area / avg_human_space
        slots = math.ceil(possible_crowd / at_a_time)
        crowd_in_each_slot = math.ceil(possible_crowd / slots)
        exit_info = calculate_emergency_exits(crowd_in_each_slot)

        num_exits = exit_info["Number of Emergency Exits Required"]
        exit_width = exit_info["Suggested Exit Width (meters) per Exit"]
        gate_height = (radius - math.sqrt(effective_area / math.pi)) if shape == "Circle" else (length - math.sqrt(effective_area / (width / length)))
        emergency_gate_area = num_exits * exit_width * gate_height
        remaining_buffer_area = 0.95 * (buffer_area - emergency_gate_area)

        toilet_area_per_unit = 1.9
        food_stall_area_per_unit = 4.7
        toilets = max(2, math.ceil((0.15 * crowd_in_each_slot) / 60))
        food_stalls = max(2, math.ceil((0.25 * crowd_in_each_slot) / 40))
        total_facility_area = toilets * toilet_area_per_unit + food_stalls * food_stall_area_per_unit

        if total_facility_area > buffer_area:
            scale_factor = buffer_area / total_facility_area
            toilets = max(1, math.floor(toilets * scale_factor))
            food_stalls = max(1, math.floor(food_stalls * scale_factor))

        total_event_time = lower_bound - upper_bound
        time_per_slot = total_event_time / slots if slots > 0 else 0
        slot_schedule = []
        slot_start = upper_bound

        for i in range(slots):
            slot_end = slot_start + time_per_slot
            start_str = format_time(slot_start)
            end_str = format_time(slot_end)
            slot_schedule.append(f"Slot {i + 1}: {start_str} - {end_str}")
            slot_start = slot_end

        EPP = int(crowd_in_each_slot / num_exits)

        st.success("✅ Event Plan Generated!")

        st.write(f"**Event Location:** {location}")
        st.write(f"**Event Area:** {round(aoe, 2)} sq m")
        st.write(f"**Event Factor:** {event_factor} unit")
        st.write(f"**Latitude:** {latitude} unit")
        st.write(f"**Longitude:** {longitude} unit")
        st.write(f"**Effective Area:** {round(effective_area, 2)} sq m")
        st.write(f"**Possible Crowd:** {int(possible_crowd)}")
        st.write(f"**Crowd at a time:** {int(at_a_time)}")
        st.write(f"**Crowd in each slot:** {int(crowd_in_each_slot)}")
        st.write(f"**Total Slots:** {slots}")
        st.write(f"**Time per Slot:** {round(time_per_slot, 2)} hours")
        st.write(f"**Emergency Exits:** {num_exits}")
        st.write(f"**Exit Width (each):** {exit_width} m")
        st.write(f"**Remaining Buffer Area:** {round(remaining_buffer_area, 2)} sq m")
        st.write(f"**Toilets:** {toilets}")
        st.write(f"**Food Stalls:** {food_stalls}")
        st.write(f"**Entry per Exit:** {EPP} persons")

        st.subheader("🕒 Slot Schedule")
        for s in slot_schedule:
            st.write(s)

        st.subheader("📍 Event Layout Visualization")
        visualize_event_space(
            area_type=shape.lower(),
            width=width,
            height=length,
            radius=radius,
            effective_area=effective_area,
            max_crowd=int(at_a_time),
            num_exits=num_exits,
            gate_width=exit_width,
            num_toilets=toilets,
            num_stalls=food_stalls,
            stage_area=stage_or_structure_area,
            latitude=latitude,
            longitude=longitude
        )


if __name__ == "__main__":
    main()
