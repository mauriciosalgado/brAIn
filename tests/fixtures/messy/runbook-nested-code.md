# Rotate the signing keys

Tags: #security #runbook

Follow every step in order. Do not skip the verification after each step.

## Procedure

1. Export the current key id:

   ```bash
   # the id is the part after the slash
   KEY_ID=$(aws kms list-aliases --query "Aliases[?AliasName=='alias/signing'].TargetKeyId" --output text)
   echo "$KEY_ID"
   ```

2. Create the new key and capture its id:

   ```bash
   NEW_ID=$(aws kms create-key --description "signing $(date +%F)" --query KeyMetadata.KeyId --output text)
   # the policy is a heredoc that itself contains a fence-looking line
   cat <<'EOF' > policy.md
   ```
   not a fence, just text inside the heredoc
   ```
   EOF
   ```

3. Point the alias at the new key.
	- tabs are used here on purpose
	- ```inline fence in a list item```

   ~~~sh
   aws kms update-alias --alias-name alias/signing --target-key-id "$NEW_ID"
   # verify
   aws kms describe-key --key-id alias/signing
   ~~~

4. Verify with the application:
   - Open the health page
   - Expect `signing_key_age_days` to be `0`

     ````markdown
     ```yaml
     # sample of the metric output
     signing_key_age_days: 0
     ```
     ````

## Rollback

If anything fails, point the alias back at `$KEY_ID`. The old key is only deleted after 30 days.

```
# an unlabeled fence
aws kms update-alias --alias-name alias/signing --target-key-id "$KEY_ID"
```
