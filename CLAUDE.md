# Working on Standings

Read `README.md` first for the design, then `NOTES.md` for the trap list --
each entry there already cost a debugging pass. Do not rediscover them.

## Orientation

A playoff-race app for Kyle's teams, built by GitHub Actions each morning and
published to <https://kyeill.github.io/standings/>. Nothing runs locally.

```
python site.py           build the app into output/site/  (in-season only)
python site.py --all     keep every sport, for working out of season
python build.py          print what each tab resolved to, no HTML
python logos.py --write  re-measure crest variants when teams change
python selftest.py       100 assertions -- run before trusting any change
```

Python is not on PATH:
`C:\Users\kyleh\AppData\Local\Programs\Python\Python312-arm64\python.exe`

**No pandas or numpy.** Standard library plus `requests`.

## If you are Claude and this folder is your working directory

Kyle's project notes live in the memory for the **parent** directory,
`C:\Users\kyleh\My Drive\Documents\Claude`. Opening a session here loads none
of it, and you are working from these files alone. A copy of those notes sits
in `..\memory-backup\`.

Two standing preferences of his, easy to miss:

* End every reply with a clearly marked section of outstanding **questions**,
  plus key notes and action items. Buried asks get lost.
* **Verify by running things.** Most of the trap list came from code that
  looked obviously correct.

He has also asked to be reminded, once this settles, about **bundling this
with `sports-daily`** and/or folding the UI into that page. The two projects
deliberately share no code today.

## The shape of it

`leagues.py` is the source of truth for tabs and what each shows. `build.py`
assembles each tab, `site.py` renders it, and `fetch.py` is the only thing that
talks to the network -- except `chockey.py`, which derives college hockey
standings from game results because ESPN publishes none.

## Publishing a change the same day

Three steps, and skipping any of them silently does nothing:

1. commit
2. `git pull --rebase` -- the morning build commits odds history, so your push
   will be rejected otherwise
3. delete `output/history/_last_build.txt`, commit, push, then dispatch:
   `gh workflow run build.yml -R kyeill/standings`

Without step 3 the gate sees the day as already built and skips.

## If git says it is stopping "in case you still have something valuable"

This repo lives inside Google Drive, which syncs `.git` and sometimes holds a
handle on a file git is trying to delete. A finished rebase can leave an EMPTY
`.git/rebase-merge/` behind, and every later `pull --rebase` then refuses.

    rmdir .git/rebase-merge
    rm -f .git/REBASE_HEAD

Check `git log` first: the rebase has usually already succeeded, so there is
nothing to recover. `git status -sb` showing a normal branch line confirms it.
