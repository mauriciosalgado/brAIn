# AWS CLI SSO Config

Script to add AWS account profiles to your local AWS CLI config for SSO login.

Tags: #aws #script #onboarding

## Add AWS Accounts to Config

Replace the placeholders with your organization's SSO start URL and each account's ID, then run
the block. Add one `[profile ...]` entry per account you need.

```bash
cat >> "$HOME/.aws/config" << 'EOF'
[sso-session <sso-session>]
sso_start_url = https://<your-org>.awsapps.com/start/
sso_region = <sso-region>
sso_registration_scopes = sso:account:access

[profile <profile-name-dev>]
sso_session = <sso-session>
sso_account_id = <account-id>
sso_role_name = <role-name>
region = <aws-region>

[profile <profile-name-prod>]
sso_session = <sso-session>
sso_account_id = <account-id>
sso_role_name = <role-name>
region = <aws-region>
EOF

echo "Profiles added to ~/.aws/config"
```

## Log In

```bash
# execute-code runs with Obsidian's minimal PATH — add common tool dirs so `aws` is found.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

aws sso login --sso-session <sso-session>
```

## References

- [AWS CLI SSO configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)
- [obsidian-execute-code](https://github.com/twibiral/obsidian-execute-code)
