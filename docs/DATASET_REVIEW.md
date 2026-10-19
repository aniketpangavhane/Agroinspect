# Dataset review: current local source

## What was found

`Crop_recommendation.csv` now contains 4,513 rows and 11 columns:

`District_Name`, `Soil_color`, `Nitrogen`, `Phosphorus`, `Potassium`, `pH`, `Rainfall`, `Temperature`, `Crop`, `Fertilizer`, and `Link`.

It covers five Maharashtra districts and 16 crop labels. There are no null values and no fully duplicate rows. The contract normalizes one known quality issue: `Soil_color` contains both `Red` and `Red `, which should be the same category.

## What can be modelled now

For the current prototype, use only these pre-decision inputs:

- district
- soil colour
- nitrogen, phosphorus, potassium, and pH
- rainfall and temperature

The user has confirmed that `Crop` means the recommended-crop label. The model predicts that supplied label from the listed inputs; it does not prove that the prediction is the agronomically best crop. Treat the result as a prototype prediction, not verified advice or a promise of crop success.

## Fields deliberately excluded

| Field | Why it is excluded |
| --- | --- |
| `Fertilizer` | It is likely selected after crop choice and is strongly associated with crop. Including it would create data leakage and would turn an input requirement into circular advice. |
| `Link` | It is untrusted external metadata. In this file, every link maps to one crop label, making it direct target leakage. It is never sent to the model or returned by the API. |

## Why this is not production data yet

The file does not record source/provider, licence, collection date, season, year, plot or farm identity, coordinates, irrigation, crop history, measurement units/methods, yield, price, profit, or farmer-verified outcome. Its numerical values are highly discretized (for example, only seven pH and seven temperature values), which is a warning sign that it may be a reference/generated dataset rather than field observations.

Do not use its evaluation score to claim accuracy for unseen farms, crops, seasons, or districts.

## Required next data fields

At minimum, a production training record should include:

```text
plot_id (pseudonymous), geography/geohash, district, season, crop year,
soil test date + laboratory + units, N/P/K/pH/organic carbon,
historical weather and forecast timestamp, irrigation, prior crop,
candidate crop, actual yield, input cost, sale price, and outcome quality flag.
```

The correct long-term modelling unit is a candidate crop in a specific location and season with an observed outcome—not merely a row labelled with a crop name.
