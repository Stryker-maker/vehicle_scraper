# Vehicle Scraper

Automated AutoTrader.ca scraper for Ford F-350 diesel trucks. Searches across Western Canada, ranks results by price, mileage, and driving distance, and saves results as CSV files.

---

## What It Does

- Searches AutoTrader.ca across 29 cities in AB, SK, and BC
- Filters by year, price, engine, and fuel type
- Calculates **driving distance** using OpenRouteService (not straight-line)
- Ranks results: **Price 60% | Mileage 25% | Distance 15%**
- Saves ranked results to `data/` as a timestamped CSV
- Runs automatically every Monday at 8:00 AM UTC

---

## Repository Structure

```
vehicle_scraper/
├── scraper.py                        # Main script
├── config.json                       # Search criteria (edit this)
├── data/                             # CSV results saved here
└── .github/
    └── workflows/
        └── scrape.yml                # GitHub Actions automation
```

---

## One-Time Setup

### Step 1 — Add your OpenRouteService API key as a GitHub Secret

1. Open your repository on GitHub (browser or mobile)
2. Tap **Settings** → **Secrets and variables** → **Actions**
3. Tap **New repository secret**
4. Name: `ORS_API_KEY`
5. Value: paste your OpenRouteService API key
6. Tap **Add secret**

### Step 2 — Make sure the `data/` folder exists in the repo

GitHub Actions needs this folder to save CSV files. Create a placeholder:

1. In your repo, tap **Add file** → **Create new file**
2. Name it: `data/.gitkeep`
3. Leave it blank and commit it

### Step 3 — Trigger a manual run to test

1. Go to **Actions** tab in your repo
2. Select **Weekly AutoTrader Scrape**
3. Tap **Run workflow** → **Run workflow**
4. Watch the logs — results will appear in `data/` when complete

---

## Customizing Search Criteria

Edit `config.json` to change what you're searching for:

```json
{
  "make": "Ford",
  "model": "F-350",
  "min_year": 2015,
  "max_year": 2023,
  "max_price": 60000,
  "fuel": "Diesel",
  "engine": "6.7L",
  "max_distance_km": 800,
  "max_results": 50,
  "ranking_weights": {
    "price": 0.60,
    "mileage": 0.25,
    "distance": 0.15
  }
}
```

---

## Distance Resolution Priority

For each listing, driving distance is calculated using this priority:

1. **Dealer street address** — most accurate
2. **Listing city center** — used if no address available
3. **Nearest search city center** — fallback if city can't be geocoded

The `distance_method` column in the CSV tells you which method was used for each result.

---

## Running Locally (Pydroid 3)

1. Install dependencies in Pydroid 3's pip manager:
   - `requests`
   - `beautifulsoup4`
   - `geopy`

2. Set your API key — add this line temporarily at the top of `scraper.py` for local testing (remove before committing):
   ```python
   os.environ["ORS_API_KEY"] = "your_key_here"
   ```

3. Run `scraper.py`

---

## CSV Output Columns

| Column | Description |
|---|---|
| rank | Final ranking (1 = best) |
| year | Model year |
| make | Ford |
| model | F-350 |
| trim | Trim level |
| price | Listed price (CAD) |
| mileage | Odometer in km |
| engine | Engine displacement |
| fuel | Fuel type |
| dealer | Dealership name |
| dealer_address | Dealer street address |
| location | City, Province |
| distance_km | Driving distance from Red Deer |
| distance_method | How distance was calculated |
| listing_id | AutoTrader listing ID |
| url | Direct link to listing |
| score | Ranking score (lower = better) |
