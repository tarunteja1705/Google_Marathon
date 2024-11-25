from dotenv import load_dotenv
import streamlit as st
import os
from PIL import Image
import hashlib
import firebase_admin
from firebase_admin import credentials, db
import google.generativeai as genai

# Load environment variables
load_dotenv()

st.set_page_config(page_title="Gemini Image Demo")

# Firebase initialization
try:
    if not firebase_admin._apps:  # Check if Firebase app is already initialized
        credentials_dict = {
            "type": "service_account",
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
            "universe_domain": "googleapis.com"
        }
        cred = credentials.Certificate(credentials_dict)
        firebase_admin.initialize_app(cred, {
            "databaseURL": os.getenv("FIREBASE_DATABASE_URL")
        })
        st.success("Firebase connected successfully!")
    else:
        st.info("Firebase app already initialized.")
except Exception as e:
    st.error(f"Error initializing Firebase: {e}")
    st.stop()

# Gemini API configuration
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
except Exception as e:
    st.error(f"Error initializing Gemini API: {e}")
    st.stop()

# Function to get Gemini response
def get_gemini_response(input_text, image_data, prompt):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([input_text, image_data[0], prompt])
        return response.text
    except Exception as e:
        st.error(f"Error generating response: {e}")
        return None

# Function to prepare the uploaded image for API
def input_image_setup(uploaded_file):
    try:
        if uploaded_file is not None:
            bytes_data = uploaded_file.getvalue()
            image_parts = [
                {
                    "mime_type": uploaded_file.type,
                    "data": bytes_data
                }
            ]
            return image_parts
        else:
            raise FileNotFoundError("No file uploaded")
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None

# Function to encode image in binary format for database storage/lookup
def encode_image_binary(uploaded_file):
    try:
        return hashlib.sha256(uploaded_file.getvalue()).hexdigest()
    except Exception as e:
        st.error(f"Error encoding image to binary: {e}")
        return None

# Function to store the response in Firebase under the binary-encoded identifier
def store_response_in_firebase(identifier, response, encoding):
    try:
        response_ref = db.reference(f"/responses/{identifier}")
        response_ref.set({"response": response, "encoding": encoding})
        st.success(f"Response successfully stored in Firebase under identifier: {identifier}")
    except Exception as e:
        st.error(f"Error storing response in Firebase: {e}")

# Function to check Firebase for existing response
def check_existing_response(image_id):
    try:
        response_ref = db.reference(f"/responses/{image_id}")
        response = response_ref.get()
        return response
    except Exception as e:
        st.error(f"Error checking Firebase for existing response: {e}")
        return None

# Streamlit App UI
st.header("Gemini Application")

# Main App
input_text = st.text_input("Input Prompt: ", key="input")
uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
image = None

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", use_container_width=True)

submit = st.button("Generate Insights")

input_prompt = """
Take the persona of a Dashboard analyzer.
There will be multiple charts or graphs in the input data.
List down all the types of charts.
List down all the variables and their values in the input data.
Generate a summary of the input data.
The output should be in the form of the JSON given below:

Output: {
  "Charts": { },
  "Variables": {
    "Variable1":{
    "Sub Variable1": "Value1",
    "Sub Variable2": "Value2"}
    "Variable2":{
    "Sub Variable1": "Value1",
    "Sub Variable2": "Value2"}
    ...
  },
  "Summary": "Summary of the input data in pointers"
}

If you are unable to extract the data, strictly give the response as Null. Do not print anything else
In charts the key is the header of the chart and value is description of the chart
for variables try to find out all the variables and their values


"""

if submit:
    if not input_text:
        st.warning("Please enter an input prompt.")
    elif not uploaded_file:
        st.warning("Please upload an image.")
    else:
        image_data = input_image_setup(uploaded_file)
        if image_data:
            # Generate a binary-encoded identifier for the image
            image_id = encode_image_binary(uploaded_file)
            if image_id:
                # Check if a response already exists in Firebase
                existing_response = check_existing_response(image_id)
                if existing_response:
                    st.info("Response already exists. Fetching from Firebase.")
                    response = existing_response.get("response", "No response found")
                else:
                    st.info("No existing response found. Generating a new one.")
                    response = get_gemini_response(input_prompt, image_data, input_text)
                    if response:
                        # Store the new response in Firebase
                        store_response_in_firebase(image_id, response, image_id)

                if response:
                    st.subheader("The Response is")
                    st.write(response)
                else:
                    st.error("No response generated. Check inputs and try again.")
