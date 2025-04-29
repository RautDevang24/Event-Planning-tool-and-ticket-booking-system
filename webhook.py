from flask import Flask, request, jsonify
import mysql.connector
import uuid
import re
from utils.reemail import send_email
from datetime import datetime, timedelta
import requests
import threading

app = Flask(__name__)

# Store user session data
user_sessions = {}

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Devang@1224",
        database="TicketBooking"
    )

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

def background_booking(booking_data, session_id):
    try:
        api_url = "http://127.0.0.1:5000/book_ticket"
        response = requests.post(api_url, json=booking_data)
        response.raise_for_status()
        booking_response = response.json()
        print(f"Booking response: {booking_response}")
        
    except Exception as e:
        print(f"Background booking failed for session {session_id}: {str(e)}")

def is_valid_aadhaar(aadhaar_number):
    print(f"Aadhaar Type: {type(aadhaar_number)}, Value: {aadhaar_number}")
    aadhaar_number = str(aadhaar_number)  # Convert to string
    return aadhaar_number.isdigit() and len(aadhaar_number) == 12

def is_valid_date(date_time):
    max_booking_days = 60  # 2 months
    booking_start_time = 7  # 7 AM
    booking_end_time = 21  # 9 PM
    max_date = datetime.now() + timedelta(days=max_booking_days)
    return datetime.now() <= date_time <= max_date and booking_start_time <= date_time.hour < booking_end_time

def send_latest_booking_email(aadhaar_number, email):
    conn = get_db_connection()
    print(aadhaar_number)
    print(email)
    try:
        with conn.cursor() as cursor:
            query = """
                SELECT booking_id, slot_time, ticket_count, username
                FROM bookings
                WHERE aadhaar_number = %s AND email = %s
                ORDER BY slot_time DESC
                LIMIT 1;

            """
            cursor.execute(query, (aadhaar_number, email))
            result = cursor.fetchone()

            if result:
                booking_id, slot_time, ticket_count, username = result
                booking_thread = threading.Thread(target=send_email, args=(email, booking_id, slot_time, ticket_count, username))
                booking_thread.start()
                # send_email(email, booking_id, slot_time, ticket_count, username)
                return 0
            else:
                return 1
    finally:
        conn.close()

def check_availability(slot_time):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(ticket_count), 0) FROM bookings WHERE slot_time = %s", (slot_time,))
    booked_tickets = cursor.fetchone()[0] or 0
    conn.close()
    return 500 - booked_tickets  # Max 500 per slot

