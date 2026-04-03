# Cloudflare Pages Migration

## Recommended setup for this repo

Cloudflare Pages should build from the repository root. The root [ _config.yml ](C:/个人小项目/ClarityStack/_config.yml) now sets `source: site`, so Jekyll will correctly load posts, layouts, includes, assets, and pages from [site](C:/个人小项目/ClarityStack/site).

1. Go to Cloudflare Dashboard -> Pages -> Create a project.
2. Connect GitHub and choose `RayZYunYan/ClarityStack`.
3. Use these settings:
   - Framework preset: `Jekyll`
   - Root directory: `/`
   - Build command: `bundle exec jekyll build`
   - Build output directory: `_site`
   - Environment variable: `JEKYLL_ENV=production`
4. Deploy.

## URLs

- Primary Cloudflare URL in [_config.yml](C:/个人小项目/ClarityStack/_config.yml): `https://claritystack.pages.dev`
- GitHub Pages mirror override in [_config.github-pages.yml](C:/个人小项目/ClarityStack/_config.github-pages.yml): `https://rayzyunyan.github.io` with baseurl `/ClarityStack`

This split keeps Cloudflare Pages serving at the root while GitHub Pages can remain as a backup mirror.

## Security headers

Cloudflare Pages headers are defined in [site/_headers](C:/个人小项目/ClarityStack/site/_headers), and the root config includes `_headers` so it lands in the final build output.

## Optional custom domain

1. Add the domain in Cloudflare Pages -> Custom domains.
2. If the domain is managed by Cloudflare, DNS is created automatically.
3. Update [_config.yml](C:/个人小项目/ClarityStack/_config.yml) `url:` to your final domain, for example `https://claritystack.dev`.

## Notes

- [automation/publish_github.py](C:/个人小项目/ClarityStack/automation/publish_github.py) does not need any Cloudflare-specific change; pushes to GitHub still trigger a rebuild.
- The GitHub Actions workflow is still enabled as a mirror build for GitHub Pages.
- All internal nav and asset paths should continue to work because the templates use `relative_url`.
- If you want Cloudflare-only later, we can disable [.github/workflows/deploy.yml](C:/个人小项目/ClarityStack/.github/workflows/deploy.yml), but I have left it enabled as a backup mirror.
