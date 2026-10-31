# Stage 1 — Foundations

**Goal:** a GitHub repo under version control, a Snowflake account you can reach from the command line, and least-privilege roles, warehouses and cost guardrails, all created from SQL files in this repo.

**Done when:** `snow sql -f infra/sql/90_verify.sql` returns your role, warehouse and region, plus a one-sentence answer from Cortex, and the work is merged to `main` through a pull request.

**Time:** 2–4 hours.

---

## 1. Create the Snowflake trial

1. Sign up at [signup.snowflake.com](https://signup.snowflake.com).
2. Choose **Enterprise** edition, cloud **AWS**, region **US West (Oregon)** or **US East (N. Virginia)**. Cortex features tend to arrive in these regions first; cross-region inference (script `04`) covers the gaps.
3. Activate the account from the email and log in to Snowsight.
4. **Add a payment method** (Admin → Billing & Terms). AI features (Cortex, AI functions, agents) are disabled on self-service trials until a card is added. Adding one does not end the trial or upgrade the account; free credits are still used first.
5. Copy your **account identifier**: click your name (bottom left) → **Account** → copy the identifier in `orgname-accountname` form.

## 2. Install the tools

```bash
# uv: fast Python package and tool manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Snowflake CLI, installed as an isolated tool
uv tool install snowflake-cli
snow --version
```

## 3. Set up key-pair authentication

Key pairs let the CLI sign in without a password or MFA prompt, and it's the same method CI uses later.

```bash
mkdir -p ~/.snowflake/keys && cd ~/.snowflake/keys
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out noi_rsa_key.p8 -nocrypt
openssl rsa -in noi_rsa_key.p8 -pubout -out noi_rsa_key.pub
chmod 600 noi_rsa_key.p8

# Print the public key body without the header/footer lines
grep -v "PUBLIC KEY" noi_rsa_key.pub | tr -d '\n'; echo
```

In a Snowsight worksheet, as `ACCOUNTADMIN`, register the public key on your user:

```sql
ALTER USER <your_username> SET RSA_PUBLIC_KEY = '<paste the key body>';
```

> The `.p8` file is your private key. It stays in `~/.snowflake/keys/`, never in the repo.

## 4. Connect the CLI

```bash
cp infra/config.example.toml ~/.snowflake/config.toml
# edit ~/.snowflake/config.toml: account, user
chmod 600 ~/.snowflake/config.toml

snow connection test -c noi
```

`Status: OK` means you're connected. After step 5, add `warehouse = "NOI_WH_DEV"` to the connection so later commands have compute by default.

## 5. Run the infrastructure scripts, in order

Each script switches to the role it needs, so read the header of each before running it.

```bash
snow sql -f infra/sql/00_roles.sql          -c noi   # roles + hierarchy
snow sql -f infra/sql/01_warehouses.sql     -c noi   # X-Small, 60s auto-suspend
snow sql -f infra/sql/02_databases.sql      -c noi   # NOI_DEV, NOI_PROD
snow sql -f infra/sql/03_cost_guardrails.sql -c noi  # 40-credit monthly cap
snow sql -f infra/sql/04_cortex_access.sql  -c noi   # Cortex access
snow sql -f infra/sql/90_verify.sql         -c noi   # check it all worked
```

All scripts are rerunnable: running one twice does no harm.

## 6. Commit through a pull request

```bash
git checkout -b stage-1-foundations
git add .
git commit -m "feat(infra): roles, warehouses, databases, cost guardrails"
git push -u origin stage-1-foundations
gh pr create --fill
```

Review the PR on GitHub, merge it, then:

```bash
git checkout main && git pull
```

Tick Stage 1 in the README in the same PR or the next one.

## What you should be able to explain

- **Why four roles?** Each job gets the smallest set of privileges it needs; ACCOUNTADMIN is used only for account-level settings.
- **Why two databases?** Dev and Prod are isolated, so a broken Dev build can never affect what agent users see.
- **What does the resource monitor not cover?** Cortex services and Container Services compute pools. Those are watched with `91_cost_report.sql` and stopped with `99_teardown.sql`.
- **Why key pairs?** No passwords in scripts, no MFA prompts in automation, and the private key never leaves your machine.

## Troubleshooting

| Error | Likely cause | Fix |
| --- | --- | --- |
| `JWT token is invalid` | Public key not set, or set on the wrong user | Rerun the `ALTER USER ... SET RSA_PUBLIC_KEY` step |
| `Insufficient privileges to operate on ...` | Script run before the one that grants the role | Run the scripts in numeric order |
| `Role 'NOI_ADMIN' does not exist` in `90_verify` | `00_roles.sql` failed | Rerun `00_roles.sql` and read its output |
| `SNOWFLAKE.CORTEX.COMPLETE is not available on this account` | New accounts must use the newer AI functions | Use `AI_COMPLETE` (already in `90_verify.sql`) |
| `AI function ... is not available for trial accounts` | AI features are off until a payment method is added | Add a card in Admin → Billing & Terms, then rerun |
| `AI_COMPLETE` model error | Model not available in region | Confirm `04_cortex_access.sql` ran; try another model name |
