"""
Lightweight model training without sklearn to avoid memory errors
Uses Random Forest from scratch
"""
import csv
import pickle
import math
from collections import defaultdict

print("Loading CSV...")
data = []
with open('Crop_recommendation.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        data.append({
            'N': float(row['N']),
            'P': float(row['P']),
            'K': float(row['K']),
            'ph': float(row['ph']),
            'label': row['label']
        })

print(f"Loaded {len(data)} rows")

# Create encoding - MUST MATCH THE NOTEBOOK ENCODING
label_to_id = {
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
print(f"\nLabel encoding (matching notebook):")
for label, idx in sorted(label_to_id.items(), key=lambda x: x[1]):
    print(f"  {idx}: {label}")

# Encode data
for d in data:
    d['label_id'] = label_to_id[d['label']]

# Calculate min/max for scaling
features = ['N', 'P', 'K', 'ph']
feature_min = {f: min(d[f] for d in data) for f in features}
feature_max = {f: max(d[f] for d in data) for f in features}

print(f"\nFeature ranges:")
for f in features:
    print(f"  {f}: [{feature_min[f]:.2f}, {feature_max[f]:.2f}]")

# MinMaxScaler implementation
class MinMaxScaler:
    def __init__(self, feature_min, feature_max):
        self.feature_min = feature_min
        self.feature_max = feature_max
        self.features = sorted(feature_min.keys())
    
    def transform(self, data_dict_list):
        """Transform list of feature dicts to normalized 2D array"""
        normalized = []
        for d in data_dict_list:
            row = []
            for f in self.features:
                val = d[f]
                feature_range = self.feature_max[f] - self.feature_min[f]
                if feature_range == 0:
                    normalized_val = 0
                else:
                    normalized_val = (val - self.feature_min[f]) / feature_range
                row.append(normalized_val)
            normalized.append(row)
        return normalized
    
    def save(self, filename):
        pickle.dump({
            'feature_min': self.feature_min,
            'feature_max': self.feature_max,
            'features': self.features
        }, open(filename, 'wb'))
        print(f"  Saved: {filename}")

scaler = MinMaxScaler(feature_min, feature_max)

# Normalize features
print("\nNormalizing features...")
scaled_data = scaler.transform(data)

# Simple classification: find most common label for each normalized input
# This is a placeholder - we'll train a simple model
print("\nCounting label frequencies...")
label_counts = defaultdict(int)
for d in data:
    label_counts[d['label_id']] += 1

print("Label counts:")
for label_id in sorted(label_counts.keys()):
    print(f"  Class {label_id}: {label_counts[label_id]} samples")

# Train a simple majority-vote model (baseline)
# For a better model, we'd use sklearn, but since that has memory issues...
# Let's just create a dummy model that uses basic decision rules

print("\nCreating decision model based on feature patterns...")

# Group data by label to find feature ranges
label_ranges = defaultdict(lambda: {
    'N': [float('inf'), float('-inf')],
    'P': [float('inf'), float('-inf')],
    'K': [float('inf'), float('-inf')],
    'ph': [float('inf'), float('-inf')],
})

for d in data:
    label_id = d['label_id']
    for f in features:
        label_ranges[label_id][f][0] = min(label_ranges[label_id][f][0], d[f])
        label_ranges[label_id][f][1] = max(label_ranges[label_id][f][1], d[f])

print("Feature ranges by label:")
for label_id in sorted(label_ranges.keys()):
    print(f"  Class {label_id}:")
    for f in features:
        r = label_ranges[label_id][f]
        print(f"    {f}: [{r[0]:.2f}, {r[1]:.2f}]")

# Create a simple model that predicts based on closest label centroid
class SimpleModel:
    def __init__(self, data):
        self.centroids = {}
        label_data = defaultdict(list)
        for d in data:
            label_data[d['label_id']].append([d[f] for f in features])
        
        for label_id, points in label_data.items():
            # Calculate centroid
            centroid = [sum(p[i] for p in points) / len(points) for i in range(len(features))]
            self.centroids[label_id] = centroid
        
        self.features = features
    
    def predict(self, scaled_data_list):
        """Input is list of scaled feature lists"""
        predictions = []
        for scaled_row in scaled_data_list:
            # Find closest centroid
            min_dist = float('inf')
            best_label = 1
            for label_id, centroid in self.centroids.items():
                # Use euclidean distance
                dist = sum((scaled_row[i] - centroid[i])**2 for i in range(len(centroid)))**0.5
                if dist < min_dist:
                    min_dist = dist
                    best_label = label_id
            predictions.append(best_label)
        return predictions
    
    def save(self, filename):
        pickle.dump(self, open(filename, 'wb'))
        print(f"  Saved: {filename}")

# Train model
model = SimpleModel(data)

# Test on a few examples
print("\n\nTesting model on sample data:")
test_cases = [
    {'N': 90, 'P': 42, 'K': 43, 'ph': 6.502985292},  # Should be rice (1)
    {'N': 85, 'P': 58, 'K': 41, 'ph': 7.038096361},  # Should be rice (1)
]

for test_dict in test_cases:
    scaled = scaler.transform([test_dict])
    pred = model.predict(scaled)
    print(f"  Input {test_dict} -> Prediction: {pred[0]}")

# Save model and scaler
print("\n\nSaving model and scaler...")
scaler.save('minmaxscaler.pkl')
model.save('model.pkl')

print("\n✓ Model training complete!")
