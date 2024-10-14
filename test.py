"""MariaDB test database program.  Simply uploads this file to a MariaDB database.
You can check the uploaded content using phpMyAdmin."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue, MariaDBDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import types as sa_types
from sqlalchemy.dialects.mysql import types as mysql_types
from sqlmodel import Field, Session, SQLModel, create_engine


class DBSettings(BaseSettings):
    """Pydantic Settings class for the database connection info.  Note we have fixed the database
    engine to mariadb+pymysql.

    Note to avoid clashes with key environment variables such as $USER, we apply a "dbtest_"
    prefix."""

    user: str
    password: str
    host: str = Field(default='localhost')
    port: int = Field(default=3306)
    database: str

    @computed_field
    @property
    def connection_str(self) -> MariaDBDsn:
        """Build the connection string from the fields."""

        conn = MariaDBDsn(
            f'mariadb+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}'
        )
        return str(conn)

    model_config = SettingsConfigDict(
        env_prefix='testdb_',
        env_file='secret.env',
        env_file_encoding='utf-8'
    )


settings = DBSettings(database='db_test')


class MyModel(SQLModel, table=True):
    """A file with an id and name."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4, sa_type=sa_types.UUID, primary_key=True)

    # Saved as VARCHAR(256)
    filename: str = Field(index=True, max_length=256)

    # Converted to MariaDB's DATETIME type
    uploaded: datetime = Field(default_factory=lambda: datetime.now(UTC))

    file_bytes: bytes = Field(sa_type=mysql_types.LONGBLOB)
    json_data: JsonValue = Field(sa_type=sa_types.JSON)


print(settings.connection_str)
engine = create_engine(settings.connection_str, echo=True,
                       connect_args={'connect_timeout': 30, 'max_allowed_packet': 1073741824})


def init_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def upload(filename: str, file_bytes: bytes, json_data: JsonValue):
    """Upload a file to the database."""
    with Session(engine) as session:
        obj = MyModel(filename=filename, file_bytes=file_bytes, json_data=json_data)
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj.id


if __name__ == '__main__':
    init_db()

    path = Path(__file__).parent / 'test.pdf'
    with open(path, 'rb') as file:
        f_bytes = file.read()

    json_obj = {
        'field1': ['a', 'b', 'c'],
        'field2': {
            'str': '123',
            'int': 123
        }
    }

    upload(path.name, f_bytes, json_obj)
