import aiosqlite
import asyncio
from pathlib import Path
from typing import List
from typing import Optional, Union, List, Tuple


def getDBfolder():
    current_dir = Path.cwd()
    root_dir = current_dir
    db_dir = root_dir / "db"
    db_dir.mkdir(exist_ok=True)  # create if folder does not exist
    return db_dir


class DataBase:
    def __init__(
        self, commands: List[str], db_name: str, db_folder: Path = getDBfolder()
    ):
        """Initialise the SQLite database. must include .sqlite file extension in database name"""
        path = db_folder / db_name
        path.touch(exist_ok=True)  # create if database does not exist
        self.path_to_db = path.resolve()
        self.name = db_name
        asyncio.run(self.initialise_database(commands))

    async def execute(
        self,
        sql: str,
        parameters: tuple | List[tuple] | None = None,
        fetch: str = "none",
    ) -> tuple | List[tuple] | None:
        async with aiosqlite.connect(self.path_to_db) as db:
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
                    print(f"Failed to execute SQL: {sql}")
                    print(f"Error: {e}")
                    await db.rollback()
                    raise  # Re-raise the exception after logging

    async def initialise_database(self, sql_list: List[str]):
        """sql_list = List of commands to initialise database. Cannot return any values"""
        async with aiosqlite.connect(self.path_to_db) as db:
            try:
                for sql in sql_list:
                    await db.execute(sql)
                await db.commit()
                print("Successfully Initialised", self.name)

            except Exception as e:
                print("Unsuccessfully Initialised", self.name)
                print(f"Error initializing databasesE: {e}")
                await db.rollback()
            return
