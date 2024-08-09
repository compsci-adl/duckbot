class SkullSQL:
    """Store SQL statements for the skullboard functionalities.
    Each variable is named after the function or functionality associated with the statements
    SQL statements intended to be executed sequentially are placed in lists
    """

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

    update_skull_post = """
    INSERT INTO posts(postId, userId, channelId, day, frequency)
    VALUES(?,?,?,?,?)
    ON CONFLICT(postId) DO UPDATE SET
    frequency = excluded.frequency;
    """

    histogram_7 = """
    SELECT frequency AS bucket,
    COUNT(frequency) AS count
    FROM   posts
    GROUP BY bucket;"""

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
    posts_expire_hof = """
    INSERT INTO hof (postId, userId, channelId, day, frequency)
    SELECT postId, userId, channelId, day, frequency
    FROM posts
    WHERE day <= ? AND frequency >= ?;
    """

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

    posts_expire_users = """
    INSERT INTO users (userId, frequency)
    SELECT userId, COUNT(*) AS frequency
    FROM posts
    WHERE day <= ? AND frequency >= ?
    GROUP BY userId
    ON CONFLICT(userId) DO UPDATE SET frequency = users.frequency + excluded.frequency;
    """

    posts_expire_days = """
    INSERT INTO days (day, bucket, frequency)
    SELECT day, frequency AS bucket, COUNT(*) AS frequency
    FROM posts
    WHERE day <= ? AND frequency > 0
    GROUP BY day, frequency;
    """

    posts_expire_delete = "DELETE FROM posts WHERE day <= ?;"

    days_expire_alltime = """
    INSERT INTO alltime (bucket, frequency)
    SELECT bucket, SUM(frequency) AS total_frequency
    FROM days
    WHERE day < ?
    GROUP BY bucket
    ON CONFLICT(bucket) DO UPDATE SET frequency = alltime.frequency + EXCLUDED.frequency;
    """
    days_expire_delete = """
    DELETE FROM days
    WHERE day < ?;
    """
    day_7_post = """SELECT * FROM posts
    ORDER BY frequency DESC, day ASC
    LIMIT ?;
    """

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
