# Publiceren van runvouch/vouch-action
Deze map is de bron; de GitHub-repo is een kopie. De token in .env heeft geen `workflow`-scope,
dus geen .github/workflows in deze map (voorbeelden staan in examples/).

    cd packaging/github-action && rm -rf .git && git init -q -b main && git add -A \
      && git -c user.name=RunVouch -c user.email=launch@runvouch.com commit -qm "vouch-action vX" \
      && git tag v1 && git remote add origin "https://runvouch:$GITHUB_TOKEN@github.com/runvouch/vouch-action.git" \
      && git push -qf origin main --tags && rm -rf .git
Gebruikers pinnen op `@v1`; de tag verschuift mee (force).
