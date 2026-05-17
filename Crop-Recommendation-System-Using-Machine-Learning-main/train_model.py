"""
Clean model training script to ensure correct model and scaler generation
"""
import numpy as np
import pandas as pd
import pickle
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# Load the data
print("Loading data...")
crop = pd.read_csv("Crop_recommendation.csv")
print(f"Dataset shape: {crop.shape}")
print(f"Unique crops: {crop['label'].unique()}")
print(f"Crop value counts:\n{crop['label'].value_counts()}\n")

# Create encoding dictionary based on ACTUAL unique labels in data
unique_crops = sorted(crop['label'].unique())
crop_dict = {crop_name: idx for idx, crop_name in enumerate(unique_crops, start=1)}
print(f"Crop encoding dictionary:\n{crop_dict}\n")

# Encode labels
crop['crop_num'] = crop['label'].map(crop_dict)
print(f"Sample of encoded data:\n{crop.head()}\n")

# Prepare features and target
X = crop.drop(['label', 'crop_num'], axis=1)
y = crop['crop_num']

print(f"Features shape: {X.shape}")
print(f"Features columns: {X.columns.tolist()}")
print(f"Target shape: {y.shape}")
print(f"Feature values range:\n{X.describe()}\n")

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"Training set size: {X_train.shape[0]}")
print(f"Test set size: {X_test.shape[0]}\n")

# Scale features
print("Scaling features...")
ms = MinMaxScaler()
X_train_scaled = ms.fit_transform(X_train)
X_test_scaled = ms.transform(X_test)
print(f"Scaler min values: {ms.data_min_}")
print(f"Scaler max values: {ms.data_max_}\n")

# Train model
print("Training Random Forest model...")
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train_scaled, y_train)

# Evaluate
y_pred = model.predict(X_test_scaled)
accuracy = accuracy_score(y_test, y_pred)
print(f"Model Accuracy: {accuracy:.4f}\n")

# Test with a specific example from CSV
print("Testing with row from CSV (should predict rice=1):")
test_input = np.array([[90, 42, 43, 6.502985292]])
test_scaled = ms.transform(test_input)
test_pred = model.predict(test_scaled)
print(f"Input: N=90, P=42, K=43, pH=6.502985292")
print(f"Prediction: {test_pred[0]} (should be 1=Rice)\n")

# Save model and scaler
print("Saving model and scaler...")
pickle.dump(model, open('model.pkl', 'wb'))
pickle.dump(ms, open('minmaxscaler.pkl', 'wb'))
print("✓ model.pkl saved")
print("✓ minmaxscaler.pkl saved")

# Also save the crop mapping for reference
with open('crop_mapping.txt', 'w') as f:
    for crop_name, crop_num in sorted(crop_dict.items(), key=lambda x: x[1]):
        f.write(f"{crop_num}: {crop_name}\n")
print("✓ crop_mapping.txt saved\n")

print("Training complete!")
