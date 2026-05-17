"""
Proper model training with sklearn
"""
import pandas as pd
import numpy as np
import pickle
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

print("=" * 60)
print("MODEL TRAINING SCRIPT")
print("=" * 60)

# Load data
print("\n[1] Loading data...")
df = pd.read_csv('Crop_recommendation.csv')
print(f"    Loaded {len(df)} samples with {len(df.columns)} columns")
print(f"    Columns: {df.columns.tolist()}")

# Define encoding to match the notebook
crop_dict = {
    'rice': 1,
    'maize': 2,
    'cotton': 3,
    'orange': 4,
    'watermelon': 5,
    'grapes': 6,
    'mango': 7,
    'banana': 8,
    'pomegranate': 9,
    'mungbean': 10,
    'mothbeans': 11,
}

print("\n[2] Encoding labels...")
df['crop_id'] = df['label'].map(crop_dict)
print("    Label encoding:")
for crop, idx in sorted(crop_dict.items(), key=lambda x: x[1]):
    count = (df['crop_id'] == idx).sum()
    print(f"      {idx:2d}: {crop:15s} ({count:3d} samples)")

# Prepare features and target
print("\n[3] Preparing features...")
X = df[['N', 'P', 'K', 'ph']]
y = df['crop_id']

print(f"    Feature shape: {X.shape}")
print(f"    Target shape: {y.shape}")
print(f"    Feature ranges:")
for col in X.columns:
    print(f"      {col}: [{X[col].min():7.2f}, {X[col].max():7.2f}]")

# Split data
print("\n[4] Splitting data (80-20 train-test)...")
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"    Training: {len(X_train)} samples")
print(f"    Testing:  {len(X_test)} samples")

# Scale features
print("\n[5] Scaling features with MinMaxScaler...")
scaler = MinMaxScaler(feature_range=(0, 1))
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

print(f"    Scaler data_min_: {scaler.data_min_}")
print(f"    Scaler data_max_: {scaler.data_max_}")
print(f"    Scaler scale_:    {scaler.scale_}")

# Train model
print("\n[6] Training Random Forest Classifier...")
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=20,
    min_samples_split=5,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train_scaled, y_train)
print("    Model trained!")

# Evaluate
print("\n[7] Evaluating model...")
y_pred_train = model.predict(X_train_scaled)
y_pred_test = model.predict(X_test_scaled)

train_accuracy = accuracy_score(y_train, y_pred_train)
test_accuracy = accuracy_score(y_test, y_pred_test)

print(f"    Training accuracy: {train_accuracy:.4f} ({train_accuracy*100:.2f}%)")
print(f"    Testing accuracy:  {test_accuracy:.4f} ({test_accuracy*100:.2f}%)")

# Test predictions
print("\n[8] Testing specific examples from CSV...")
test_cases = [
    {'N': 90, 'P': 42, 'K': 43, 'ph': 6.502985292, 'expected': 1, 'name': 'Rice'},
    {'N': 85, 'P': 58, 'K': 41, 'ph': 7.038096361, 'expected': 1, 'name': 'Rice'},
    {'N': 60, 'P': 55, 'K': 44, 'ph': 7.840207144, 'expected': 1, 'name': 'Rice'},
]

# Reverse dict for display
id_to_crop = {v: k for k, v in crop_dict.items()}

for test in test_cases:
    X_test_sample = np.array([[test['N'], test['P'], test['K'], test['ph']]])
    X_scaled = scaler.transform(X_test_sample)
    pred = model.predict(X_scaled)[0]
    pred_name = id_to_crop[pred]
    expected_name = id_to_crop[test['expected']]
    match = "✓" if pred == test['expected'] else "✗"
    print(f"    {match} Input {test['name']} (N={test['N']}, P={test['P']}, K={test['K']}, pH={test['ph']:.2f})")
    print(f"         Expected: {test['expected']} ({expected_name}), Got: {pred} ({pred_name})")

# Save model and scaler
print("\n[9] Saving model and scaler...")
pickle.dump(model, open('model.pkl', 'wb'))
print("    ✓ Saved model.pkl")

pickle.dump(scaler, open('minmaxscaler.pkl', 'wb'))
print("    ✓ Saved minmaxscaler.pkl")

# Save crop mapping for reference
with open('crop_mapping.txt', 'w') as f:
    f.write("Crop ID Mapping:\n")
    f.write("=" * 40 + "\n")
    for idx, crop in sorted(id_to_crop.items()):
        f.write(f"{idx:2d}: {crop}\n")
print("    ✓ Saved crop_mapping.txt")

print("\n" + "=" * 60)
print("✓ MODEL TRAINING COMPLETE!")
print("=" * 60)
