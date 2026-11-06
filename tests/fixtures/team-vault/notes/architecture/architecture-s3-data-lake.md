# S3 Data Lake Layout

Tags: #aws #architecture

## Buckets

The data lake has three buckets per environment: `acme-<env>-raw`, `acme-<env>-curated` and `acme-<env>-athena-results`. All have versioning enabled, block public access on, and default encryption with SSE-KMS using the environment data key with bucket keys turned on to reduce KMS request charges.

## Prefix Layout

Raw data lands under `source=<system>/dt=YYYY-MM-DD/` so Athena partitions prune by date. Curated data is Parquet, snappy-compressed, targeted at 128-256 MB files. Small files are compacted nightly by a Glue job; a prefix with thousands of tiny objects is the usual cause of slow queries.

## Lifecycle Rules

Raw objects transition to Standard-IA after 30 days and Glacier Instant Retrieval after 90, and expire after 400 days. Noncurrent versions expire after 14 days. Incomplete multipart uploads are aborted after 3 days, a rule that recovered about 2 TB when first enabled. Athena result objects expire after 7 days.

## Access

Writers use IRSA roles scoped to a prefix. Analysts read through Athena with an SSO-backed role; direct bucket reads are denied by bucket policy except for the pipeline roles. Cross-account sharing is done through bucket policy plus KMS key grants, never public ACLs.
