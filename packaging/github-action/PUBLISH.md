# Publiceren van runvouch/vouch-action
Deze map is de bron; de GitHub-repo is een kopie. De token in .env heeft geen `workflow`-scope,
dus geen .github/workflows in deze map (voorbeelden staan in examples/).

    cd packaging/github-action && rm -rf .git && git init -q -b main && git add -A \
      && git -c user.name=RunVouch -c user.email=launch@runvouch.com commit -qm "vouch-action vX" \
      && git tag v1 && git remote add origin https://github.com/runvouch/vouch-action.git \
      && git push -qf origin main --tags && rm -rf .git
Gebruikers pinnen op `@v1`; de tag verschuift mee (force).

Het duwen leunt op de credential-helper (`git config --global credential.helper`, of `gh auth login`).
Zet de token nooit in de remote-URL: hij belandt dan in leesbare tekst in `.git/config`, staat in de
uitvoer van `git remote -v`, en een secret-scanner leest een URL met gebruiker en token voor het
apenstaartje als een gelekt wachtwoord (GitGuardian meldde deze regel op 29 augustus 2026 als
"Basic Auth String"). Schrijf die vorm dus ook niet als voorbeeld op: de scanner leest het voorbeeld.
