import os
from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
from google.generativeai import types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure Gemini API Key
# Make sure to set the GEMINI_API_KEY environment variable
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Error: GEMINI_API_KEY environment variable not set.")
    # You might want to exit or handle this more gracefully
    exit(1)


app = Flask(__name__)

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handles chatbot requests."""
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({"error": "Missing 'message' in request body"}), 400

    try:
        # Initialize the Gemini client implicitly through configure
        # No need to create a Client instance if genai.configure is used

        model_name = "gemini-1.5-flash" # Using gemini-1.5-flash as gemini-2.0-flash might not be available directly this way yet
        model = genai.GenerativeModel(model_name)

        # Prepare contents for the API call - simplified
        # The library often allows passing the prompt string directly
        contents = [user_message] # Pass the user message directly

        # Configuration for text generation
        generation_config = types.GenerationConfig(
            # response_mime_type="text/plain" # This seems deprecated or incorrect for GenerativeModel
            candidate_count=1,
            temperature=0.7 # Optional: Adjust creativity
        )

        # Use generate_content for a non-streaming response suitable for a simple API
        # Pass the simplified contents list
        response = model.generate_content(
            contents=contents, # Pass the user message string directly
            generation_config=generation_config
        )

        # Extract the text response
        if response.candidates and response.candidates[0].content.parts:
             bot_response = response.candidates[0].content.parts[0].text
        else:
             # Handle cases where the response might be empty or blocked
             bot_response = "Sorry, I couldn't generate a response."


        return jsonify({"response": bot_response})

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # Log the error details if needed
        # import traceback
        # traceback.print_exc()
        return jsonify({"error": "Failed to get response from Gemini API", "details": str(e)}), 500

if __name__ == '__main__':
    # Run the Flask app
    # Use 0.0.0.0 to make it accessible on the network if needed, otherwise 127.0.0.1
    # Debug=True is useful for development but should be False in production
    app.run(host='0.0.0.0', port=5000, debug=True)