from pathlib import Path

from flask import Flask, request, render_template_string
import numpy as np
import pickle

BASE_DIR = Path(__file__).resolve().parent

# Load the model and MinMaxScaler
with (BASE_DIR / 'model.pkl').open('rb') as model_file:
    model = pickle.load(model_file)

with (BASE_DIR / 'minmaxscaler.pkl').open('rb') as scaler_file:
    ms = pickle.load(scaler_file)

# Create Flask app
app = Flask(__name__)

@app.route('/')
def index():
    # Manually load the HTML content from the file
    with (BASE_DIR / 'index.html').open('r', encoding='utf-8') as f:
        html_content = f.read()
    return render_template_string(html_content)

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # Get the form values and convert to float
        N = float(request.form['Nitrogen'])
        P = float(request.form['Phosphorus'])
        K = float(request.form['Potassium'])
        ph = float(request.form['Ph'])

        # Validate input ranges (basic sanity check)
        if N < 0 or P < 0 or K < 0 or ph < 0 or ph > 14:
            result = "Error: Please enter valid values. pH must be between 0-14, and N, P, K must be non-negative."
        else:
            # Convert form data to array
            feature_list = [N, P, K, ph]
            single_pred = np.array(feature_list).reshape(1, -1)

            # Scale the features using the pre-fitted MinMaxScaler (CRITICAL: use transform, not fit_transform)
            final_features = ms.transform(single_pred)

            # Make prediction
            prediction = model.predict(final_features)
            
            # Get the predicted crop number
            pred_crop_num = int(prediction[0])

            # Crop mapping (must match the training data)
            crop_dict = {
                1: "Rice",
                2: "Maize",
                3: "Cotton",
                4: "Orange",
                5: "Watermelon",
                6: "Grapes",
                7: "Mango",
                8: "Banana",
                9: "Pomegranate",
                10: "Mungbean",
                11: "Mothbeans"
            }

            # Get the result
            if pred_crop_num in crop_dict:
                crop = crop_dict[pred_crop_num]
                result = "{} is the best crop to be cultivated right there".format(crop)
            else:
                result = "Sorry, we could not determine the best crop to be cultivated with the provided data."

        # Manually load the HTML content from the file
        with (BASE_DIR / 'index.html').open('r', encoding='utf-8') as f:
            html_content = f.read()

        return render_template_string(html_content, result=result)
    except ValueError:
        with (BASE_DIR / 'index.html').open('r', encoding='utf-8') as f:
            html_content = f.read()
        return render_template_string(html_content, result="Error: Please enter valid numeric values for all fields.")
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    app.run(debug=True)
