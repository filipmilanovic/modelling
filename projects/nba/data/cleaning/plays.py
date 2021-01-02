# CLEAN RAW PLAYS DATA
from modelling.projects.nba import *  # import all project specific utils
from modelling.projects.nba.data.scraping import *  # importing scraping for certain exceptions


# LOADING AND TIDYING OF RAW PLAYS TEXT
# get the plays for specified game
def get_raw_plays(game_id):
    home_team = games.home_team[games.game_id == game_id].item()
    away_team = games.away_team[games.game_id == game_id].item()

    global team_names
    team_names = {'home_team': home_team, 'away_team': away_team}

    output = plays_raw.loc[plays_raw.game_id == game_id]
    output = output.iloc[1:].reset_index()
    output['plays'] = play_remove_line_break(output['plays'])
    output['plays'] = play_remove_score_added(output['plays'])
    output['time'] = get_time(output['plays'])
    output['plays'] = play_remove_time(output['plays'])
    output['teams'] = get_teams(output['plays'])
    output['plays'] = play_remove_score(output['plays'])
    output['plays'] = output['plays'].str.strip()

    log_performance()
    return output


# cleans line break from raw plays
def play_remove_line_break(x):
    # output = re.sub(r'\n', '', x)
    output = x.str.replace(r'\n', '')

    log_performance()
    return output


# cleans out +d score from raw plays
def play_remove_score_added(x):
    # output = re.sub(r'(\+[0-9])', '', x)
    output = x.str.replace(r'(\+[0-9])', '')

    log_performance()
    return output


# cleans out scoreboard from raw plays
def play_remove_score(x):
    # output = re.sub(r'\d+(-)+\d+', '', x)
    output = x.str.replace(r'\d+-+\d+', '')

    log_performance()
    return output


# cleans out time remaining from raw plays
def play_remove_time(x):
    # output = re.sub(r'\d+:\d+\.\d', '', x)
    output = x.str.replace(r'\d+:\d+\.\d', '')

    log_performance()
    return output


# FILLING BASIC PLAY INFORMATION
# get the period of the game based on the 'start of period' line
def get_quarter(play):
    # play = get_play(x)
    period = re.search(r'Start of (.*)', play).group(1)
    if 'overtime' in period:
        output = 'OT' + str(left(period, 1))
    else:
        output = re.search(r'(.*) quarter', period).group(1)

    log_performance()
    return output


# get the time of the play
def get_time(series):
    output = series.str.extract(r'(\d+:\d+\.\d)', expand=False)
    output = output.str.replace(r'\.0', '')

    log_performance()
    return output


def get_score(df):
    home_points = (df.loc[df['event'].str.contains(' Make')
                          & (df['team_id'] == team_names['home_team']),
                          'event_value']).reindex(range(len(df))).fillna(0)
    home_cumulative = home_points.astype('int').cumsum().astype('str')

    away_points = (df.loc[df['event'].str.contains(' Make')
                          & (df['team_id'] == team_names['away_team']),
                          'event_value']).reindex(range(len(df))).fillna(0)
    away_cumulative = away_points.astype('int').cumsum().astype('str')

    output = home_cumulative.str.cat(away_cumulative, sep='-')

    log_performance()
    return output


# find team_id based on the location of the actual play to the score in the raw text line (away before, home after)
def get_teams(series):
    # find location of score in the strings
    scores = series.str.extract(r'(\d+-+\d+)', expand=False)
    score_location = pd.Series([series[i].find(str(scores[i])) for i in range(len(series))])

    # set mapping conditions
    conditions = [score_location == -1, score_location == 2]
    teams = [None, team_names['home_team']]

    # generate column of teams
    output = np.select(conditions, teams, default=team_names['away_team'])

    log_performance()
    return output


def get_team_id(row, reverse=False):
    # set as initial team_id
    output = row['teams']

    # in some cases (steals, blocks, some fouls), the play appears on the 'wrong' side
    if reverse:
        output = list(team_names.values())[team_names['home_team'] == output]

    log_performance()
    return output


