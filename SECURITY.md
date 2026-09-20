# Security Notes

## Secret handling

- Real credentials belong only in `.env`, which is ignored by Git.
- `.env.example` must contain placeholders such as `your_api_key_here`.
- Never paste a live key into documentation, tests, or commit messages.

## Known past incident

Commit `bea0c04` ("Mistral AI Initial Program") committed a real
`CAPGEMINI_API_KEY` value into `.env.example`. The value was replaced with a
placeholder in a later commit, but it remained reachable in the pushed Git
history, so it must be treated as publicly disclosed.

Required response:

1. Revoke and reissue the affected API key in the Generative Engine portal.
2. Update the local `.env` with the new key.
3. Rewrite the published history so the value is no longer served by GitHub.

## Rewriting history to remove a leaked value

```powershell
python -m pip install git-filter-repo
"OLD_SECRET_VALUE==>your_api_key_here" | Set-Content replacements.txt -Encoding utf8
git filter-repo --replace-text replacements.txt --force
git remote add origin https://github.com/Mahmoud-N-Siam/capgemini-chatbot.git
git push --force origin main
Remove-Item replacements.txt
```

Notes:

- `git filter-repo` rewrites every commit hash, so existing clones and forks
  must be re-cloned.
- It removes the `origin` remote by design; re-add it before pushing.
- GitHub may keep the old blob visible in cached views. Contact GitHub Support
  to purge it, and treat rotation as the real fix.

## Operational notes

- The server binds to `127.0.0.1`, so it is not reachable from other hosts.
- Uploaded documents, embeddings, and conversation history are in-memory per
  process and cleared on restart.
- `SECRET_KEY` falls back to a random value per process when unset, which
  invalidates existing sessions on restart. Set it explicitly for stable
  sessions.
