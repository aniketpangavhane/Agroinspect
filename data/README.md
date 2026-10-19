# Data layout

The current user-supplied CSV remains at the repository root as `Crop_recommendation.csv` so no user data is moved or overwritten during this refactor.

The configured pipeline treats that file as raw, read-only input and writes a canonical cleaned copy to `data/curated/maharashtra_crop_recommendation_v1.csv`. Generated curated data is ignored by Git because it is reproducible from the raw file plus contract.

When a verified external source is selected, place an immutable source snapshot under `data/raw/`, add a new manifest under `data/metadata/`, update the training configuration, and do not overwrite the older source version.
