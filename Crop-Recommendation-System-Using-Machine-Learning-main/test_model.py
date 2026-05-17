import pickle
import numpy as np

model = pickle.load(open('model.pkl', 'rb'))
ms = pickle.load(open('minmaxscaler.pkl', 'rb'))

# Original order: N, P, K, ph
print("Testing original order (N, P, K, ph):")
test1 = np.array([[90, 42, 43, 6.502985292]])
try:
    scaled1 = ms.transform(test1)
    pred1 = model.predict(scaled1)
    print(f"  N=90, P=42, K=43, pH=6.5 -> Prediction: {pred1[0]}")
except Exception as e:
    print(f"  Error: {e}")

# Check scaler properties
print("\n\nScaler properties:")
print(f"Data min: {ms.data_min_}")
print(f"Data max: {ms.data_max_}")
print(f"Feature range: {ms.feature_range}")
print(f"Scale: {ms.scale_}")
