# Deployment and domain registration

The site is static and is served by Cloudflare Workers Assets. This is the same
Pages-style static hosting pattern used by the sibling projects.

## Current state

- `wrangler.toml` defines the worker name `compactation` and points assets at
  `./public`.
- `deploy.sh` copies `index.html` and `og-image.png` into `public/`, installs
  pinned dependencies with `npm ci` when needed, and runs `wrangler deploy`.
- The deploy account is the Wrangler OAuth login on the operator's machine. No
  API token, key, or secret is stored in this repository.
- `compactation.dev` is registered in Cloudflare. Both
  `https://compactation.dev` and `https://www.compactation.dev` are attached to
  the `compactation` worker in production and serve the same bytes as
  `public/index.html`; `/og-image.png` matches `public/og-image.png`.

## Deploy

Before deploying copy that advertises a release, push the signed tag for that
release and confirm it verifies. For v0.0.2:

```sh
git tag -v v0.0.2
git push origin v0.0.2
```

If either command fails, stop. Deploying first would publish a quickstart URL
that returns 404 and a tag verification command that cannot succeed. After the
tag is live, deploy:

```sh
./deploy.sh
```

For review, never run a live deploy. Use:

```sh
npx wrangler deploy --dry-run
```

## Domain registration (completed)

Domain purchase and custom-domain attachment require an authenticated
Cloudflare account with billing enabled. That action is deliberately not
encoded in the repository and no credential is committed.

1. `compactation.dev` was registered through Domains → Registrations and is
   active in the account.
2. Under Workers & Pages → `compactation` → Settings → Domains & Routes, both
   `compactation.dev` and `www.compactation.dev` are attached to production.
3. Cloudflare created the DNS records automatically; no external registrar or
   manual CNAME is involved.
4. The canonical URL in site metadata is live. Verify published bytes with:

   ```sh
   curl -fsSL https://compactation.dev/ | sha256sum
   sha256sum public/index.html
   ```

If the registration is ever allowed to lapse, change the canonical URL in
`index.html` back to the `workers.dev` URL before claiming the custom domain
is live.

## Secrets policy

Never place API tokens, Cloudflare keys, or GitHub tokens in this repository,
its fixtures, or its issues. Deployment uses the operator's local Wrangler
session and GitHub credential helper only.