# GENERATING LIST OF ON-COURT PLAYERS
# get players on the court in a key format by period
def get_on_court_player_ids(df):
    # set game_id
    game_id = df.game_id[0]

    # get list of game periods
    periods = set(df.period)

    # get teams and initialise series
    home_team = games.home_team[games.game_id == game_id].item()
    away_team = games.away_team[games.game_id == game_id].item()
    home_players = pd.Series(dtype='str')
    away_players = pd.Series(dtype='str')

    for i in periods:
        # get players from known plays data
        home_players_period = get_players_period(df, home_team, i)
        away_players_period = get_players_period(df, away_team, i)

        # check if 5 players on each team, and scrape from box scores if there is an issue
        home_players_period = check_on_court_data(home_players_period, home_team, game_id, i)
        away_players_period = check_on_court_data(away_players_period, away_team, game_id, i)

        # append players to base series
        home_players = home_players.append(home_players_period)
        away_players = away_players.append(away_players_period)

    # add full dataframe index, then fill in blanks for both teams
    home_players = home_players.reindex(range(len(df))).fillna(method='ffill').fillna(method='bfill')
    away_players = away_players.reindex(range(len(df))).fillna(method='ffill').fillna(method='bfill')

    # set players as players on court for given team_id, and opp_players as opposition
    players = home_players[df.team_id == home_team].append(away_players[df.team_id == away_team]).sort_index()
    opp_players = home_players[df.team_id == away_team].append(away_players[df.team_id == home_team]).sort_index()

    log_performance()
    return players, opp_players


# get the player_ids key for each play for a given team and period
def get_players_period(df, team, period):
    # save index for later use
    index = df[(df.team_id == team) & (df.period == period)].index

    # get team specific plays
    team_plays = df[(df.team_id == team) & (df.period == period)].reset_index(drop=True)

    # generate series of players by period
    players_period = []

    # firstly starting from the end and adding players who made plays
    for j in reversed(range(len(team_plays))):
        # initialise the series with the first player
        if j == len(team_plays) - 1:
            # leave blank if final play has no player_id (e.g. Team rebound)
            players = str(if_none(team_plays.player_id[j], '')) + '|'
        else:
            # add current row players by checking information and known players of last 2 plays
            players = get_player_array(team_plays[j:j+2], players_period[len(team_plays)-j-2], j)

        # append current row players to series
        players_period.append(players)

    # go back from start to end and fill down new information from each row to the next
    players_period = fill_down_players(players_period)

    # convert to series
    output = pd.Series(players_period)

    # re-index based on initial index of plays for the team
    output.index = index

    log_performance()
    return output


# get on court player list by adding new player to known list (this runs backwards)
def get_player_array(plays_info, previous_player_ids, iteration):
    play = plays_info.loc[iteration]

    # use previous play in the event of a substitution, and substitute player
    previous_play = plays_info.loc[iteration + 1]
    if previous_play.event == 'Substitution':
        previous_player_ids = re.sub(previous_play.player_id, previous_play.event_detail, previous_player_ids)

    # get list of players from the previous play
    players = extract_players(previous_player_ids)

    # sometimes players on the bench get a tech, so we will just exclude this
    if play.event == 'Technical foul':
        pass

    else:
        # add player if they are not in existing list
        try:
            if play.player_id not in previous_player_ids:
                players.append(play.player_id)
        except TypeError:
            pass

    # combine players back into player_id key
    output = convert_to_string(players)

    log_performance()
    return output


# turn on court player key to list of player_ids
def extract_players(x):
    output = [i for i in x.split('|') if i]

    log_performance()
    return output


# turn list of on court player_ids to key
def convert_to_string(x):
    # join first 4 players with separator
    players = [str(i) + '|' for i in x[0:4]]
    if len(x) == 5:
        # add final player without separator
        players += x[4]
    # join player_ids
    output = ''.join(players)

    log_performance()
    return output


