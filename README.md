# Modelling
## NBA Package
### Set-up Instructions
#### Terminal
If running virtual environment (venv), initiate with

`venv\Scripts\activate`

then check that Python Interpreter is located at  ~\ProjectName\venv\Scripts\python.exe

Next change the working directory to modelling folder

`cd modelling`

then install all requirements

`pip install -r requirements.txt`

The project should now be set up and ready to run and interact with GitHub

#### Database
By default, this project has been set up to work with MySQL databases.  All the SQL connections are defined at 
[connections.py](projects/nba/utils/connections.py).

The connection parameters can be adjusted at [environment.py](projects/nba/utils/environment.py).

The `write_data`, `load_data` and `initialise_df` functions have been defined at
[functions.py](projects/nba/utils/functions.py) and will need to be adjusted  if another DB is to be used.

#### Dataset
To ensure everything runs smoothly, the modules should be run in the following order:

[cleaning.teams.py](projects/nba/data/cleaning/teams.py) - this automatically writes all team data defined in
[classes.py](projects/nba/utils/classes.py) to `nba.teams` in the DB.

[scraping.games.py](projects/nba/data/scraping/games.py) - this scrapes daily score data from Basketball Reference 
within the date range defined in [params.py](projects/nba/utils/params.py) and writes the data to `nba.games` in the DB.

[scraping.plays.py](projects/nba/data/scraping/plays.py) - this scrapes the raw play-by-play rows from Basketball
Reference for all games that appear within both the nba.games table, and the date range defined in
[params.py](projects/nba/utils/params.py), then writes the data to `nba_raw.plays_raw` in the DB

[scraping.odds.py](projects/nba/data/scraping/odds.py) - this scrapes game odds from
[oddsportal](https://www.oddsportal.com/) on a season by season basis (set in
[params.py](projects/nba/utils/params.py)) for seasons existing in `nba.games`, then writes the data to `nba.odds` in
the DB.

[scraping.players.py](projects/nba/data/scraping/players.py) - this pulls the entire roster for each game-season
combination in the `nba.games`, then scrapes information about each player in the list, then writes the data to
`nba.players` in the DB.

[scraping.game_lineups](projects/nba/data/scraping/game_lineups.py) - this goes through the box score for each game in
`nba.games` and scrapes the lineups for each time, denoting Starters, Bench, and DNP, then writes the data to
`nba.games_lineups` in the DB.

[cleaning.plays.py](projects/nba/data/cleaning/plays.py) - this applies logic to all raw play by play rows in
`nba_raw.plays_raw` to clean and isolate each individual statistic that happens in a game (e.g. one FGA row
becomes multiple rows; FGA, FG Miss/Make, Assist, Block, Rebound), then writes the data to `nba.plays` in the DB.
Unfortunately, Basketball Reference does not show substitutions during breaks, so a messy extra bit of code has been
written to produce players on the court.

### Analysis & Modelling
#### Potential analyses
* Overall 'value added' statistic by player (e.g. +/- by player accounting for other players on the court)
* Predicting game probabilities (e.g. based on record, home/away, fatigue, missing players)
* Interesting stats/trends (e.g. likelihood of shooting/making next shot after shot/make; importance index
  by game)

### Planned Development
*Note: all data and modelling files that are not listed above are currently not in use.*
* Write [cleaning.game_logs.py](projects/nba/data/cleaning/plays.py) script to create a nicer dataset for predictive
  analysis
* ~~Update [cleaning.plays.py](projects/nba/data/cleaning/plays.py) to include possession indicator and which players
  are on the court~~
* Add automated performance testing
* Update all data modules to be faster (e.g. multi-processing, writing output in batches, more efficient code)
* Make Team-based code adaptable for changes in team names
* Set up central control to build dataset from one script
* **Goal is to scrape 20 seasons of data reasonably quickly and accurately**

### Bug Log
* Occasionally Basketball Reference has a shot that doesn't show up, or a make that is incorrectly counted as a 2/3
* Missing rebounds when a shot doesn't show up in Basketball Reference, or there is a substitution 'after' a missed FT,
  so the shooter is not picked up