@app.route('/dialogflow-webhook', methods=['POST'])
def dialogflow_webhook():
    req = request.get_json()
    intent_name = req['queryResult']['intent']['displayName']
    parameters = req['queryResult']['parameters']
    session_id = req['session']  # Unique user session
    print(f"Session ID: {session_id}")

    # Initialize session storage if not exists
    if session_id not in user_sessions:
        user_sessions[session_id] = {}

    # Store user inputs in session storage
    if intent_name == "ask_for_username":
        user_sessions[session_id]['username'] = parameters.get("username")
        return jsonify({"fulfillmentText": "Please provide your email address.eg: my email id is xyz@abc.com"})

    elif intent_name == "ask_for_email":
        email = parameters.get("email")
        if not is_valid_email(email):
            return jsonify({"fulfillmentText": "Invalid email format! Please enter a valid email."})
        user_sessions[session_id]['email'] = email
        return jsonify({"fulfillmentText": "What would you like to do?\n1. Book a ticket\n2. Download a previous ticket\n3. Contact help"})

    elif intent_name == "down_aad_email":
        print("Raw parameters:", parameters)
        aadhaarr = parameters.get("aadharr")
        print(f"input aadhaarr:{aadhaarr}")
        emaill= parameters.get("emaill")
        if not is_valid_aadhaar(aadhaarr):
            print(aadhaarr)
            return jsonify({"fulfillmentText": "Invalid Aadhaar! Enter a 12-digit number."})
        if not is_valid_email(emaill):
            return jsonify({"fulfillmentText": "Invalid email format! Please enter a valid email."})
        else:
           print(f"fun aadhaar:{aadhaarr}")
           result = send_latest_booking_email(aadhaarr, emaill)
           print(result)
           if result == 1:
               return jsonify({"fulfillmentText": "No booking found for the given Aadhaar and email."})
           else:
               return jsonify({"fulfillmentText": "The ticket will be shortly send to your email."})

    elif intent_name == "ask_for_aadhaar":
        aadhaar = parameters.get("aadhaar")
        if not is_valid_aadhaar(aadhaar):
            return jsonify({"fulfillmentText": "Invalid Aadhaar! Enter a 12-digit number."})
        user_sessions[session_id]['aadhaar_number'] = aadhaar
        return jsonify({"fulfillmentText": "Enter your preferred booking date and time. eg: i want to book for 1 may at 3 pm"})

    elif intent_name == "ask_for_date_time":
        date_time_data = parameters.get("date-time")  
        if isinstance(date_time_data, dict) and "date_time" in date_time_data:
          date_time_str = date_time_data["date_time"]  # Extract the actual string
        print(f"Received date-time: {date_time_str}")  # Debugging
        try:
            date_time = datetime.strptime(date_time_str[:19], "%Y-%m-%dT%H:%M:%S")
            if not is_valid_date(date_time):
                return jsonify({"fulfillmentText": "Invalid date or time! Enter a valid date within booking hours."})
            user_sessions[session_id]['date_time'] = date_time.strftime("%Y-%m-%d %H")
            available_tickets = check_availability(date_time)
            return jsonify({"fulfillmentText": f"Available tickets: {available_tickets}. Enter the number of tickets you want to book. eg: i want 1 ticket"})
        except ValueError:
            return jsonify({"fulfillmentText": "Invalid date format! Use eg: i want to book for 1 may at 3 pm."})

    elif intent_name == "ask_for_ticket_count":
        ticket_count = int(parameters.get("number"))
        if ticket_count > 4:
            return jsonify({"fulfillmentText": "You can book a maximum of 4 tickets per Aadhaar."})
        user_sessions[session_id]['ticket_count'] = ticket_count
        if ticket_count== 1:
         user_sessions[session_id]['passenger_names'] = user_sessions[session_id]['username']
         return jsonify({"fulfillmentText": "Confirm your booking? (yes/no)"})
        else:   
         return jsonify({"fulfillmentText": "Please provide passenger names. eg: one is Rugved other is Sandeep"})

    elif intent_name == "ask_for_passenger_names":
        passenger_names = parameters.get("passenger_names", [])
        if not isinstance(passenger_names, list):
            return jsonify({"fulfillmentText": "Invalid input! Please provide passenger names, eg: one is Rugved other is Sandeep."})
        user_sessions[session_id]['passenger_names'] = passenger_names
        return jsonify({"fulfillmentText": "Confirm your booking? (yes/no)"})

    elif intent_name == "yes_confirm_booking":
        print(f"Current session data: {user_sessions}")
        # Prepare the booking request
        booking_data = {
                "username": user_sessions[session_id]['username'],
                "email": user_sessions[session_id]['email'],
                "aadhaar_number": user_sessions[session_id]['aadhaar_number'],
                "date_time": user_sessions[session_id]['date_time'],
                "ticket_count": user_sessions[session_id]['ticket_count'],
                "passenger_names": user_sessions[session_id]['passenger_names']
            }
        
        # Launch booking in background thread
        booking_thread = threading.Thread(target=background_booking, args=(booking_data, session_id))
        booking_thread.start()

        # api_url = "http://127.0.0.1:5000/book_ticket"
        # try:
        #         response = requests.post(api_url, json=booking_data)
        #         response.raise_for_status()  # Raises an error for HTTP errors
        #         booking_response = response.json()
        #         print(f"Booking response: {booking_response}")  # Debugging

        #         message_value = booking_response.get("message")
        #         print(f"Message value: '{message_value}'")
        #         book_id = booking_response.get("booking_id")
                
        #         if message_value and message_value.strip() == "Booking successful":
        #            user_sessions.pop(session_id, None)
        #            print(f"Booking fun response: {booking_response}")  # Debugging
        #            final_message = f"Congratulations! Your ticket has been booked. Booking ID: {book_id}."
        #            print(f"Final response to Dialogflow: {final_message}")
        #            return jsonify({
        #                "fulfillmentText": final_message
        #            })
        #         else:
        #            print("Booking not successful or message mismatch.")
                
        # except requests.exceptions.RequestException as e:
        #         return jsonify({"fulfillmentText": f"Booking failed due to an error: {str(e)}. Please try again later."})

        return jsonify({"fulfillmentText": f"Your booking is being processed! You will receive a confirmation email shortly."})

    elif intent_name == "no_confirm_booking":
        user_sessions.pop(session_id, None)
        return jsonify({"fulfillmentText": "Booking cancelled."})
        


if __name__ == "__main__":
    app.run(port=5001, debug=True, use_reloader=False)