# fill down list generated by get_player_array to flesh out each play to 5 players
def fill_down_players(array):
    array = list(reversed(array))
    for i in range(1, len(array)):
        # get list of players from each row
        play_list = extract_players(array[i])

        # find number of players
        play_players = len(play_list)

        # get list of players from previous row
        previous_play_list = extract_players(array[i-1])

        # compare number of players to previous row
        previous_play_players = len(previous_play_list)

        if previous_play_players > play_players:
            # check if current row of players shorter than previous row, then fill in missing positions
            missing = previous_play_list[play_players:previous_play_players+1]
            [play_list.append(i) for i in missing]

        # convert player list to player_id key
        array[i] = convert_to_string(play_list)

    log_performance()
    return array


# SCRAPING OF DATA WHEN MISSING PLAYERS
# check that each row has 5 players, as a player that plays a whole period with no contribution will not show up
def check_on_court_data(series, team_id, game_id, period):
    # checking
    check_result = on_court_player_check(series)
    output = series

    # if check results in fewer than 5 players, then get the missing players
    if check_result != 5:
        output = get_missing_players(series, team_id, game_id, period)

    # check if issue resolved
    check_updated = on_court_player_check(output)

    if check_updated != 5:
        print(f'Missing players in {period} period of {game_id}')
        exit()

    log_performance()
    return output


# check to ensure there are always 10 players on the court
def on_court_player_check(series):
    # generate empty series
    count_check = pd.Series(dtype=bool)

    # check number of players on court by counting number of 0 (player_id's to date all contain one 0)
    for i in series.index:
        count_check.loc[i] = series[i].count('0')

    # return minimum number of players found in list
    output = min(count_check)

    log_performance()
    return output


# if there are fewer than 5 players, then we need to find the missing players
def get_missing_players(series, team_id, game_id, period):
    # index for later re-indexation
    index = series.index

    # visit game box scores to figure out which players played in the desired period
    error = scrape_box_score(team_id, game_id, period)

    # check which player did not show up in the initial series of on-court players
    missing_index = [all([i not in j for j in series]) for i in error]

    # get missing player_id
    missing_player_id = error[missing_index]

    # add missing player to each row
    output = add_missing_player(series, missing_player_id)

    # match initial index
    output.index = index

    log_performance()
    return output


# interacting with basketball reference to get the box score data
def scrape_box_score(team_id, game_id, period):
    all_periods = 'Game', 'Q1', 'Q2', 'Q3', 'Q4', 'OT1', 'OT2', 'OT3', 'OT4'

    # calculate data missing in OT1 by difference between total game time and regulation game time
    periods = [i for i in all_periods if i != period_name[period]]
    if any(period == i for i in ['1st', '2nd', '3rd', '4th']):
        seconds = 720
    else:
        seconds = 300
    # Method not perfect, check later if issues arise

    # load website using index
    url = f"https://www.basketball-reference.com/boxscores/{game_id}.html"
    driver = webdriver.Chrome(executable_path=str(ROOT_DIR) + "/utils/chromedriver.exe",
                              options=options)
    driver.get(url)

    # get minutes by player by period
    player_minutes = get_player_minutes(driver, periods, team_id)

    # get minutes by player in desired period
    missing_period_minutes = get_missing_period_minutes(player_minutes, periods)

    # get players who played in the desired period
    output = player_minutes.loc[missing_period_minutes.between(seconds-1, seconds+2), 'player_id_Game']

    # close the driver
    driver.close()

    log_performance()
    return output


# get a DataFrame of number of minutes played by player by period
def get_player_minutes(driver, periods, team_id):
    player_minutes = pd.DataFrame()

    # for each of the desired periods, scrape player_ids and minutes
    for i in periods:
        # get the key for the box score
        box_key = get_box_key(team_id, i)

        # Only for periods that exist in the game
        try:
            # access the relevant box score by selecting the desired period
            click_period(driver, i)

            # get box score stats for the period
            player_minutes_period = get_box_score(driver, box_key)

            # convert column names to show which period
            player_minutes_period.columns = [f'player_id_{i}', f'minutes_{i}']

            # join together all periods
            player_minutes = pd.concat([player_minutes, player_minutes_period], axis=1)
        except IndexError:
            pass

    log_performance()
    return player_minutes


# get box score key to use for accessing correct box score
def get_box_key(team_id, period):
    output = 'box-' + team_id + '-' + period.lower() + '-basic'

    log_performance()
    return output


