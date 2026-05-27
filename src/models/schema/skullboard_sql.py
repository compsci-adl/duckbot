"""
ABOUT Skullboard Schema:

Overview:

The Skullboard database stores information regarding posts on the skullboard. The database tracks:
- The top posts of all time
- The top users of all time
- The distribution for the number of skull reactions received for posts made in the last week/month/year/all-time
- Top reactors (users who add the most skull reactions)

Tables in this schema include:
- (posts): posts less than 7 days old are tracked and have skull counts updated.
- (hof): the Hall of Fame which tracks the top 100 posts of all time.
- (users): counts the number of posts which reached a minimum reaction threshold sent by each user.
- (days): stores the distribution of skull reactions for all posts sent within a day (for days between 7 and 365 days ago).
- (alltime): stores the distribution of skull reactions for all posts older than 365 days.
- (reactor_posts): temporary table recording which users reacted to which posts while posts are tracked.
- (reactors): aggregated long-term counts of skull reactions added by users (updated during expiry).

Info :

Post tracking:
Posts up to 7 days old are stored in (posts). These posts are considered tracked, where reaction counts to these posts are still updated.

Data expiration:
Posts older than 7 days in (posts) are no longer tracked and are subject to expiration. Tables like (hof), (users), (days), and (reactors) store expired data long-term for queries. A routine in DuckBot's __init__() function automatically expires content on startup and once a day.

Reactor tracking:
While a post is tracked (within the 7-day window), each skull reaction by a user is recorded in (reactor_posts). When posts expire, reactor counts are aggregated into (reactors) and reactor_posts rows for those posts are removed. This enables the `/skull reactors` command to show the users who add the most skull reactions.

"""


