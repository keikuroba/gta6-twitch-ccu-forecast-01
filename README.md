# GTA VI Twitch CCU forecast

Entry for make.fun bounty `gta6-twitch-ccu-forecast-01`: a program that
forecasts, hour by hour, how many people watch Grand Theft Auto VI live
on Twitch over the 24 UTC hours of its release day, from everything
recorded up to the end of its first hour.

## Program

`main.py` (Python 3.13, standard library only) reads one case from
`/input/<id>.in` and writes `/output/<id>.out`: for each hour 2..24,
five quantiles (5%, 25%, 50%, 75%, 95%) of that hour's concurrent
viewers in the "Grand Theft Auto VI" Twitch category.

## Method

A launch's audience curve depends strongly on how big its first hour
already is: a category that opens near-empty at 00:00 UTC typically
grows many-fold as unlocks roll across time zones, while a category
that opens huge stays roughly flat or decays. So the forecast conditions
on launch size: for each hour it takes the 8 comparable past launches
whose hour-1 viewer count is closest in log space to this case's hour-1
print, and uses the mean of their log-ratios `log(viewers_h /
viewers_1)` as the centre and the standard deviation of those
log-ratios as the spread:

```
q_tau(h) = p1 * exp(centre_h + z_tau * spread_h)
```

with `z` the standard normal quantiles at the five scored levels. When
too few neighbours report an hour, it falls back to the same statistics
over all usable comparables, then to a persistence forecast with a
random-walk spread.

## Validation

On the four practice launches (Marvel's Wolverine, Red Dead Redemption
2, God of War Ragnarök, Marvel's Spider-Man 2), scored against
SullyGnome hourly averages with the competition's pinball loss:

- house persistence baseline: loss 0.387
- this program: loss 0.224 (leave-one-out on 37 comparable launches:
  0.416 vs baseline 0.930)

The program is deterministic (two runs write byte-identical output),
offline, and reads nothing outside its input directory.

## Run

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## License

MIT — see `LICENSE`.