# click on the correct period in the box score screen on basketball reference
def click_period(driver, period):
    # scroll down the page so that the tabs show aren't covered by an ad
    driver.execute_script("window.scrollTo(0, 800);")

    # wait to ensure everything has loaded properly
    time.sleep(0.5)

    # get all tabs
    tabs = driver.find_elements_by_class_name('sr_preset')

    # select tab which matches desired period
    tab = [x for x in tabs if x.text == period][0]

    # click on tab to open desired period box score
    tab.click()

    log_performance()


# get the box score of a given period
def get_box_score(driver, key):
    # grab table based on box_score_key
    table = driver.find_element_by_id(key)

    # get table data from BeautifulSoup
    soup = BeautifulSoup(table.get_attribute('innerHTML'), 'html.parser')

    # want to scrape player_ids and number of minutes
    players_columns = ['player_id', 'minutes']

    # get player link and minutes for all players who played for the team
    output = pd.DataFrame([[x.findChild('th').findChild('a').get('href'), x.findChild('td').text]
                           for x in soup.find_all('tr')
                           if x.findChild('th').findChild('a') is not None
                           and 'Did Not' not in x.findChild('td').text],
                          columns=players_columns)

    # isolate player_id from href
    output.player_id = [re.search('players/[a-z]/(.*).html', i).group(1) for i in output.player_id]

    # replace empty minutes played with 0 and convert series to time
    output.minutes = [dt.strptime(i.replace('\xa0', '0:00'), '%M:%S').time() for i in output.minutes]

    log_performance()
    return output


# get the number of minutes played in desired period by calculating (as players with no plays are blank in pbp)
def get_missing_period_minutes(df, periods):
    # select only periods which exist
    n = int(len(df.columns)/2)
    periods = periods[:n]

    # convert seconds played into dataframe by player, by period
    minutes_played = pd.DataFrame([[get_seconds(i) for i in df[f'minutes_{periods[j]}']]
                                   for j in range(len(periods))],
                                  index=periods).transpose()

    # calculate the number of minutes the players played in the desired period
    output = minutes_played[periods[0]]

    for i in range(1, len(minutes_played.columns)):
        output -= minutes_played[periods[i]]

    log_performance()
    return output


# concatenate missing player_ids onto end of each row
def add_missing_player(series, player_id):
    try:
        # if multiple players, join by the '|' separator
        separator = '|'
        to_append = separator.join(player_id)
    except TypeError:
        # if only one player, append without separator
        to_append = player_id
    # loop through each row in the series
    output = pd.Series([i + to_append for i in series])

    log_performance()
    return output


# GET EVENT_DETAIL FOR SHOTS
# get the amount of points a shot was worth
def get_shot_value(play):
    if 'free throw' in play:
        # FTs worth 1 point
        output = 1
    elif match := re.search(r'(\d)-pt', play):
        # FGs worth amount given in play
        output = match.group(1)
    else:
        output = None

    log_performance()
    return output


# get distance of shot, or which free throw it was
def get_shot_detail(play):
    if match := re.search(r'free throw (\d)', play):
        # get which number in sequence of FTs
        output = match.group(1)
    elif 'technical' in play:
        # get if technical FT
        output = 1
    elif match := re.search(r'(\d+) ft', play):
        # get distance of shot if FG
        output = match.group(1)
    else:
        output = 0

    log_performance()
    return output


