# GCP setup

This API uses **Cloud Vision** for OCR and **Firestore** to cache results by image hash. Use the same GCP project for both.

Set the project id once:

```bash
export PROJECT_ID=fast-oct   # must match GOOGLE_CLOUD_PROJECT in .env
gcloud config set project "$PROJECT_ID"
```

## 1. Enable APIs

```bash
gcloud services enable \
  vision.googleapis.com \
  firestore.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  --project="$PROJECT_ID"
```

`run` and `cloudbuild` are only required if you deploy to Cloud Run from source.

## 2. Firestore database (once)

Create a **Native** mode database. Skip this if the project already has one. Mode cannot be changed later. The `ocr_results` collection is **not** created here — the first successful OCR cache write creates it.

```bash
gcloud firestore databases create \
  --location=nam5 \
  --type=firestore-native \
  --project="$PROJECT_ID"
```

`nam5` is US multi-region (fits Cloud Run in `us-central1`). If the command says the database already exists, continue.

## 3. Run locally

Application Default Credentials (ADC), same as Vision:

```bash
gcloud auth application-default login
```

Copy [`.env.example`](.env.example) to `.env` and set:

```bash
GOOGLE_CLOUD_PROJECT=fast-oct
FIRESTORE_COLLECTION=ocr_results
```

Leave `GOOGLE_APPLICATION_CREDENTIALS` unset when using ADC.

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

```bash
curl -X POST -F "image=@sample-images/image1.JPG" http://localhost:8080/extract-text
```

First request: Vision + Firestore save (cache miss). Same image again: Firestore only (cache hit). Logs:

```
OcrService cache lookup hash=…
OcrService cache miss, calling VisionService
```

or `OcrService cache hit`.

If Firestore is missing or IAM is wrong, logs show `cache lookup failed` / `cache save failed` and OCR still runs (fail open).

## 4. Cloud Run

The default Compute Engine service account needs Firestore access:

```bash
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user"
```

`roles/datastore.user` is read/write for Firestore. Vision typically already works with this default account on Cloud Run.

Deploy:

```bash
gcloud run deploy fast-ocr \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --project="$PROJECT_ID" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},FIRESTORE_COLLECTION=ocr_results"
```

On Cloud Run, ADC is the service account; do not mount a JSON key.

CI/CD on `main` is [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) (Workload Identity Federation → Cloud Run `us-central1`). After that path is used, grant `roles/datastore.user` to the **runtime** service account of the Cloud Run service if it is not the default Compute SA.

## 5. Check

| Check | Command / place |
| --- | --- |
| Vision API enabled | `gcloud services list --enabled --project="$PROJECT_ID" \| grep vision` |
| Firestore API enabled | `gcloud services list --enabled --project="$PROJECT_ID" \| grep firestore` |
| Database exists | Firebase / GCP console → Firestore |
| Collection appears | After first cache miss: collection `ocr_results`, document id = SHA-256 of the image bytes |
| Local auth | `gcloud auth application-default print-access-token` succeeds |
