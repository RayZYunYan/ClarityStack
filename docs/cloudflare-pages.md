# Cloudflare Pages Migration

## Recommended setup for this repo

Because the site now lives under `site/`, configure Cloudflare Pages with that directory as the project root.

1. Go to Cloudflare Dashboard -> Pages -> Create a project.
2. Connect GitHub and choose `RayZYunYan/ClarityStack`.
3. Use these settings:
   - Framework preset: `Jekyll`
   - Root directory: `site`
   - Build command: `bundle exec jekyll build`
   - Build output directory: `_site`
   - Environment variable: `JEKYLL_ENV=production`
4. Deploy.

## URLs

- Primary Cloudflare URL in [site/_config.yml](C:/个人小项目/ClarityStack/site/_config.yml): `https://claritystack.pages.dev`
- GitHub Pages mirror override in [site/_config.github-pages.yml](C:/个人小项目/ClarityStack/site/_config.github-pages.yml): `https://rayzyunyan.github.io` with baseurl `/ClarityStack`

This split keeps Cloudflare Pages serving at the root while GitHub Pages can remain as a backup mirror.

## Security headers

Cloudflare Pages headers are defined in [site/_headers](C:/个人小项目/ClarityStack/site/_headers).

## Optional custom domain

1. Add the domain in Cloudflare Pages -> Custom domains.
2. If the domain is managed by Cloudflare, DNS is created automatically.
3. Update [site/_config.yml](C:/个人小项目/ClarityStack/site/_config.yml) `url:` to your final domain, for example `https://claritystack.dev`.

## Notes

- [automation/publish_github.py](C:/个人小项目/ClarityStack/automation/publish_github.py) does not need any Cloudflare-specific change; pushes to GitHub still trigger a rebuild.
- The GitHub Actions workflow is still enabled as a mirror build for GitHub Pages.
- All internal nav and asset paths should continue to work because the templates use `relative_url`.
