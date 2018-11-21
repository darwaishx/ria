# PoC Tool to Analyze Batch of Images using Amazon Rekognition

## Prerequisites
- Python
- AWS CLI

## How to run RIA

- Follow one the formats below. input-bucket is required, whereas all other parameters are optional.
    - python3 ria.py --input-bucket your-bucket
    - python3 ria.py --input-bucket your-bucket --input-directory your-input-directory --output-bucket your-bucket --output-directory your-output-directory --min-confidence 50 --collection-id your-collection --s3-expiration-time 3600 --no-csv

## Output UI
![](assets/ria-html.png)

## CSV Export of Metadata
![](assets/ria-csv.png)
