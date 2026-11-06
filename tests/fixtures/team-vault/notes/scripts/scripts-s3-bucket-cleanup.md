# Runbook: Clean Up S3 Buckets Safely

Tags: #aws #scripts

## Before Deleting Anything

Check who owns the bucket via the `owner` tag, whether versioning is on, and whether it is referenced by Terraform, CloudFront or a Glue table. Buckets with `prevent_destroy` must be unprotected through a PR.

## Measure First

```bash
aws s3 ls s3://acme-dev-scratch --recursive --summarize --human-readable | tail -2
aws s3api list-object-versions --bucket acme-dev-scratch --query 'length(DeleteMarkers)'
```

Versioned buckets keep old data and delete markers; plain `aws s3 rm --recursive` will not free the space.

## Empty a Versioned Bucket

Use a lifecycle rule that expires current and noncurrent versions after 1 day instead of a script when the bucket is large (over 1 million objects); S3 removes the data itself and you avoid request charges. Then delete the bucket once it reports empty.

## Abort Stale Multipart Uploads

```bash
aws s3api list-multipart-uploads --bucket acme-prod-raw --query 'Uploads[?Initiated<`2025-01-01`].[Key,UploadId]'
```

Abort them with `aws s3api abort-multipart-upload`, or add a lifecycle rule `AbortIncompleteMultipartUpload` with `DaysAfterInitiation: 3`.
