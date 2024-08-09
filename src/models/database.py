import aiosqlite
import asyncio
import logging

import asyncio
from functools import wraps
from pathlib import Path
from typing import List
from typing import Optional, Union, List, Tuple


"""/////////////////UTILS///////////////////////"""


def get_db_folder():
    db_dir = Path.cwd() / "db"
    db_dir.mkdir(exist_ok=True)  # create if folder does not exist
    return db_dir


"""/////////////////////////////////////////////"""


class DataBase:
    """A wrapper for a SQLite database"""

    def __init__(
        self, commands: List[str], db_name: str, db_folder: Path = get_db_folder()
    ):
        """Initialise the SQLite database. must include .sqlite file extension in database name"""
        path = db_folder / db_name
        path.touch(exist_ok=True)  # create if database does not exist
        self.db_path = path.resolve()
        self.name = db_name
        asyncio.run(
            self.initialise_database(commands)
        )  # Catastrophic error: will crash if initialise_database fails

    def crash_handler(func):
        """Decorator to handle crashes in async functions by logging exceptions and returning None."""

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logging.exception(f"{func.__name__} : args({args}) kwargs({kwargs})")
                return None  # Suppress the exception and return None

        return wrapper

    async def execute(
        self,
        sql: str,
        parameters: tuple | List[tuple] | None = None,
        fetch: str = "none",
    ) -> tuple | List[tuple] | None:
        """Execute a SQLite command into a database.
        Parameters are used for (?) values in SQL statements.
        May choose to retrieve data from query, and whether to return one or all rows (fetch= "none" | "one" | "all").

        Execute() raises an error when there is a databse error. In most cases, this should be handled by crash_handler.
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.cursor() as cursor:
                try:
                    if parameters:
                        await cursor.execute(sql, parameters)
                    else:
                        await cursor.execute(sql)

                    if fetch == "one":
                        result = await cursor.fetchone()
                    elif fetch == "all":
                        result = await cursor.fetchall()
                    else:
                        result = None

                    await db.commit()
                    return result

                except Exception as e:
                    logging.exception("SQLite execution")
                    await db.rollback()
                    raise  # Re-raise the exception after logging

    async def initialise_database(self, sql_list: List[str]):
        """List of commands to initialise database with. Cannot return any values"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                for sql in sql_list:
                    await db.execute(sql)
                await db.commit()
                print("Successfully Initialised", self.name)

            except Exception as e:
                logging.exception(f"Database Initialisation: {self.name}")
                await db.rollback()
                raise  # Re-raise the exception after logging
            return