# PRODUCE ROWS FOR EACH DIFFERENT TYPE OF EVENT
# Produce the 'Period Start' line in order to get the correct period
def get_period_start(row, game_id):
    play = row['plays']
    array = [game_id,  # game_id
             get_quarter(play),  # period
             row['time'],  # time
             None,  # score
             None,  # team_id
             None,  # players
             None,  # opp_players
             None,  # player_id
             'Period Start',  # event
             None,  # event_value
             None,  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


# Produce the 'Period End' line in order to get the correct period end
def get_period_end(game_id):
    array = [game_id,  # game_id
             None,  # period
             '0:00',  # time
             None,  # score
             None,  # team_id
             None,  # players
             None,  # opp_players
             None,  # player_id
             'Period End',  # event
             None,  # event_value
             None,  # event_detail
             1  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


# get data for a jump ball
def get_jump_ball_data(row, game_id):
    player_1 = row['player_1']
    player_2 = row['player_2']
    player_3 = row['player_3']
    # find team that controlled the tip
    winning_team_id = games_lineups.team_id[(games_lineups.game_id == game_id) &
                                            (games_lineups.player_id == player_3)].item()
    # find which player from that team competed for the jump ball
    winning_team_players = games_lineups.player_id[(games_lineups.game_id == game_id) &
                                                   (games_lineups.team_id == winning_team_id) &
                                                   (games_lineups.player_id == player_1)]
    # if player_id found in winning team, then sat that player as player_id, then set other as event_detail
    if len(winning_team_players) > 0:
        winning_player_id = player_1
        losing_player_id = player_2
    else:
        winning_player_id = player_2
        losing_player_id = player_1
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             winning_team_id,  # team_id
             None,  # players
             None,  # opp_players
             winning_player_id,  # player_id
             'Jump Ball',  # event
             1,  # event_value
             losing_player_id,  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


# get necessary data for a shot attempt
def get_shot_attempt_data(row, shot_type, game_id):
    play = row['plays']
    player_id = row['player_1']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             str(shot_type) + ' Shot',  # event
             get_shot_value(play),  # event_value
             get_shot_detail(play),  # event_detail
             0  # possession
             ]
    output = array

    log_performance()
    return output


# get necessary data for a made shot
def get_shot_make_data(row, shot_type, game_id):
    play = row['plays']
    player_id = row['player_1']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             str(shot_type) + ' Make',  # event
             get_shot_value(play),  # event_value
             get_shot_detail(play),  # event_detail
             1  # possession
             ]
    output = array

    log_performance()
    return output


# get necessary data for a missed shot
def get_shot_miss_data(row, shot_type, game_id):
    play = row['plays']
    player_id = row['player_1']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             str(shot_type) + ' Miss',  # event
             get_shot_value(play),  # event_value
             get_shot_detail(play),  # event_detail
             1  # possession
             ]
    output = array

    log_performance()
    return output


# get which player assisted if there was a made shot
def get_assist_data(row, game_id):
    shooter_id = row['player_1']
    player_id = row['player_2']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             'Assist',  # event
             1,  # event_value
             shooter_id,  # event_detail
             0  # possession
             ]
    output = array

    log_performance()
    return output


# get which player blocked a shot
def get_block_data(row, game_id):
    shooter_id = row['player_1']
    player_id = row['player_2']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row, True),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             'Block',  # event
             1,  # event_value
             shooter_id,  # event_detail
             0  # possession
             ]
    output = array

    log_performance()
    return output


# combine all shot related information to produce detailed rows of data
def get_shot_data(row, game_id):
    play = row['plays']
    arrays = []
    # label FT or FG
    if 'free throw' in play:
        shot_type = 'FT'
    else:
        shot_type = 'FG'

    # get row for shot attempt
    shot = get_shot_attempt_data(row, shot_type, game_id)

    # get row for shot miss
    if ' misses' in play:
        miss = get_shot_miss_data(row, shot_type, game_id)
        arrays = [shot, miss]

        # get row for block if shot blocked
        if 'block by' in play:
            block = get_block_data(row, game_id)
            arrays = [shot, miss, block]

    # get row for shot make
    elif ' makes' in play:
        make = get_shot_make_data(row, shot_type, game_id)
        arrays = [shot, make]

        # get row for assist if applicable
        if 'assist by' in play:
            assist = get_assist_data(row, game_id)
            arrays = [shot, make, assist]

    # create dataframe of given rows
    output = pd.DataFrame(arrays, columns=columns)

    log_performance()
    return output


