

deploy from cli

```bash

gcloud run deploy fast-ocr \
  --source . \
  --region us-central1 \
  --allow-unauthenticated


```


## run without docker

```bash

source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload

```