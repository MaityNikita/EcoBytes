# EcoBytes: Digital Footprint & Carbon Tracker
## One-Line Pitch
A transparent dashboard that visualizes your cross-platform digital usage and carbon footprint to promote digital wellness and privacy.

## The Problem
In an increasingly connected world, we interact with dozens of services—like Google Drive, Gmail, and YouTube—without understanding the environmental impact of our data usage or the extent of our digital footprint. This lack of visibility makes it difficult to manage personal privacy and environmental impact.

## Tech Stack
EcoBytes is built with a modular, secure architecture:

Backend: Flask (v3.0.3), SQLAlchemy (ORM).

Authentication: Google OAuth2 (via Authlib).

Intelligence: Custom carbon_engine.py for translating API telemetry into kg CO₂e.

Frontend: Jinja2 templating, Vanilla CSS3/JS for dynamic UI.

Deployment: Gunicorn (Production-ready).

## Features
Secure OAuth Integration: Authenticate safely using your Google account to access usage data.

Carbon Calculator: Real-time translation of your cloud storage (GBs), emails, and streaming into environmental impact scores.

Interactive Dashboard: Visualize your footprint with dynamic charts and tailored reduction recommendations.

## Installation & Running Locally
Clone the repository:

Bash
git clone https://github.com/MaityNikita/EcoBytes.git

cd EcoBytes
Create a virtual environment:


Bash
python app.py

## Security & Privacy
EcoBytes uses Google's official OAuth2 protocols to ensure that your credentials remain secure. The application only requests the specific scopes required to calculate your footprint and does not store personal sensitive content.

## Credits
Developer: Nikita Maity

Event: Virtual: PromptWars Hackathon


## Deployed Link -: https://ecobytes1.onrender.com/

https://github.com/user-attachments/assets/bb5d04ac-4eca-4d3b-9bda-760b6d9cb176