# get who rebounded the ball, with whose shot they rebounded
def get_rebound_data(row, y, game_id):
    shooter = None
    play = row['plays']
    player_id = row['player_1']
    # there is a bug with rare missing shot info, or sub occurs after FT miss so the shooter isn't picked up
    if y.event.item() is None:
        shooter = None
    elif 'Miss' in y.event.item():
        shooter = y.player_id.item()
    elif 'Block' in y.event.item():
        shooter = y.event_detail.item()
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             re.search(r'(.*) rebound', play).group(0),  # event
             1,  # event_value
             shooter,  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


def get_turnover_data(row, game_id):
    play = row['plays']
    player_id = row['player_1']
    detail = if_none(re.search(r'\((.*);', play), re.search(r'\((.*)\)', play))
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             'Turnover',  # event
             1,  # event_value
             detail.group(1),  # event_detail
             1  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


def get_steal_data(row, game_id):
    turnover_player_id = row['player_1']
    player_id = row['player_2']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row, True),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             'Steal',  # event
             1,  # event_value
             turnover_player_id,  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


def get_foul_data(row, game_id):
    play = row['plays']
    player_id = row['player_1']
    fouled_player_id = row['player_2']

    # find foul types which should 'reverse' the team_id
    reversed_fouls = ['Away from play foul',
                      'Clear path foul',
                      'Def 3 sec tech foul',
                      'Flagrant foul',
                      'Inbound foul',
                      'Offensive charge foul',
                      'Personal foul',
                      'Personal block foul',
                      'Personal take foul',
                      'Shooting foul',
                      'Shooting block foul']
    event = re.search(r'(.*) foul', play).group(0)
    reverse = any(x in event for x in reversed_fouls)

    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row, reverse),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             event,  # event
             1,  # event_value
             fouled_player_id,  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


def get_violation_data(row, game_id):
    play = row['plays']
    player_id = row['player_1']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             'Violation',  # event
             1,  # event_value
             re.search(r'\((.*)\)', play).group(1),  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


def get_substitution_data(row, game_id):
    player_id = row['player_1']
    sub_player_id = row['player_2']
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             player_id,  # player_id
             'Substitution',  # event
             1,  # event_value
             sub_player_id,  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


def get_timeout_data(row, game_id):
    play = row['plays']
    detail = re.search(r'(20 second|full|Official) timeout', play).group(1)
    array = [game_id,  # game_id
             None,  # period
             row['time'],  # time
             None,  # score
             get_team_id(row),  # team_id
             None,  # players
             None,  # opp_players
             None,  # player_id
             'Timeout',  # event
             1,  # event_value
             detail.capitalize(),  # event_detail
             0  # possession
             ]
    output = pd.DataFrame([array], columns=columns)

    log_performance()
    return output


# iterate through plays to produce base event details
def clean_plays(df):
    output = pd.DataFrame(columns=columns)
    for i in range(len(df['plays'])):
        game_id = df.game_id[i]
        if 'Start of ' in df.loc[i, 'plays']:
            output = output.append(get_period_start(df.loc[i], game_id))
        elif 'End of ' in df.loc[i, 'plays']:
            output = output.append(get_period_end(game_id))
        elif all(x in df.loc[i, 'plays'] for x in ['Jump ball', 'possession']):
            output = output.append(get_jump_ball_data(df.loc[i], game_id))
        elif any(x in df.loc[i, 'plays'] for x in [' makes ', ' misses ']):
            output = output.append(get_shot_data(df.loc[i], game_id))
        elif ' rebound ' in df.loc[i, 'plays']:
            output = output.append(get_rebound_data(df.loc[i], output.tail(1), game_id))
        elif 'Turnover ' in df.loc[i, 'plays']:
            output = output.append(get_turnover_data(df.loc[i], game_id))
            if 'steal by' in df.loc[i, 'plays']:
                output = output.append(get_steal_data(df.loc[i], game_id))
        elif ' foul ' in df.loc[i, 'plays']:
            output = output.append(get_foul_data(df.loc[i], game_id))
        elif 'Violation' in df.loc[i, 'plays']:
            output = output.append(get_violation_data(df.loc[i], game_id))
        elif 'enters the game' in df.loc[i, 'plays']:
            output = output.append(get_substitution_data(df.loc[i], game_id))
        elif 'timeout' in df.loc[i, 'plays']:
            output = output.append(get_timeout_data(df.loc[i], game_id))
    output = output

    log_performance()
    return output


