import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
import barcode
from barcode.writer import ImageWriter
import os
from datetime import datetime

def format_datetime(date_time):
    """Convert 'YYYY-MM-DD HH' string to 'DD Month YYYY, HH:MM AM/PM' format."""
    if isinstance(date_time, str):
        dt_obj = datetime.strptime(date_time, "%Y-%m-%d %H")  # Convert string to datetime
    else:
        dt_obj = date_time  # Already a datetime object

    formatted_date = dt_obj.strftime("%d %B %Y, %I:%M %p")  # Example: "02 April 2025, 09:00 AM"
    return formatted_date

def generate_ticket_pdf(booking_id, date_time, ticket_count, username):
    pdf_filename = f"Ticket_{booking_id}.pdf"

    # Generate Barcode
    barcode_filename = f"barcode_{booking_id}.png"
    code128 = barcode.get_barcode_class('code128')
    barcode_obj = code128(booking_id, writer=ImageWriter())
    barcode_path = barcode_obj.save(barcode_filename)

    # Format Date & Time
    formatted_date_time = format_datetime(date_time)

    # PDF Setup
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Add Logo (Replace with your logo file path)
    logo_path = "C:/Users/SANDEEP/OneDrive/Desktop/Chatbot/logo.png"  # Ensure you have a logo image
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=140, height=140)
        elements.append(logo)

    # Title
    elements.append(Spacer(1, 20))
    title = Paragraph("<b><font size=18 color='#2E86C1'>🎫 Prasthana - Ticket Confirmation</font></b>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 10))

    # User Greeting
    greeting = Paragraph(f"<font size=14>Dear <b>{username}</b>,</font>", styles["Normal"])
    elements.append(greeting)
    elements.append(Spacer(1, 8))

    # Booking Details
    details = f"""
    <font size=12>
    🆔 <b>Booking ID:</b> {booking_id} <br/>
    📅 <b>Date & Time:</b> {formatted_date_time} <br/>
    🎟️ <b>Number of Tickets:</b> {ticket_count} <br/>
    </font>
    """
    elements.append(Paragraph(details, styles["Normal"]))
    elements.append(Spacer(1, 10))

    # Barcode Image
    barcode_img = Image(barcode_path, width=250, height=70)
    elements.append(barcode_img)
    elements.append(Spacer(1, 15))

    # Instructions
    instructions = Paragraph("""
    <font size=11 color='gray'>
    Please present this ticket at the venue for verification. <br/>
    Thank you for choosing our service! 🎉
    </font>
    """, styles["Italic"])
    elements.append(instructions)

    # Footer
    elements.append(Spacer(1, 30))
    footer = Paragraph("<b>📞 Customer Support: 7385877592</b>", styles["Normal"])
    elements.append(footer)

    # Build PDF
    doc.build(elements)

    # Clean up barcode image
    os.remove(barcode_path)

    return pdf_filename

def send_email(user_email, booking_id, date_time, ticket_count, username):
    sender_email = "myac1224567@gmail.com"
    app_password = "uqtcjgjxtcihwbqh"  # Use App Password
    subject = "Your Ticket Booking Confirmation"

    # Generate PDF ticket
    pdf_filename = generate_ticket_pdf(booking_id, date_time, ticket_count, username)

    # Email Content
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = user_email
    message["Subject"] = subject

    body = f"""
    Dear {username},

    Your ticket booking has been confirmed. Please find your ticket attached as a PDF.

    Booking ID: {booking_id}  
    Date & Time: {format_datetime(date_time)}  
    Number of Tickets: {ticket_count}

    Please present the attached ticket at the venue for verification.

    Best regards,  
    prasthana  
    Customer Support Team  
    📞 7385877592
    """
    message.attach(MIMEText(body, "plain"))

    # Attach PDF
    with open(pdf_filename, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename={pdf_filename}",
    )
    message.attach(part)

    try:
        # Connect to Gmail SMTP server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, user_email, message.as_string())
        server.quit()
        print("✅ Email sent successfully!")

    except Exception as e:
        print(f"❌ Failed to send email: {e}")

    # Clean up the PDF file
    os.remove(pdf_filename)

# # Example Usage
# send_email("user@example.com", "ABC123", "10-03-2025 17:00", 2, "John Doe")
