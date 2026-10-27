# Publish the homepage and privacy policy

The public website is plain HTML and CSS in `site/`. It needs no build step, JavaScript, external fonts, or API credentials. The support address on both pages is `prepaiautomation@gmail.com`.

## Preview locally

From the repository root:

```bash
python3 -m http.server 8000 --directory site
```

Open `http://localhost:8000/` and `http://localhost:8000/privacy.html`. Stop the server with Ctrl+C.

## Publish on GitHub

1. Review the homepage and privacy policy, including data-handling and retention statements, and keep them aligned with your actual operation.
2. Commit and push `site/`, `.github/workflows/pages.yml`, and this guide to `main` in `mbaqo/coding_assessments`.
3. In the repository, open **Settings → Pages → Build and deployment → Source** and select **GitHub Actions**.
4. Open **Actions → Publish website → Run workflow** on `main`. If a push ran before Pages was configured, rerun the workflow now.
5. Wait for a successful deployment. Open the URL shown in the deployment and check both pages without signing in.

Later pushes changing `site/` or its workflow on `main` publish automatically. If you rename the default branch, update the workflow's `push.branches` value. The workflow uploads only `site/`; the Python application, private mailer state, and credentials are not part of the website artifact.

For the current repository, the expected URLs after deployment are:

| Purpose | URL |
| --- | --- |
| Homepage | `https://mbaqo.github.io/coding_assessments/` |
| Privacy policy | `https://mbaqo.github.io/coding_assessments/privacy.html` |

Use the actual deployment URL if you fork the repository or configure a custom domain. The default project URL format and free public-repository hosting are described in [GitHub Pages documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages). The workflow follows [GitHub's custom Pages workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Enter the Google OAuth branding details

After both URLs are publicly reachable, open **Google Auth Platform → Branding** in your Cloud project:

- App name: `Interview Practice` (use the same name as the homepage).
- User support email: select the monitored support address available to the Google account managing your project.
- Developer contact email: an address you monitor.
- Application homepage: the deployed homepage URL above.
- Application privacy policy: the deployed privacy-policy URL above.

Save, then return to **Audience → Publish app**. These pages supply the required disclosures; they do not themselves verify your app or guarantee Google's approval. If Google requests authorized-domain or ownership verification, follow the specific Console requirement. Do not claim ownership of `github.com` or the entire `github.io` service. See [Google's branding documentation](https://support.google.com/cloud/answer/15549049?hl=en).

Keep all website assets and links relative so the site works under the repository path. If you change contact details or data practices, update both pages as appropriate and update the privacy policy's revision date.
