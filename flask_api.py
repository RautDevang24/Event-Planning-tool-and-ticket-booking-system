from flask import Flask, request, jsonify
from database.db_config import get_db_connection
from utils.email_sender import send_email  # Import email sender function
import uuid
import re
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Welcome to the Ticket Booking API!"}), 200

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

def is_valid_aadhaar(aadhaar_number):
    return aadhaar_number.isdigit() and len(aadhaar_number) == 12

def is_valid_date(date_time):
    max_date = datetime.now() + timedelta(days=60)
    return datetime.now() <= date_time <= max_date

@app.route("/book_ticket", methods=["POST"])
def book_ticket():
    data = request.json
    username = data.get("username")
    email = data.get("email")
    aadhaar_number = data.get("aadhaar_number")
    date_str = data.get("date_time")
    ticket_count = int(data.get("ticket_count", 0))
    passenger_names = data.get("passenger_names", [])
    print(f"Received email: '{email}'")  # Check what Flask API is receiving

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email format"}), 400
    if not is_valid_aadhaar(aadhaar_number):
        return jsonify({"error": "Invalid Aadhaar number"}), 400
    
    try:
        date_time = datetime.strptime(date_str, "%Y-%m-%d %H")
        if not is_valid_date(date_time):
            return jsonify({"error": "Invalid booking date or time! Bookings are only allowed between 7 AM and 9 PM."}), 400
        
        slot_time = date_time.replace(minute=0, second=0, microsecond=0)
        db = get_db_connection()
        cursor = db.cursor()
        
        db.start_transaction()
        
        # Lock Aadhaar number for the slot
        cursor.execute("SELECT * FROM booking_locks WHERE aadhaar_number = %s AND slot_time = %s FOR UPDATE", (aadhaar_number, slot_time))
        if cursor.fetchone():
            db.rollback()
            return jsonify({"error": "Booking is already in progress for this Aadhaar number and slot"}), 400
        
        # Insert a lock record
        cursor.execute("INSERT INTO booking_locks (aadhaar_number, slot_time) VALUES (%s, %s)", (aadhaar_number, slot_time))
        
        cursor.execute("SELECT COALESCE(SUM(ticket_count), 0) FROM bookings WHERE slot_time = %s FOR UPDATE", (slot_time,))
        booked_tickets = cursor.fetchone()[0] or 0
        if booked_tickets + ticket_count > 500:
            db.rollback()
            return jsonify({"error": "Slot is full"}), 400
        
        cursor.execute("SELECT COALESCE(SUM(ticket_count), 0) FROM bookings WHERE aadhaar_number = %s AND slot_time = %s FOR UPDATE", (aadhaar_number, slot_time))
        user_tickets = cursor.fetchone()[0] or 0
        if user_tickets + ticket_count > 4:
            db.rollback()
            return jsonify({"error": "You can book only 4 tickets per slot"}), 400
        
        booking_id = "BK-" + uuid.uuid4().hex[:8].upper()
        
        sql_booking = "INSERT INTO bookings (booking_id, username, email, aadhaar_number, slot_time, ticket_count) VALUES (%s, %s, %s, %s, %s, %s)"
        values_booking = (booking_id, username, email, aadhaar_number, slot_time, ticket_count)
        cursor.execute(sql_booking, values_booking)
        
        for passenger in passenger_names:
            sql_passenger = "INSERT INTO passengers (booking_id, passenger_name) VALUES (%s, %s)"
            cursor.execute(sql_passenger, (booking_id, passenger))
        
        db.commit()
        send_email(email, booking_id, slot_time, ticket_count, username)
        
        cursor.close()
        db.close()
        return jsonify({"message": "Booking successful", "booking_id": booking_id}), 200

    except ValueError:
        return jsonify({"error": "Invalid date format! Use YYYY-MM-DD HH"}), 400
    except Exception as e:
        try:
          db.rollback()
          db.close()
        except:
          pass  # in case db wasn't initialized
        print("Booking failed due to:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