# any additional tidying goes here
def tidy_game_plays(df):
    # get list of teams
    teams = [i for i in set(df.team_id) if i is not None]

    # get index of period start rows
    period_start = df.index[df.event == 'Period Start']

    # get data from next row
    for i in period_start:
        df.loc[i, ['team_id', 'players', 'opp_players']] = df.loc[i+1, ['team_id', 'players', 'opp_players']]

    # get index of period end rows
    period_end = df.index[df.event == 'Period End']

    # get data from previous row
    for i in period_end:
        if df.possession[i-1] == 1 or df.event[i-1] == 'Assist':
            team_id = teams[teams != df.team_id[i-1]]
            players = df.opp_players[i-1]
            opp_players = df.players[i-1]
        else:
            team_id = df.team_id[i-1]
            players = df.players[i-1]
            opp_players = df.opp_players[i-1]
        df.loc[i, ['team_id', 'players', 'opp_players']] = [team_id, players, opp_players]

    log_performance()
    return df


def write_game_plays(series):
    for i in range(len(series)):
        game_start = time.process_time()

        # grab raw plays data for the given game_id from plays_raw table
        game_plays_raw = get_raw_plays(series[i])

        # base tidying up of events, details, period start and time
        game_plays = clean_plays(game_plays_raw).reset_index(drop=True)

        # fill down period from start of period row
        game_plays.period = game_plays.period.fillna(method='ffill')

        # tidying up unnecessary information
        game_plays = tidy_game_plays(game_plays)

        # generate column of scores
        game_plays.score = get_score(game_plays)

        # get players on the court for each play
        on_court_players = get_on_court_player_ids(game_plays)

        # get players for given team_id
        game_plays.players = on_court_players[0]

        # get opposition players for given team_id
        game_plays.opp_players = on_court_players[1]

        # clear rows in DB where game plays already exist
        try:
            connection_raw.execute(f'delete from nba.plays where game_id = "{series[i]}"')
        except ProgrammingError:
            pass

        cleaning_time = time.process_time() - game_start

        # write to DB and CSV and get status
        status = write_data(df=game_plays,
                            name='plays',
                            to_csv=False,
                            sql_engine=engine,
                            db_schema='nba',
                            if_exists='append',
                            index=False)

        writing_time = time.process_time() - game_start - cleaning_time

        time_taken = 'Cleaned in ' + "{:.2f}".format(cleaning_time) + ' seconds, '\
                     'Written in ' + "{:.2f}".format(writing_time) + ' seconds, '\
                     'Total ' + time_lapsed()

        # currently >2 seconds per game -> ~1.3 for clean_plays and ~0.7 for get_on_court_player_ids

        # show progress of loop
        progress(iteration=i,
                 iterations=len(series),
                 iteration_name=series[i],
                 lapsed=time_taken,
                 sql_status=status['sql'],
                 csv_status=status['csv'])


if __name__ == '__main__':
    # generate base columns
    columns = ['game_id', 'period', 'time', 'score', 'team_id', 'players', 'opp_players', 'player_id',
               'event', 'event_value', 'event_detail', 'possession']

    # initialise dataframe from scratch, or from DB
    plays = initialise_df(table_name='plays',
                          columns=columns,
                          sql_engine=engine,
                          meta=metadata)

    # load raw plays data to clean
    plays_raw = load_data(df='plays_raw',
                          sql_engine=engine_raw,
                          meta=metadata_raw)

    # load games table to access game_ids
    games = load_data(df='games',
                      sql_engine=engine,
                      meta=metadata)

    # load lineups to assist with assigning players to teams
    games_lineups = load_data(df='games_lineups',
                              sql_engine=engine,
                              meta=metadata)

    # set games to be cleaned
    game_ids = games.game_id

    # if skipping already cleaned games, then check and exclude games already in plays table
    if SKIP_SCRAPED_DAYS:
        game_ids = games.game_id[~games.game_id.isin(plays.game_id)].reset_index(drop=True)

    log_performance()

    write_game_plays(game_ids)
    write_performance()