class SkullSQL:
    """Store SQL statements for the skullboard functionalities.
    Each variable is named after the function or functionality associated with the statements.
    """

    """Initialise the Skullboard database's tables."""
    initialisation_tables = [
        """
    CREATE TABLE IF NOT EXISTS alltime (
    bucket INTEGER,
    guildId INTEGER,
    frequency INTEGER,
    PRIMARY KEY (bucket, guildId)
    );""",
        """CREATE TABLE IF NOT EXISTS posts (
    postId INTEGER PRIMARY KEY,
    userId INTEGER,
    channelId INTEGER,
    day INTEGER,
    frequency INTEGER,
    guildId INTEGER
    );""",
        """CREATE TABLE IF NOT EXISTS days (
    day INTEGER,
    bucket INTEGER,
    frequency INTEGER,
    guildId INTEGER,
    PRIMARY KEY (day, bucket, guildId)
    );""",
        """CREATE TABLE IF NOT EXISTS users (
    userId INTEGER,
    guildId INTEGER,
    frequency INTEGER,
    PRIMARY KEY (userId, guildId)
    );
    """,
        """CREATE TABLE IF NOT EXISTS reactor_posts (
    postId INTEGER,
    reactorId INTEGER,
    guildId INTEGER,
    PRIMARY KEY (postId, reactorId)
    );""",
        """CREATE TABLE IF NOT EXISTS reactors (
    reactorId INTEGER,
    guildId INTEGER,
    frequency INTEGER,
    PRIMARY KEY (reactorId, guildId)
    );""",
        """CREATE TABLE IF NOT EXISTS reactor_progress (
    guildId INTEGER,
    channelId INTEGER,
    last_message_id INTEGER,
    completed INTEGER DEFAULT 0,
    PRIMARY KEY (guildId, channelId)
    );""",
        """CREATE TABLE IF NOT EXISTS hof (
    postId INTEGER PRIMARY KEY,
    userId INTEGER,
    channelId INTEGER,
    day INTEGER,
    frequency INTEGER,
    guildId INTEGER
    );""",
    ]

    """Update the count of skull reactions for a post."""
    update_skull_post = """
    INSERT INTO posts(postId, userId, channelId, day, frequency, guildId)
    VALUES(?,?,?,?,?,?)
    ON CONFLICT(postId) DO UPDATE SET
    frequency = excluded.frequency;
    """

    """Gets the top posts from the last 7 days.
    Fetches from the tracked posts in (posts)"""
    day_7_post = """SELECT postId, userId, channelId, day, frequency FROM posts
    WHERE guildId = ?
    ORDER BY frequency DESC, day ASC
    LIMIT ?;
    """

    """Get the top x users by number of posts on the skullboard that reach the minimum reaction threshold.
    Combines the reaction counts of tracked posts from the last 7 days (posts), in addition to the counts of users in the (users) table. """
    user_rankings = """
    SELECT userId, SUM(total_frequency) as total_frequency
    FROM (
    SELECT userId, COUNT(*) AS total_frequency
    FROM posts
    WHERE frequency >= ? AND guildId = ?
    GROUP BY userId

    UNION ALL

    SELECT userId, frequency as total_frequency
    FROM users
    WHERE guildId = ?
    )
    GROUP BY userId
    ORDER BY total_frequency DESC
    LIMIT ?;
    """

    """Get the top x posts (maximum of 100) by number of reactions.
    Combines the reaction counts of tracked posts from the last 7 days (posts), in addition to the top posts in the Hall of Fame (hof) table. """
    hof_rankings = """
    SELECT postId, userId, channelId, day, frequency
    FROM (
    SELECT postId, userId, channelId, day, frequency
    FROM posts
    WHERE frequency >= ? AND guildId = ?

    UNION ALL

    SELECT postId, userId, channelId, day, frequency
    FROM hof
    WHERE guildId = ?
    )
    ORDER BY
    frequency DESC,
    day DESC
    LIMIT ?;
    """

    """Get the distribution of skull post reaction counts for the last 7 days.
    Fetches tracked posts from the last 7 days (posts)."""
    histogram_7 = """
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM posts
    WHERE guildId = ?
    GROUP BY bucket;"""

    """Get the distribution of skull post reaction counts for the last 7 days.
    Fetches tracked posts from the last 7 days (posts), as well as reaction distributions of days stored in (days)"""
    histogram_30 = """
    SELECT bucket, SUM(count) as COUNT
    FROM
    (
    select bucket,SUM(frequency) as count
    from days
    where day > ? AND guildId = ?
    group by bucket
    union all
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM posts
    WHERE guildId = ?
    GROUP BY frequency
    ) AS t
    where bucket > 0
    GROUP BY bucket;"""

    """Get the distribution of skull post reaction counts for the last 365 days.
    Fetches tracked posts from the last 7 days (posts), as well as reaction distributions of days stored in (days)"""
    histogram_365 = """
    SELECT bucket, SUM(count) as COUNT
    FROM
    (
    select bucket,SUM(frequency) as count
    from days
    where guildId = ?
    group by bucket
    union all
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM posts
    WHERE guildId = ?
    GROUP BY bucket
    ) AS t
    where bucket > 0
    GROUP BY bucket;"""

    """Get the distribution of skull post reaction counts for the last 365 days.
    Fetches tracked posts from the last 7 days (posts), as well as reaction distributions of days stored in (days), and days stored in alltime"""
    histogram_alltime = """
    SELECT bucket, SUM(count) as COUNT
    FROM
    (
    select bucket,SUM(frequency) as count
    from days
    where guildId = ?
    group by bucket
    union all
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM posts
    WHERE guildId = ?
    GROUP BY bucket
    UNION all
    select bucket,frequency as count
    From alltime
    where guildId = ?
    ) AS t
    where bucket > 0
    GROUP BY bucket;
    """

    """Adds expired posts which meet a minimum reaction threshold into the hall of fame."""
    posts_expire_hof = """
    INSERT INTO hof (postId, userId, channelId, day, frequency, guildId)
    SELECT postId, userId, channelId, day, frequency, guildId
    FROM posts
    WHERE day <= ? AND frequency >= ? AND guildId = ?;
    """

    """The hof_expire_x commands are a sequence of sql commands which orders and store only the top 100 posts."""
    hof_expire_hof_1 = """
    CREATE TABLE top_posts AS
    SELECT postId, userId, channelId, day, frequency, guildId
    FROM hof
    WHERE guildId = ?
    ORDER BY frequency DESC, day DESC
    LIMIT 100;
    """
    hof_expire_hof_2 = """
    DELETE FROM hof WHERE guildId = ?;
    """
    hof_expire_hof_3 = """
    INSERT INTO hof (postId, userId, channelId, day, frequency, guildId)
    SELECT postId, userId, channelId, day, frequency, guildId
    FROM top_posts;
    """
    hof_expire_hof_4 = """
    DROP TABLE top_posts;
    """
    hof_expire_hof = [
        hof_expire_hof_1,
        hof_expire_hof_2,
        hof_expire_hof_3,
        hof_expire_hof_4,
    ]

    """Adds the count of reactions for expired posts meeting a minimum reaction threshold to (users)."""
    posts_expire_users = """
    INSERT INTO users (userId, guildId, frequency)
    SELECT userId, guildId, COUNT(*) AS frequency
    FROM posts
    WHERE day <= ? AND frequency >= ? AND guildId = ?
    GROUP BY userId, guildId
    ON CONFLICT(userId, guildId) DO UPDATE SET frequency = users.frequency + excluded.frequency;
    """

    insert_reactor_post = """
    INSERT INTO reactor_posts (postId, reactorId, guildId)
    VALUES(?,?,?)
    ON CONFLICT(postId, reactorId) DO NOTHING;
    """

    delete_reactor_post = """
    DELETE FROM reactor_posts WHERE postId = ? AND reactorId = ? AND guildId = ?;
    """

    posts_expire_reactors = """
    INSERT INTO reactors (reactorId, guildId, frequency)
    SELECT reactorId, guildId, COUNT(*) AS frequency
    FROM reactor_posts
    WHERE postId IN (SELECT postId FROM posts WHERE day <= ? AND guildId = ?)
    GROUP BY reactorId, guildId
    ON CONFLICT(reactorId, guildId) DO UPDATE SET frequency = reactors.frequency + excluded.frequency;
    """

    posts_expire_reactor_posts_delete = """
    DELETE FROM reactor_posts
    WHERE postId IN (SELECT postId FROM posts WHERE day <= ? AND guildId = ?);
    """

    reactor_rankings = """
    SELECT reactorId, SUM(total_frequency) as total_frequency
    FROM (
    SELECT reactorId, COUNT(*) AS total_frequency
    FROM reactor_posts
    WHERE guildId = ?
    GROUP BY reactorId

    UNION ALL

    SELECT reactorId, frequency as total_frequency
    FROM reactors
    WHERE guildId = ?
    )
    GROUP BY reactorId
    ORDER BY total_frequency DESC
    LIMIT ?;
    """

    increment_reactor = """
    INSERT INTO reactors (reactorId, guildId, frequency)
    VALUES(?,?,?)
    ON CONFLICT(reactorId, guildId) DO UPDATE SET
    frequency = reactors.frequency + excluded.frequency;
    """

    reactor_progress_get = """
    SELECT last_message_id, completed
    FROM reactor_progress
    WHERE guildId = ? AND channelId = ?
    LIMIT 1;
    """

    reactor_progress_set = """
    INSERT INTO reactor_progress (guildId, channelId, last_message_id, completed)
    VALUES(?,?,?,?)
    ON CONFLICT(guildId, channelId) DO UPDATE SET
    last_message_id = excluded.last_message_id,
    completed = excluded.completed;
    """

    aggregate_reactor_posts_all = """
    INSERT INTO reactors (reactorId, guildId, frequency)
    SELECT reactorId, guildId, COUNT(*) AS frequency
    FROM reactor_posts
    GROUP BY reactorId, guildId
    ON CONFLICT(reactorId, guildId) DO UPDATE SET frequency = reactors.frequency + excluded.frequency;
    """

    clear_reactor_posts = """
    DELETE FROM reactor_posts;
    """

    decrement_reactor = """
    UPDATE reactors
    SET frequency = CASE WHEN frequency > ? THEN frequency - ? ELSE 0 END
    WHERE reactorId = ? AND guildId = ?;
    """

    delete_zero_reactors = """
    DELETE FROM reactors WHERE frequency <= 0;
    """

    mark_all_reactor_progress_completed = """
    UPDATE reactor_progress SET completed = 1;
    """

    """Adds the count of reactions for expired posts to (days), for the day of expiry."""
    posts_expire_days = """
    INSERT INTO days (day, bucket, frequency, guildId)
    SELECT day, frequency AS bucket, COUNT(*) AS frequency, guildId
    FROM posts
    WHERE day <= ? AND frequency > 0 AND guildId = ?
    GROUP BY day, frequency, guildId;
    """

    """Removes expired posts from tracked posts"""
    posts_expire_delete = "DELETE FROM posts WHERE day <= ? AND guildId = ?;"

    """Expires days older than 365 days old, into longterm tracking (alltime)"""
    days_expire_alltime = """
    INSERT INTO alltime (bucket, guildId, frequency)
    SELECT bucket, guildId, SUM(frequency) AS total_frequency
    FROM days
    WHERE day < ? AND guildId = ?
    GROUP BY bucket, guildId
    ON CONFLICT(bucket, guildId) DO UPDATE SET frequency = alltime.frequency + EXCLUDED.frequency;
    """

    """Removes days older than 365 days old"""
    days_expire_delete = """
    DELETE FROM days
    WHERE day < ? AND guildId = ?;
    """
