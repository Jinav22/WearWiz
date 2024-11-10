WearWiz: Your AI-Powered Wardrobe Assistant 👚👗👕
Welcome to WearWiz! This project combines advanced AI capabilities to help you maximize the utility of your wardrobe and explore new styling possibilities. Using image segmentation, classification, and personalized recommendations, WearWiz makes dressing smarter, easier, and more fun.

🌟 Objectives
The WearWiz project aims to create an AI-driven system with the following key objectives:

1.Segmentation and Classification
Accurately segment and classify clothing items within user-uploaded images, identifying various wardrobe components such as tops, bottoms, and accessories.

2.Daily Recommendations
Provide daily, personalized outfit suggestions based on user-defined preferences, contextual factors (like weather and occasion), and the compatibility of items within the wardrobe.

3.Outfit Generation
Generate a diverse array of outfit combinations to maximize wardrobe utility, encouraging users to discover new ways to style existing pieces.

4.Future Extensions
Enable potential expansions in sustainable fashion recommendations, eco-conscious choices through carbon footprint tracking, and integration with e-commerce platforms for targeted purchases.

🚀 Getting Started
This guide will walk you through setting up WearWiz on your local machine, from installing dependencies to running the web app and API services. Make sure you have Python and Node.js installed before you start.

📋 Prerequisites
Python 3.7+
pip (Python package installer)

📁 Project Structure
WearWiz runs on two servers:

Flask server (in app.py) manages the web application, user interface, and routing.
Uvicorn server (in api_Service.py) runs the FastAPI-powered API, providing high-performance asynchronous API calls for seamless data handling.

⚙️ Installation & Setup
Follow these steps to install and set up WearWiz on your local environment.

Step 1: Clone the Repository
Clone the WearWiz GitHub repository to your local machine:

'''bash
git clone https://github.com/your-username/wearwiz.git
cd wearwiz

Step 2: Install Backend (Python) Dependencies
Navigate to the backend directory and install the required Python libraries using the following command:

'''bash
pip install -r requirements.txt
Dependencies

Here’s a list of essential libraries and their versions for the WearWiz project:
1. chromadb: 0.5.18
2. groq: 0.11.0
3. fashion-clip: 0.2.2
4. torch: 2.5.1
5. pillow: 11.0.0
6. Flask: 3.0.3
7. Werkzeug: 3.1.2
8. fastapi: 0.115.4
9. uvicorn: 0.32.0
10. requests: 2.32.3
11. python-multipart: 0.0.17
These libraries support image processing, server communication, and API handling.

🛠 Running the Code
Once everything is installed, follow these steps to start both the Flask and Uvicorn servers.

Step 1: Start the Flask Server
The Flask server, responsible for the web application, is defined in app.py. Run the following command to start it:

'''bash
python app.py
After running this, you should see the Flask server starting on 'http://localhost:5000'.

Step 2: Start the FastAPI (Uvicorn) Server
The FastAPI server, defined in api_Service.py, manages the API functionality. Start it with Uvicorn using this command:

'uvicorn api_Service:app --host 0.0.0.0 --port 8000'
Once started, the FastAPI server will be available at 'http://localhost:8000'.

🌐 Interacting with WearWiz
1. Access the Web Application: Open a browser and go to 'http://localhost:5000' to access the WearWiz interface.
2. API Documentation: Visit 'http://localhost:8000/docs' to explore the API endpoints and test them directly through FastAPI’s interactive documentation.

🔑 Getting Your Groq API Key
To integrate with the Groq API, follow these steps to obtain your API key:

1. Log in to Groq: Go to Groq Developer Console(https://console.groq.com/login) and sign in or create an account.
2. Access API Management: In the Developer Console, navigate to the API Management section.
3. Generate API Key: Select "Generate Key," copy the key, and store it securely. You’ll use this in the WearWiz app for accessing Groq’s services.

🌱 Future Extensions
WearWiz is designed with future scalability in mind. Here are some ideas for enhancing the app:
