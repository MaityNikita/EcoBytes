import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os

def send_weekly_digest(user, footprint_log):
    # In a real application, you would configure an SMTP server 
    # (like SendGrid, Mailgun, or AWS SES) and pull from env vars.
    # For now, we print to stdout to simulate sending.
    
    fp_data = json.loads(footprint_log.raw_data)
    total_kg = footprint_log.total_kg
    
    html_content = f"""
    <html>
      <body style="font-family: sans-serif; color: #333; background: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px;">
          <h2 style="color: #2E7D52;">EcoBytes Weekly Digest</h2>
          <p>Hi {user.name},</p>
          <p>Here is your digital carbon footprint update for this week:</p>
          
          <div style="background: #e8f5e9; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
            <h1 style="color: #1A4D32; margin: 0;">{total_kg:.1f} kg CO₂e</h1>
            <p style="margin: 5px 0 0; color: #2E7D52;">Generated this week</p>
          </div>
          
          <h3>Top Recommendation:</h3>
          <p>Consider deleting unused large files from your Google Drive. 
          Idle data requires constant server cooling and power.</p>
          
          <hr style="border: 1px solid #eee; margin: 30px 0;">
          <p style="font-size: 0.8rem; color: #888;">
            You are receiving this because you enabled weekly digests in EcoBytes. 
            <a href="#">Manage preferences</a>
          </p>
        </div>
      </body>
    </html>
    """
    
    print(f"--- MOCK EMAIL TO {user.email} ---")
    print("Subject: Your Weekly Digital Footprint")
    print(html_content)
    print("------------------------------------")
    
    # Example of actual sending logic:
    # msg = MIMEMultipart('alternative')
    # msg['Subject'] = "Your Weekly Digital Footprint"
    # msg['From'] = "hello@ecobytes.app"
    # msg['To'] = user.email
    # part = MIMEText(html_content, 'html')
    # msg.attach(part)
    # with smtplib.SMTP('smtp.mailgun.org', 587) as server:
    #     server.login('user', 'pass')
    #     server.sendmail(msg['From'], [msg['To']], msg.as_string())
