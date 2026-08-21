

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

## done
- extraction api
- api doc
- support for multi image format 
- deployed to gcp 
- ci / cd added
## todo 
- refactor code 
- dwar system diagram micro or something else
- security check
- optimization
- script for demo video ( points are mention in the task pdf + study bit about gcp and github action ci/cd with gcp)
