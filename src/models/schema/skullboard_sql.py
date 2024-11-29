"""
ABOUT Skullboard Schema:

Overview:

The Skullboard database stores infomation regarding posts on the skullboard. The database tracks:
- The top posts of all time
- The top users of all time
- The distribution for the number of skull received for posts made in the last week/month/year/alltime

Tables in this schema include:
- (posts); posts less than 7 days old are "tracked", and have the skullcount continually updated.
- (hof); the Hall of Fame which tracks the top 100 posts of all time
- (users); counts the number of posts which reached a minimum reaction threshold sent by each user.
- (days); stores the distribution of skull reactions for all posts sent within a day. stores distributions for days between 7 and 365 days ago.
- (alltime); stores the distribution of skull reactions for all posts sent after 365 days.

Info :

Post tracking:
Posts up to 7 days old are stored in (posts).
These posts are considered "tracked", where the reaction counts to these posts are still updated in the database.

Data expiration:
Posts older than 7 days old in (posts) are no longer "tracked", and are subject to "expiration".
Tables like (hof),(users), and (days) store this expired data long term, for their related queries.
A routine in DuckBot's __init__() function automatically expires content on startup and once a day.
"""


class SkullSQL:
    """Store SQL statements for the skullboard functionalities.
    Each variable is named after the function or functionality associated with the statements.
    """

    """Initialise the Skullboard database's tables."""
    initialisation_tables = [
        """
    CREATE TABLE IF NOT EXISTS alltime (
    bucket INTEGER PRIMARY KEY,
    frequency INTEGER
    );""",
        """CREATE TABLE IF NOT EXISTS posts (
    postId INTEGER PRIMARY KEY,
    userId INTEGER,
    channelId INTEGER,
    day INTEGER,
    frequency INTEGER
    );""",
        """CREATE TABLE IF NOT EXISTS days (
    day INTEGER,
    bucket INTEGER,
    frequency INTEGER,
    PRIMARY KEY (day, bucket)
    );""",
        """CREATE TABLE IF NOT EXISTS users (
    userId INTEGER PRIMARY KEY,
    frequency INTEGER
    );
    """,
        """CREATE TABLE IF NOT EXISTS hof (
    postId INTEGER PRIMARY KEY,
    userId INTEGER,
    channelId INTEGER,
    day INTEGER,
    frequency INTEGER
    );""",
    ]

    """Update the count of skull reactions for a post."""
    update_skull_post = """
    INSERT INTO posts(postId, userId, channelId, day, frequency)
    VALUES(?,?,?,?,?)
    ON CONFLICT(postId) DO UPDATE SET
    frequency = excluded.frequency;
    """

    """Gets the top posts from the last 7 days.
    Fetches from the tracked posts in (posts)"""
    day_7_post = """SELECT * FROM posts
    ORDER BY frequency DESC, day ASC
    LIMIT ?;
    """

    """Get the top x users by number of posts on the skullboard that reach the minimum reaction threshold.
    Combines the reaction counts of tracked posts from the last 7 days (posts), in addition to the counts of users in the (users) table. """
    user_rankings = """
    SELECT userId, SUM(frequency) as total_frequency
    FROM (
    SELECT userId, COUNT(*) AS frequency
    FROM posts
    WHERE frequency >= ?
    GROUP BY userId

    UNION ALL

    SELECT userId, frequency
    FROM users
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
    WHERE frequency >= ?

    UNION ALL

    SELECT postId, userId, channelId, day, frequency
    FROM hof
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
    FROM   posts
    GROUP BY bucket;"""

    """Get the distribution of skull post reaction counts for the last 7 days.
    Fetches tracked posts from the last 7 days (posts), as well as reaction distributions of days stored in (days)"""
    histogram_30 = """
    SELECT bucket, SUM(count) as COUNT
    FROM
    (
    select bucket,SUM(frequency) as count
    from days
    where day > ?
    group by bucket
    union all
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM   posts
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
    group by bucket
    union all
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM   posts
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
    group by bucket
    union all
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM   posts
    GROUP BY bucket
    UNION all
    select bucket,frequency as count
    From alltime
    ) AS t
    where bucket > 0
    GROUP BY bucket;
    """

    """Adds expired posts which meet a minimum reaction threshold into the hall of fame."""
    posts_expire_hof = """
    INSERT INTO hof (postId, userId, channelId, day, frequency)
    SELECT postId, userId, channelId, day, frequency
    FROM posts
    WHERE day <= ? AND frequency >= ?;
    """

    """The hof_expire_x commands are a sequence of sql commands which orders and store only the top 100 posts."""
    hof_expire_hof_1 = """
    CREATE TABLE top_posts AS
    SELECT postId, userId, channelId, day, frequency
    FROM hof
    ORDER BY frequency DESC, day DESC
    LIMIT 100;
    """
    hof_expire_hof_2 = """
    DELETE FROM hof;
    """
    hof_expire_hof_3 = """
    INSERT INTO hof (postId, userId, channelId, day, frequency)
    SELECT postId, userId, channelId, day, frequency
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
    INSERT INTO users (userId, frequency)
    SELECT userId, COUNT(*) AS frequency
    FROM posts
    WHERE day <= ? AND frequency >= ?
    GROUP BY userId
    ON CONFLICT(userId) DO UPDATE SET frequency = users.frequency + excluded.frequency;
    """

    """Adds the count of reactions for expired posts to (days), for the day of expiry."""
    posts_expire_days = """
    INSERT INTO days (day, bucket, frequency)
    SELECT day, frequency AS bucket, COUNT(*) AS frequency
    FROM posts
    WHERE day <= ? AND frequency > 0
    GROUP BY day, frequency;
    """

    """Removes expired posts from tracked posts"""
    posts_expire_delete = "DELETE FROM posts WHERE day <= ?;"

    """Expires days older than 365 days old, into longterm tracking (alltime)"""
    days_expire_alltime = """
    INSERT INTO alltime (bucket, frequency)
    SELECT bucket, SUM(frequency) AS total_frequency
    FROM days
    WHERE day < ?
    GROUP BY bucket
    ON CONFLICT(bucket) DO UPDATE SET frequency = alltime.frequency + EXCLUDED.frequency;
    """

    """Removes days older than 365 days old"""
    days_expire_delete = """
    DELETE FROM days
    WHERE day < ?;
    """
